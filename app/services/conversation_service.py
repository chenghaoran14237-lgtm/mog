from __future__ import annotations

from sqlalchemy import select

from app.models.analysis_run import AnalysisRun
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.providers.errors import ProviderError
from app.providers.base import LLMProvider
from app.providers.rag import RAGProvider, StubRAGProvider
from app.services.analysis_fallback import build_health_analysis_fallback
from app.services.conversation_context_service import ConversationContextService


class ConversationService:
    """对话服务"""

    def __init__(
        self,
        session,
        llm_provider: LLMProvider,
        context_service: ConversationContextService,
        rag_provider: RAGProvider | None = None,
    ) -> None:
        self.session = session
        self.llm_provider = llm_provider
        self.context_service = context_service
        self.rag_provider = rag_provider or StubRAGProvider()

    def create_conversation(self, *, user_id: int, title: str) -> Conversation:
        """创建新对话"""
        conversation = Conversation(
            user_id=user_id,
            title=title,
        )
        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def send_message(
        self,
        *,
        user_id: int,
        conversation_id: int,
        message: str,
        context_document_ids: list[int] | None = None,
    ) -> ConversationMessage:
        """发送消息并获取回复"""
        # 验证对话归属
        conversation = self.session.get(Conversation, conversation_id)
        if not conversation or conversation.user_id != user_id:
            raise ValueError("Conversation not found")

        # 保存用户消息
        user_message = ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            content=message,
            context_document_ids=context_document_ids or [],
        )
        self.session.add(user_message)
        self.session.flush()

        # 构建上下文
        health_context = ""
        if context_document_ids:
            health_context = self.context_service.build_context(
                user_id=user_id,
                selected_document_ids=context_document_ids,
            )

        # 检索医疗指南（RAG）
        guideline_context = ""
        rag_results = self.rag_provider.retrieve(message, top_k=3)
        if rag_results:
            guideline_context = "\n\n相关医疗指南：\n"
            for result in rag_results:
                guideline_context += f"- {result.get('content', '')}\n"

        # 构建完整系统提示
        system_prompt = (
            "你是用户的私人家庭医生式健康助手。"
            "你需要综合用户提供的检查报告、病历叙述、诊断、治疗经过和复查建议来回答。"
            "不要把回答写成对原文的重复转述，而要优先给出判断、建议、风险轻重和下一步安排。"
            "如果用户没有特别要求，请默认按“核心判断 / 风险点 / 下一步建议 / 何时尽快就医”来组织回答。"
        )
        if health_context:
            system_prompt += f"\n\n{health_context}"
        if guideline_context:
            system_prompt += guideline_context

        # 获取历史消息
        history_messages = self._get_conversation_history(conversation_id, limit=10)

        # 调用LLM
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": message})

        try:
            llm_response = self.llm_provider.chat(messages=messages, temperature=0.7)
        except ProviderError as exc:
            llm_response = build_health_analysis_fallback(
                prompt=message,
                context_text=health_context,
                document_count=len(context_document_ids or []),
                reason=exc.message,
            )

        # 保存助手回复
        assistant_message = ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=llm_response,
            context_document_ids=[],
        )
        self.session.add(assistant_message)
        self.session.commit()
        self.session.refresh(assistant_message)

        return assistant_message

    def _get_conversation_history(self, conversation_id: int, limit: int = 10) -> list[dict]:
        """获取对话历史"""
        statement = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.id.desc())
            .limit(limit)
        )
        messages = list(self.session.scalars(statement).all())
        messages.reverse()

        return [{"role": m.role, "content": m.content} for m in messages[:-1]]

    def list_conversations(self, *, user_id: int) -> list[Conversation]:
        """列出用户的所有对话"""
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def get_conversation(self, *, user_id: int, conversation_id: int) -> Conversation | None:
        """获取对话详情"""
        conversation = self.session.get(Conversation, conversation_id)
        if conversation and conversation.user_id == user_id:
            return conversation
        return None

    def save_analysis_run(
        self,
        *,
        user_id: int,
        prompt: str,
        result: str,
        context_text: str,
        selected_document_version_ids: list[int],
        source_documents: list[dict],
    ) -> AnalysisRun:
        analysis_run = AnalysisRun(
            user_id=user_id,
            prompt=prompt,
            result=result,
            context_text=context_text,
            document_count=len(selected_document_version_ids),
            selected_document_version_ids=selected_document_version_ids,
            source_documents=source_documents,
        )
        self.session.add(analysis_run)
        self.session.commit()
        self.session.refresh(analysis_run)
        return analysis_run

    def list_analysis_runs(self, *, user_id: int, limit: int = 20) -> list[AnalysisRun]:
        statement = (
            select(AnalysisRun)
            .where(AnalysisRun.user_id == user_id)
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

    def get_analysis_run(self, *, user_id: int, analysis_run_id: int) -> AnalysisRun | None:
        statement = select(AnalysisRun).where(
            AnalysisRun.id == analysis_run_id,
            AnalysisRun.user_id == user_id,
        )
        return self.session.scalar(statement)

    def delete_analysis_run(self, *, user_id: int, analysis_run_id: int) -> bool:
        analysis_run = self.get_analysis_run(user_id=user_id, analysis_run_id=analysis_run_id)
        if analysis_run is None:
            return False
        self.session.delete(analysis_run)
        self.session.commit()
        return True
