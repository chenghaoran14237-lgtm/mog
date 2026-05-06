from __future__ import annotations

import base64
from urllib.parse import urlparse

import httpx

from app.providers.base import OCRExtractionResult, OCRProvider, ProviderConfig
from app.providers.errors import (
    ProviderConfigurationError,
    ProviderExternalServiceError,
    ProviderNonRetryableError,
)
from app.providers.ocr.block_structure import OCRBlock, OCRBlockPayload


SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/bmp", "image/webp"}
DEFAULT_BASE_URL = "https://aip.baidubce.com"
DEFAULT_VARIANT = "accurate_basic"
SUPPORTED_VARIANTS = {
    "general_basic": "/rest/2.0/ocr/v1/general_basic",
    "general": "/rest/2.0/ocr/v1/general",
    "accurate_basic": "/rest/2.0/ocr/v1/accurate_basic",
    "accurate": "/rest/2.0/ocr/v1/accurate",
}


class BaiduOCRProvider(OCRProvider):
    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)

    def extract(self, file_bytes: bytes, content_type: str | None = None) -> OCRExtractionResult:
        normalized_content_type = (content_type or "").lower().strip()
        if normalized_content_type not in SUPPORTED_IMAGE_TYPES:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="unsupported_input_type",
                message=(
                    f"Baidu OCR only supports image inputs. Received '{content_type}'. "
                    "Supported: image/png, image/jpeg, image/jpg, image/bmp, image/webp"
                ),
            )

        access_token = self._get_access_token()
        response_body = self._request_ocr(access_token=access_token, file_bytes=file_bytes)
        words_result = response_body.get("words_result") or []
        extracted_lines = [
            item.get("words", "").strip()
            for item in words_result
            if isinstance(item, dict) and item.get("words", "").strip()
        ]
        extracted_text = "\n".join(extracted_lines).strip()
        if not extracted_text:
            raise ProviderNonRetryableError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="empty_ocr_output",
                message="Baidu OCR returned an empty extraction result",
            )

        return OCRExtractionResult(
            provider_name=self.config.name,
            raw_text=extracted_text,
            raw_payload={
                "variant": self._resolve_variant(),
                "content_type": normalized_content_type,
                "log_id": response_body.get("log_id"),
                "direction": response_body.get("direction"),
                "words_result_num": response_body.get("words_result_num", len(extracted_lines)),
            },
            block_payload=self._build_block_payload(words_result),
        )

    def _get_access_token(self) -> str:
        api_key = (self.config.api_key or "").strip()
        secret_key = (self.config.secret_ref or "").strip()
        self._validate_base_url()
        if not api_key:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="missing_api_key",
                message="Baidu OCR API key is not configured",
            )
        if not secret_key:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="missing_secret_key",
                message="Baidu OCR secret key is not configured",
            )

        with self._build_client() as client:
            try:
                response = client.post(
                    "/oauth/2.0/token",
                    params={
                        "grant_type": "client_credentials",
                        "client_id": api_key,
                        "client_secret": secret_key,
                    },
                )
            except httpx.TimeoutException as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="token_timeout",
                    message="Timed out while requesting Baidu OCR access token",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="token_connection_failed",
                    message="Failed to reach Baidu OCR token endpoint",
                    retryable=True,
                ) from exc

        if response.status_code >= 400:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="token_request_failed",
                message=f"Baidu OCR token request failed: {response.text[:200]}",
                details={"status_code": response.status_code},
            )

        body = response.json()
        access_token = body.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="missing_access_token",
                message="Baidu OCR token response did not contain a valid access_token",
                details={"response": body},
            )
        return access_token

    def _request_ocr(self, *, access_token: str, file_bytes: bytes) -> dict:
        image_base64 = base64.b64encode(file_bytes).decode("ascii")
        endpoint = SUPPORTED_VARIANTS[self._resolve_variant()]
        payload = {
            "image": image_base64,
            "detect_direction": "true",
            "paragraph": "false",
            "probability": "false",
        }

        with self._build_client() as client:
            try:
                response = client.post(
                    endpoint,
                    params={"access_token": access_token},
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except httpx.TimeoutException as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="ocr_timeout",
                    message="Timed out while waiting for Baidu OCR response",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="ocr_connection_failed",
                    message="Failed to reach Baidu OCR service",
                    retryable=True,
                ) from exc

        if response.status_code >= 500:
            raise ProviderExternalServiceError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="ocr_http_error",
                message=f"Baidu OCR service error: {response.text[:200]}",
                retryable=True,
                details={"status_code": response.status_code},
            )
        if response.status_code >= 400:
            raise ProviderNonRetryableError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="ocr_http_error",
                message=f"Baidu OCR request rejected: {response.text[:200]}",
                details={"status_code": response.status_code},
            )

        body = response.json()
        if "error_code" in body:
            error_code = str(body.get("error_code"))
            message = str(body.get("error_msg") or "Baidu OCR returned an error")
            if error_code in {"18", "19", "282000", "282103"}:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code=f"baidu_{error_code}",
                    message=message,
                    retryable=True,
                    details={"body": body},
                )
            raise ProviderNonRetryableError(
                provider_type="ocr",
                provider_name=self.config.name,
                code=f"baidu_{error_code}",
                message=message,
                details={"body": body},
            )
        return body

    def _resolve_variant(self) -> str:
        variant = (self.config.variant or self.config.model or DEFAULT_VARIANT).strip().lower()
        if variant not in SUPPORTED_VARIANTS:
            supported = ", ".join(sorted(SUPPORTED_VARIANTS))
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="unsupported_variant",
                message=f"Unsupported Baidu OCR variant '{variant}'. Available: {supported}",
            )
        return variant

    def _build_block_payload(self, words_result: list[dict]) -> OCRBlockPayload:
        blocks: list[OCRBlock] = []
        for index, item in enumerate(words_result):
            if not isinstance(item, dict):
                continue
            words = str(item.get("words") or "").strip()
            if not words:
                continue
            blocks.append(
                OCRBlock(
                    block_id=f"page_0_line_{index}",
                    page_index=0,
                    reading_order=index,
                    source_kind="line",
                    raw_text=words,
                    clean_text=words,
                    line_index_within_page=index,
                )
            )
        return OCRBlockPayload(
            blocks=blocks,
            page_count=1,
            extraction_metadata={
                "provider": self.config.name,
                "variant": self._resolve_variant(),
                "block_generation_strategy": "words_result_lines",
            },
        )

    def _validate_base_url(self) -> None:
        base_url = (self.config.base_url or DEFAULT_BASE_URL).strip()
        parsed = urlparse(base_url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="invalid_base_url",
                message="Baidu OCR base URL is invalid",
            )
        if "baidubce.com" not in hostname:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="invalid_base_url",
                message=(
                    f"Baidu OCR must use a Baidu endpoint, but OCR_BASE_URL is '{base_url}'. "
                    "Use 'https://aip.baidubce.com' or leave OCR_BASE_URL empty."
                ),
            )

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=(self.config.base_url or DEFAULT_BASE_URL).rstrip("/"),
            timeout=self.config.timeout_seconds,
        )
