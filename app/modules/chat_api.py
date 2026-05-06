from __future__ import annotations

from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.providers.registry import ProviderRegistry
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.schemas.conversation import (
    ChatResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageListResponse,
    MessageResponse,
)
from app.services.conversation_context_service import ConversationContextService
from app.services.conversation_service import ConversationService


class ChatModuleAPI:
    """Module 6: Medical Chatbot API"""

    def __init__(self, *, conversation_service: ConversationService) -> None:
        self.conversation_service = conversation_service

    @classmethod
    def from_session(cls, session) -> "ChatModuleAPI":
        llm_provider = ProviderRegistry().build_llm_provider()
        document_version_repo = DocumentVersionRepository(session)
        measurement_repo = MeasurementRepository(session)
        context_service = ConversationContextService(document_version_repo, measurement_repo)
        conversation_service = ConversationService(session, llm_provider, context_service)
        return cls(conversation_service=conversation_service)

    def create_conversation(self, *, user_id: int, title: str) -> ConversationResponse:
        """创建新对话"""
        conversation = self.conversation_service.create_conversation(user_id=user_id, title=title)
        return ConversationResponse.model_validate(conversation)

    def list_conversations(self, *, user_id: int) -> ConversationListResponse:
        """列出所有对话"""
        conversations = self.conversation_service.list_conversations(user_id=user_id)
        return ConversationListResponse(
            conversations=[ConversationResponse.model_validate(c) for c in conversations]
        )

    def get_conversation(self, *, user_id: int, conversation_id: int) -> ConversationResponse | None:
        """获取对话详情"""
        conversation = self.conversation_service.get_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if conversation:
            return ConversationResponse.model_validate(conversation)
        return None

    def get_conversation_messages(
        self,
        *,
        user_id: int,
        conversation_id: int,
    ) -> MessageListResponse | None:
        """获取对话消息列表"""
        conversation = self.conversation_service.get_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if not conversation:
            return None

        return MessageListResponse(
            messages=[MessageResponse.model_validate(m) for m in conversation.messages]
        )

    def send_message(
        self,
        *,
        user_id: int,
        conversation_id: int,
        message: str,
        context_document_ids: list[int] | None = None,
    ) -> ChatResponse:
        """发送消息并获取回复"""
        assistant_message = self.conversation_service.send_message(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
            context_document_ids=context_document_ids or [],
        )

        # 获取用户消息
        conversation = self.conversation_service.get_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        user_message = conversation.messages[-2]

        return ChatResponse(
            user_message=MessageResponse.model_validate(user_message),
            assistant_message=MessageResponse.model_validate(assistant_message),
        )
