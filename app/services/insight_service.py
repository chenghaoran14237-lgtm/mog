from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.insight_message import InsightMessage
from app.models.insight_session import InsightSession
from app.providers.base import LLMProvider
from app.repositories.document_version_repository import DocumentVersionRepository
from app.services.conversation_context_service import ConversationContextService


class InsightService:
    def __init__(
        self,
        session,
        *,
        llm_provider: LLMProvider,
        document_version_repo: DocumentVersionRepository,
        context_service: ConversationContextService,
    ) -> None:
        self.session = session
        self.llm_provider = llm_provider
        self.document_version_repo = document_version_repo
        self.context_service = context_service

    def create_session(
        self,
        *,
        user_id: int,
        selected_document_version_ids: list[int],
        prompt: str,
    ) -> tuple[InsightSession, InsightMessage]:
        valid_versions = [
            version
            for version_id in selected_document_version_ids
            if (version := self.document_version_repo.get_by_id(version_id, user_id=user_id)) is not None
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
        base_context_text = self.context_service.build_context_for_version_ids(
            user_id=user_id,
            selected_version_ids=valid_version_ids,
        )

        title = self._build_title(prompt)
        insight_session = InsightSession(
            user_id=user_id,
            title=title,
            base_context_text=base_context_text,
            selected_document_version_ids=valid_version_ids,
            source_documents=source_documents,
        )
        self.session.add(insight_session)
        self.session.flush()

        user_message = InsightMessage(
            session_id=insight_session.id,
            role="user",
            content=prompt,
        )
        self.session.add(user_message)
        self.session.commit()
        self.session.refresh(insight_session)
        self.session.refresh(user_message)
        return self.get_session(user_id=user_id, session_id=insight_session.id), user_message

    def list_sessions(self, *, user_id: int, limit: int = 20) -> list[InsightSession]:
        statement = (
            select(InsightSession)
            .where(InsightSession.user_id == user_id)
            .order_by(InsightSession.updated_at.desc(), InsightSession.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

    def get_session(self, *, user_id: int, session_id: int) -> InsightSession | None:
        statement = (
            select(InsightSession)
            .options(selectinload(InsightSession.messages))
            .where(InsightSession.id == session_id, InsightSession.user_id == user_id)
        )
        return self.session.scalar(statement)

    def list_messages(self, *, user_id: int, session_id: int) -> list[InsightMessage]:
        insight_session = self.get_session(user_id=user_id, session_id=session_id)
        if insight_session is None:
            return []
        return list(insight_session.messages)

    def append_user_message(
        self,
        *,
        user_id: int,
        session_id: int,
        content: str,
    ) -> tuple[InsightSession, InsightMessage]:
        insight_session = self.get_session(user_id=user_id, session_id=session_id)
        if insight_session is None:
            raise ValueError("Insight session not found")

        message = InsightMessage(
            session_id=session_id,
            role="user",
            content=content,
        )
        insight_session.updated_at = datetime.now(timezone.utc)
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        return self.get_session(user_id=user_id, session_id=session_id), message

    def append_assistant_message(
        self,
        *,
        user_id: int,
        session_id: int,
        content: str,
    ) -> InsightMessage:
        insight_session = self.get_session(user_id=user_id, session_id=session_id)
        if insight_session is None:
            raise ValueError("Insight session not found")

        message = InsightMessage(
            session_id=session_id,
            role="assistant",
            content=content,
        )
        insight_session.updated_at = datetime.now(timezone.utc)
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        return message

    def delete_session(self, *, user_id: int, session_id: int) -> bool:
        insight_session = self.get_session(user_id=user_id, session_id=session_id)
        if insight_session is None:
            return False
        self.session.delete(insight_session)
        self.session.commit()
        return True

    def build_llm_messages_for_session(self, *, insight_session: InsightSession) -> list[dict]:
        system_prompt = self._build_system_prompt(insight_session.base_context_text)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in insight_session.messages
        )
        return messages

    def _build_system_prompt(self, base_context_text: str) -> str:
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
8. 在多轮对话里，要承接之前已经说过的结论，避免每一轮都重新复述整份报告。

如果用户没有特别指定格式，请优先按下面结构回答：
一、核心判断
二、我最关心的风险点
三、接下来怎么做
四、哪些情况要尽快就医
五、我的依据
"""
        return f"{system_prompt}\n\n{base_context_text}\n"

    def _build_title(self, prompt: str) -> str:
        compact = " ".join(prompt.split()).strip()
        if not compact:
            return "新的智能洞察"
        return compact[:48]
