import pytest
from fastapi import HTTPException

from app.api.v1 import chat
from app.models.user import User
from app.providers.base import OCRExtractionResult, ProviderConfig
from app.providers.errors import ProviderExternalServiceError
from app.providers.normalization.llm_direct import LLMDirectNormalizationProvider
from app.providers.ocr.auto import AutoRoutingOCRProvider
from app.providers.ocr.baidu_ocr import BaiduOCRProvider
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


def test_auto_ocr_routes_octet_stream_text_to_plaintext():
    provider = AutoRoutingOCRProvider(ProviderConfig(provider_type="ocr", name="auto"))

    result = provider.extract("空腹血糖 6.8 mmol/L".encode("utf-8"), content_type="application/octet-stream")

    assert result.provider_name == "plaintext"
    assert result.raw_text == "空腹血糖 6.8 mmol/L"
    assert result.raw_payload["auto_router"]["selected_provider"] == "plaintext"


def test_auto_ocr_routes_images_to_baidu(monkeypatch):
    provider = AutoRoutingOCRProvider(
        ProviderConfig(
            provider_type="ocr",
            name="auto",
            base_url="https://aip.baidubce.com",
            variant="accurate",
            api_key="key",
            secret_ref="secret",
        )
    )

    def fake_extract(self, file_bytes, content_type=None):
        return OCRExtractionResult(provider_name="baidu_ocr", raw_text="体检中心检验报告", raw_payload={"variant": self.config.variant})

    monkeypatch.setattr(BaiduOCRProvider, "extract", fake_extract)

    result = provider.extract(b"image-bytes", content_type="image/png")

    assert result.provider_name == "baidu_ocr"
    assert result.raw_payload["variant"] == "accurate"
    assert result.raw_payload["auto_router"]["selected_provider"] == "baidu_ocr"
