import pytest
from fastapi import HTTPException

from app.api.v1 import chat
from app.models.user import User
from app.providers.errors import ProviderExternalServiceError
from app.providers.normalization.llm_direct import LLMDirectNormalizationProvider
from app.repositories.task_repository import TaskRepository


class FailingConversationService:
    def send_message(self, **_kwargs):
        raise ProviderExternalServiceError(
            provider_type="llm",
            provider_name="openai_compatible",
            code="gateway_unavailable",
            message="LLM gateway unavailable",
            retryable=True,
        )


def test_chat_message_provider_error_returns_503():
    with pytest.raises(HTTPException) as exc_info:
        chat.send_message(
            conversation_id=1,
            data=chat.MessageCreate(message="hello", context_document_ids=[]),
            current_user=User(id=1, email="demo@example.com", password_hash="x"),
            conversation_service=FailingConversationService(),
        )

    assert exc_info.value.status_code == 503
    assert "AI" in str(exc_info.value.detail)


def test_task_error_messages_are_truncated_for_mysql_string_columns():
    long_message = "x" * 800

    assert len(TaskRepository._safe_message(long_message)) <= 255
    assert TaskRepository._safe_message(None) is None


def test_llm_direct_normalization_falls_back_to_rule_based_when_gateway_fails(monkeypatch):
    provider = LLMDirectNormalizationProvider()

    def fail_call(_prompt):
        raise ProviderExternalServiceError(
            provider_type="normalization",
            provider_name="llm_direct",
            code="llm_request_failed",
            message="LLM request failed",
            retryable=True,
        )

    monkeypatch.setattr(provider, "_call_llm", fail_call)

    result = provider.normalize("Lab Report\nGlucose 5.6 mmol/L 3.9-6.1\nALT 32 U/L 0-40")

    assert result.document_category == "structured_metrics"
    assert result.measurements
    assert result.normalized_payload["extraction_method"] == "rule_based_fallback"
    assert result.normalized_payload["fallback_reason"]["code"] == "llm_request_failed"
