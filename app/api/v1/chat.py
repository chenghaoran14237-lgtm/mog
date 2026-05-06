from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.providers.errors import ProviderError
from app.providers.registry import ProviderRegistry
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.schemas.conversation import (
    AnalysisRunDetailResponse,
    AnalysisRunListResponse,
    AnalysisRunSummaryResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    ChatResponse,
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
)
from app.services.analysis_fallback import build_health_analysis_fallback
from app.services.conversation_context_service import ConversationContextService
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_conversation_service(session: Session = Depends(get_session)) -> ConversationService:
    llm_provider = ProviderRegistry().build_llm_provider()
    document_version_repo = DocumentVersionRepository(session)
    measurement_repo = MeasurementRepository(session)
    context_service = ConversationContextService(document_version_repo, measurement_repo)
    return ConversationService(session, llm_provider, context_service)


def _build_batch_analysis_messages(
    *,
    conversation_service: ConversationService,
    user_id: int,
    document_version_ids: list[int],
    prompt: str,
) -> tuple[list[dict], int, str, list[int], list[dict]]:
    from app.repositories.document_version_repository import DocumentVersionRepository

    session = conversation_service.session
    doc_version_repo = DocumentVersionRepository(session)
    valid_versions = [
        version
        for version_id in document_version_ids
        if (version := doc_version_repo.get_by_id(version_id, user_id=user_id)) is not None
    ]
    valid_version_ids = [version.id for version in valid_versions]
    source_documents = [
        {
            "document_id": version.document_id,
            "document_version_id": version.id,
            "title": getattr(version.document, "display_name", None) or f"文档 {version.document_id}",
            "document_category": getattr(version.document, "document_category", None),
            "report_date": (version.report_date or getattr(version.document, "report_date", None) or version.created_at).isoformat(),
        }
        for version in valid_versions
    ]

    context_text = conversation_service.context_service.build_context_for_version_ids(
        user_id=user_id,
        selected_version_ids=valid_version_ids,
    )

    system_prompt = """你不是“文档总结器”，而是用户的私人家庭医生式健康分析助手。
你的首要任务不是复述报告原文，而是基于报告内容做判断、整合和建议。只有在支撑判断时，才允许少量引用或概括原文。

你必须遵守以下规则：
1. 不要按文档顺序大段复述，不要把回答写成“报告里写了什么”的流水账。
2. 先抓住最重要的临床问题，再解释证据，再给建议。
3. 你的价值在于：整合多份报告、识别风险、指出轻重缓急、告诉用户接下来该做什么。
4. 如果发现明确异常、危险信号、需要尽快复诊或急诊的情形，要直接说清楚，不要含糊。
5. 如果信息不足，可以说明不确定性，但仍然要在现有信息基础上给出最稳妥的建议。
6. 不要因为缺少结构化测量值就拒绝分析；病历叙事、诊断、治疗经过、出院医嘱同样重要。
7. 语气要像谨慎、专业、克制的家庭医生，不要空泛安慰，不要模板化套话。

请严格按下面结构输出，除非用户明确要求别的格式：

一、核心判断
- 用 2 到 4 句话直接说明目前最值得关注的问题，不要复述全文。

二、我最关心的风险点
- 列出 3 到 5 条最重要的风险或异常。
- 每条都要说明“为什么值得注意”。

三、接下来怎么做
- 给出具体、现实、可执行的建议。
- 优先包含：复查项目、复诊科室、用药沟通、生活方式注意事项、需要补充的信息。

四、哪些情况要尽快就医
- 明确写出应尽快线下就诊或急诊的触发条件。

五、我的依据
- 只用简短方式点出你判断所依据的关键报告信息，不要再次长篇复述原文。
"""
    system_prompt += f"\n{context_text}\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    return messages, len(valid_version_ids), context_text, valid_version_ids, source_documents


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """创建新对话"""
    conversation = conversation_service.create_conversation(
        user_id=current_user.id,
        title=data.title,
    )
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """列出所有对话"""
    conversations = conversation_service.list_conversations(user_id=current_user.id)
    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations]
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """获取对话详情"""
    conversation = conversation_service.get_conversation(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if not conversation:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
def get_conversation_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """获取对话消息列表"""
    conversation = conversation_service.get_conversation(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if not conversation:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Conversation not found")

    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in conversation.messages]
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
def send_message(
    conversation_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """发送消息"""
    try:
        assistant_message = conversation_service.send_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            message=data.message,
            context_document_ids=data.context_document_ids,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI analysis service is temporarily unavailable: {exc.message}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # 获取用户消息（刚保存的）
    conversation = conversation_service.get_conversation(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    user_message = conversation.messages[-2]  # 倒数第二条是用户消息

    return ChatResponse(
        user_message=MessageResponse.model_validate(user_message),
        assistant_message=MessageResponse.model_validate(assistant_message),
    )


@router.post("/conversations/batch-analyze", response_model=BatchAnalyzeResponse)
def batch_analyze(
    data: BatchAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """批量分析多份文档"""
    from app.providers.errors import ProviderError

    start_time = time.time()
    messages, document_count, context_text, selected_version_ids, source_documents = _build_batch_analysis_messages(
        conversation_service=conversation_service,
        user_id=current_user.id,
        document_version_ids=data.document_version_ids,
        prompt=data.prompt,
    )

    try:
        llm_response = conversation_service.llm_provider.chat(messages=messages, temperature=0.7)
    except ProviderError as e:
        llm_response = build_health_analysis_fallback(
            prompt=data.prompt,
            context_text=context_text,
            document_count=document_count,
            reason=e.message,
        )

    processing_time_ms = int((time.time() - start_time) * 1000)
    history = conversation_service.save_analysis_run(
        user_id=current_user.id,
        prompt=data.prompt,
        result=llm_response,
        context_text=context_text,
        selected_document_version_ids=selected_version_ids,
        source_documents=source_documents,
    )

    return BatchAnalyzeResponse(
        result=llm_response,
        document_count=document_count,
        processing_time_ms=processing_time_ms,
        history_id=history.id,
    )


@router.post("/conversations/batch-analyze/stream")
def batch_analyze_stream(
    data: BatchAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """批量分析多份文档并流式返回结果"""
    from app.providers.errors import ProviderError

    start_time = time.time()
    messages, document_count, context_text, selected_version_ids, source_documents = _build_batch_analysis_messages(
        conversation_service=conversation_service,
        user_id=current_user.id,
        document_version_ids=data.document_version_ids,
        prompt=data.prompt,
    )

    def event(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False) + "\n"

    def generate():
        chunks: list[str] = []
        yield event({"type": "meta", "document_count": document_count})
        try:
            for chunk in conversation_service.llm_provider.stream_chat(messages=messages, temperature=0.7):
                if chunk:
                    chunks.append(chunk)
                    yield event({"type": "delta", "content": chunk})
        except ProviderError as e:
            fallback = build_health_analysis_fallback(
                prompt=data.prompt,
                context_text=context_text,
                document_count=document_count,
                reason=e.message,
            )
            chunks.append(fallback)
            yield event({"type": "delta", "content": fallback})

        processing_time_ms = int((time.time() - start_time) * 1000)
        history = conversation_service.save_analysis_run(
            user_id=current_user.id,
            prompt=data.prompt,
            result="".join(chunks),
            context_text=context_text,
            selected_document_version_ids=selected_version_ids,
            source_documents=source_documents,
        )
        yield event({
            "type": "done",
            "processing_time_ms": processing_time_ms,
            "document_count": document_count,
            "history_id": history.id,
        })

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/analysis-runs", response_model=AnalysisRunListResponse)
def list_analysis_runs(
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    items = conversation_service.list_analysis_runs(user_id=current_user.id)
    return AnalysisRunListResponse(
        items=[AnalysisRunSummaryResponse.model_validate(item) for item in items]
    )


@router.get("/analysis-runs/{analysis_run_id}", response_model=AnalysisRunDetailResponse)
def get_analysis_run(
    analysis_run_id: int,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    item = conversation_service.get_analysis_run(user_id=current_user.id, analysis_run_id=analysis_run_id)
    if not item:
        raise HTTPException(status_code=404, detail="Analysis history not found")
    return AnalysisRunDetailResponse.model_validate(item)


@router.delete("/analysis-runs/{analysis_run_id}", status_code=204)
def delete_analysis_run(
    analysis_run_id: int,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    deleted = conversation_service.delete_analysis_run(
        user_id=current_user.id,
        analysis_run_id=analysis_run_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Analysis history not found")
