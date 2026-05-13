from __future__ import annotations

from urllib.parse import urlparse

from app.providers.base import OCRExtractionResult, OCRProvider, ProviderConfig
from app.providers.errors import ProviderConfigurationError
from app.providers.ocr.baidu_ocr import BaiduOCRProvider, SUPPORTED_IMAGE_TYPES as BAIDU_IMAGE_TYPES
from app.providers.ocr.openai_compatible_vision import OpenAICompatibleVisionOCRProvider
from app.providers.ocr.plaintext import PlaintextOCRProvider


TEXT_CONTENT_TYPES = {
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/json",
    "application/xml",
}
PDF_CONTENT_TYPES = {"application/pdf"}


class AutoRoutingOCRProvider(OCRProvider):
    """Route OCR by content type while preserving the provider audit trail."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)

    def extract(self, file_bytes: bytes, content_type: str | None = None) -> OCRExtractionResult:
        normalized_content_type = (content_type or "application/octet-stream").split(";", maxsplit=1)[0].lower().strip()
        provider = self._select_provider(file_bytes=file_bytes, content_type=normalized_content_type)
        result = provider.extract(file_bytes=file_bytes, content_type=normalized_content_type)
        result.raw_payload = {
            **result.raw_payload,
            "auto_router": {
                "configured_provider": self.config.name,
                "selected_provider": result.provider_name,
                "content_type": normalized_content_type,
            },
        }
        return result

    def _select_provider(self, *, file_bytes: bytes, content_type: str) -> OCRProvider:
        if content_type in TEXT_CONTENT_TYPES or self._looks_like_text(file_bytes, content_type=content_type):
            return PlaintextOCRProvider(ProviderConfig(provider_type="ocr", name="plaintext"))

        if content_type in BAIDU_IMAGE_TYPES:
            return self._build_image_provider()

        if content_type in PDF_CONTENT_TYPES:
            return self._build_pdf_provider()

        raise ProviderConfigurationError(
            provider_type="ocr",
            provider_name=self.config.name,
            code="unsupported_input_type",
            message=(
                f"Unsupported OCR input type '{content_type}'. "
                "Supported: text/plain, image/png, image/jpeg, image/jpg, image/bmp, image/webp, application/pdf"
            ),
        )

    def _build_image_provider(self) -> OCRProvider:
        if self._is_baidu_configured():
            return BaiduOCRProvider(self._child_config("baidu_ocr"))
        if self._is_openai_vision_configured():
            return OpenAICompatibleVisionOCRProvider(self._child_config("openai_compatible_vision"))
        raise ProviderConfigurationError(
            provider_type="ocr",
            provider_name=self.config.name,
            code="image_ocr_not_configured",
            message="Image OCR requires Baidu OCR keys or an OpenAI-compatible vision OCR model",
        )

    def _build_pdf_provider(self) -> OCRProvider:
        if self._is_openai_vision_configured() and not self._is_baidu_configured():
            return OpenAICompatibleVisionOCRProvider(self._child_config("openai_compatible_vision"))
        raise ProviderConfigurationError(
            provider_type="ocr",
            provider_name=self.config.name,
            code="pdf_ocr_not_configured",
            message="PDF OCR requires OCR_BASE_URL, OCR_MODEL, and OCR_API_KEY for an OpenAI-compatible vision model",
        )

    def _child_config(self, name: str) -> ProviderConfig:
        return ProviderConfig(
            provider_type="ocr",
            name=name,
            base_url=self.config.base_url,
            model=self.config.model,
            variant=self.config.variant,
            api_key=self.config.api_key,
            secret_ref=self.config.secret_ref,
            timeout_seconds=self.config.timeout_seconds,
            max_retries=self.config.max_retries,
            options=dict(self.config.options or {}),
        )

    def _is_baidu_configured(self) -> bool:
        hostname = (urlparse(self.config.base_url or "").hostname or "").lower()
        return bool(self.config.secret_ref) or "baidubce.com" in hostname

    def _is_openai_vision_configured(self) -> bool:
        return bool(self.config.base_url and self.config.model and self.config.api_key)

    def _looks_like_text(self, file_bytes: bytes, *, content_type: str) -> bool:
        if content_type != "application/octet-stream":
            return False
        sample = file_bytes[:4096]
        if not sample:
            return False
        try:
            decoded = sample.decode("utf-8")
        except UnicodeDecodeError:
            return False
        if "\x00" in decoded:
            return False
        printable = sum(1 for char in decoded if char.isprintable() or char in "\r\n\t")
        return printable / max(1, len(decoded)) > 0.92
