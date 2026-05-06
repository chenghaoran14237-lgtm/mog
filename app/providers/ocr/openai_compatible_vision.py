from __future__ import annotations

import base64
from collections.abc import Iterable
import json

import httpx

from app.providers.base import OCRExtractionResult, OCRProvider, ProviderConfig
from app.providers.errors import (
    ProviderConfigurationError,
    ProviderExternalServiceError,
    ProviderNonRetryableError,
)
from app.providers.ocr.block_structure import OCRBlock, OCRBlockPayload


SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg"}
SUPPORTED_INPUT_TYPES = SUPPORTED_IMAGE_TYPES | {"application/pdf"}


class OpenAICompatibleVisionOCRProvider(OCRProvider):
    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)

    def extract(self, file_bytes: bytes, content_type: str | None = None) -> OCRExtractionResult:
        normalized_content_type = (content_type or "").lower().strip()
        self._validate_config()
        if normalized_content_type not in SUPPORTED_INPUT_TYPES:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="unsupported_input_type",
                message=f"Unsupported OCR input type '{content_type}'. Supported: image/png, image/jpeg, application/pdf",
            )

        available_models = self._fetch_model_ids()
        if self.config.model not in available_models:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="ocr_model_not_available",
                message=f"OCR model '{self.config.model}' is not exposed by the configured gateway",
                details={"available_models": available_models[:20]},
            )

        chat_payload = self._build_chat_completion_payload(
            file_bytes=file_bytes,
            content_type=normalized_content_type,
        )
        response_body, protocol = self._request_ocr_completion(chat_payload, file_bytes=file_bytes, content_type=normalized_content_type)
        extracted_text = self._extract_text(response_body, protocol=protocol)
        if not extracted_text.strip():
            raise ProviderNonRetryableError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="empty_ocr_output",
                message="OCR provider returned an empty extraction result",
            )

        return OCRExtractionResult(
            provider_name=self.config.name,
            raw_text=extracted_text.strip(),
            raw_payload={
                "model": self.config.model,
                "content_type": normalized_content_type,
                "protocol": protocol,
                "response_id": response_body.get("id"),
                "finish_reason": self._extract_finish_reason(response_body, protocol=protocol),
                "usage": response_body.get("usage", {}),
            },
            block_payload=self._build_block_payload(extracted_text.strip()),
        )

    def _build_block_payload(self, raw_text: str, page_count: int = 1) -> OCRBlockPayload:
        blocks: list[OCRBlock] = []
        lines = raw_text.split("\n")

        for idx, line in enumerate(lines):
            if not line.strip():
                continue

            blocks.append(
                OCRBlock(
                    block_id=f"page_0_line_{idx}",
                    page_index=0,
                    reading_order=idx,
                    source_kind="line",
                    raw_text=line,
                    clean_text=line.strip(),
                    line_index_within_page=idx,
                )
            )

        return OCRBlockPayload(
            blocks=blocks,
            page_count=page_count,
            extraction_metadata={
                "provider": self.config.name,
                "model": self.config.model,
                "block_generation_strategy": "line_split",
            },
        )

    def _validate_config(self) -> None:
        if not self.config.base_url:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="missing_base_url",
                message="OCR gateway base URL is not configured",
            )
        if not self.config.api_key:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="missing_api_key",
                message="OCR gateway API key is not configured",
            )
        if not self.config.model:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="missing_model",
                message="OCR gateway model is not configured",
            )

    def _fetch_model_ids(self) -> list[str]:
        with self._build_client() as client:
            try:
                response = client.get("/models")
            except httpx.TimeoutException as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="gateway_timeout",
                    message="Timed out while probing OCR gateway capabilities",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="gateway_connection_failed",
                    message="Failed to reach OCR gateway capability endpoint",
                    retryable=True,
                ) from exc

        if response.status_code in {401, 403}:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="gateway_authentication_failed",
                message="OCR gateway authentication failed during capability probe",
            )
        if response.status_code >= 500:
            raise ProviderExternalServiceError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="gateway_capability_probe_failed",
                message="OCR gateway capability probe failed",
                retryable=True,
            )
        if response.status_code >= 400:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="gateway_capability_probe_rejected",
                message="OCR gateway rejected capability probe request",
                details={"status_code": response.status_code},
            )

        body = response.json()
        return [item.get("id", "") for item in body.get("data", []) if item.get("id")]

    def _build_chat_completion_payload(self, *, file_bytes: bytes, content_type: str) -> dict:
        instruction = (
            "Perform OCR on the provided document. "
            "Return only the extracted plaintext, preserving meaningful line breaks. "
            "Do not add commentary, markdown, or explanations."
        )
        if content_type in SUPPORTED_IMAGE_TYPES:
            encoded = base64.b64encode(file_bytes).decode("ascii")
            file_part = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{encoded}",
                },
            }
        elif content_type == "application/pdf":
            if self.config.options.get("enable_pdf_fallback"):
                raise ProviderConfigurationError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="pdf_fallback_unavailable",
                    message="OCR PDF fallback was enabled but no local PDF-to-image renderer is installed",
                )
            encoded = base64.b64encode(file_bytes).decode("ascii")
            file_part = {
                "type": "file",
                "file": {
                    "filename": "document.pdf",
                    "file_data": encoded,
                },
            }
        else:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="unsupported_input_type",
                message=f"Unsupported OCR input type '{content_type}'",
            )

        return {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": instruction,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all visible text from this file."},
                        file_part,
                    ],
                },
            ],
            "temperature": 0,
        }

    def _build_responses_payload(self, *, file_bytes: bytes, content_type: str) -> dict:
        instruction = (
            "Perform OCR on the provided document. "
            "Return only the extracted plaintext, preserving meaningful line breaks. "
            "Do not add commentary, markdown, or explanations."
        )
        if content_type in SUPPORTED_IMAGE_TYPES:
            encoded = base64.b64encode(file_bytes).decode("ascii")
            input_part = {
                "type": "input_image",
                "image_url": f"data:{content_type};base64,{encoded}",
            }
        elif content_type == "application/pdf":
            if self.config.options.get("enable_pdf_fallback"):
                raise ProviderConfigurationError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="pdf_fallback_unavailable",
                    message="OCR PDF fallback was enabled but no local PDF-to-image renderer is installed",
                )
            encoded = base64.b64encode(file_bytes).decode("ascii")
            input_part = {
                "type": "input_file",
                "filename": "document.pdf",
                "file_data": f"data:application/pdf;base64,{encoded}",
            }
        else:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="unsupported_input_type",
                message=f"Unsupported OCR input type '{content_type}'",
            )

        return {
            "model": self.config.model,
            "instructions": instruction,
            "input": [
                {
                    "role": "user",
                    "content": [
                        input_part,
                        {"type": "input_text", "text": "Extract all visible text from this file."},
                    ],
                }
            ],
        }

    def _request_ocr_completion(self, chat_payload: dict, *, file_bytes: bytes, content_type: str) -> tuple[dict, str]:
        try:
            return self._send_chat_completion(chat_payload, content_type), "chat_completions"
        except ProviderConfigurationError as exc:
            if exc.code != "chat_completions_not_supported":
                raise
        responses_payload = self._build_responses_payload(file_bytes=file_bytes, content_type=content_type)
        return self._send_responses_completion(responses_payload, content_type), "responses"

    def _send_chat_completion(self, payload: dict, content_type: str) -> dict:
        with self._build_client() as client:
            try:
                response = client.post("/chat/completions", json=payload)
            except httpx.TimeoutException as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="gateway_timeout",
                    message="Timed out while waiting for OCR gateway response",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="gateway_connection_failed",
                    message="Failed to reach OCR gateway",
                    retryable=True,
                ) from exc

        if response.status_code in {401, 403}:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="gateway_authentication_failed",
                message="OCR gateway authentication failed",
            )
        if response.status_code == 404:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="chat_completions_not_supported",
                message="OCR gateway does not expose a compatible /chat/completions endpoint",
            )
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise ProviderExternalServiceError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="gateway_request_failed",
                message="OCR gateway request failed",
                retryable=True,
                details={"status_code": response.status_code},
            )
        if response.status_code >= 400:
            raise self._map_capability_error(response, content_type)

        return response.json()

    def _send_responses_completion(self, payload: dict, content_type: str) -> dict:
        with self._build_client() as client:
            try:
                response = client.post("/responses", json=payload)
            except httpx.TimeoutException as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="gateway_timeout",
                    message="Timed out while waiting for OCR gateway response",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderExternalServiceError(
                    provider_type="ocr",
                    provider_name=self.config.name,
                    code="gateway_connection_failed",
                    message="Failed to reach OCR gateway",
                    retryable=True,
                ) from exc

        if response.status_code in {401, 403}:
            raise ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="gateway_authentication_failed",
                message="OCR gateway authentication failed",
            )
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise ProviderExternalServiceError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="gateway_request_failed",
                message="OCR gateway request failed",
                retryable=True,
                details={"status_code": response.status_code},
            )
        if response.status_code >= 400:
            raise self._map_capability_error(response, content_type)

        return response.json()

    def _map_capability_error(self, response: httpx.Response, content_type: str) -> ProviderConfigurationError | ProviderNonRetryableError:
        message = self._extract_error_message(response)
        normalized = message.lower()
        if "unsupported legacy protocol" in normalized and "/v1/responses" in normalized:
            return ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="chat_completions_not_supported",
                message=message,
            )
        if "model" in normalized and ("not found" in normalized or "does not exist" in normalized or "unknown" in normalized):
            return ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="ocr_model_not_available",
                message=message,
            )
        if content_type in SUPPORTED_IMAGE_TYPES and any(token in normalized for token in ["image_url", "vision", "multimodal", "image input", "content type image"]):
            return ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="vision_input_not_supported",
                message=message,
            )
        if content_type == "application/pdf" and any(token in normalized for token in ["file", "pdf", "document", "unsupported", "not support"]):
            return ProviderConfigurationError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="pdf_input_not_supported",
                message=message,
            )
        return ProviderNonRetryableError(
            provider_type="ocr",
            provider_name=self.config.name,
            code="gateway_rejected_request",
            message=message,
            details={"status_code": response.status_code},
        )

    def _extract_text(self, body: dict, *, protocol: str) -> str:
        if protocol == "responses":
            output_text = body.get("output_text")
            if isinstance(output_text, str) and output_text.strip():
                return output_text
            output = body.get("output", [])
            parts: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "message":
                    continue
                for content_item in item.get("content", []):
                    if isinstance(content_item, dict) and content_item.get("type") == "output_text":
                        text = content_item.get("text")
                        if isinstance(text, str) and text.strip():
                            parts.append(text)
            if parts:
                return "\n".join(parts)
            raise ProviderNonRetryableError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="unsupported_completion_shape",
                message="OCR gateway returned an unsupported responses payload shape",
                details={"body": self._safe_body_preview(body)},
            )

        choices = body.get("choices", [])
        if not choices:
            raise ProviderNonRetryableError(
                provider_type="ocr",
                provider_name=self.config.name,
                code="missing_choices",
                message="OCR gateway returned no completion choices",
            )

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, Iterable):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if item.get("type") == "text" and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif isinstance(item.get("content"), str):
                        parts.append(item["content"])
            if parts:
                return "\n".join(part.strip() for part in parts if part and part.strip())

        raise ProviderNonRetryableError(
            provider_type="ocr",
            provider_name=self.config.name,
            code="unsupported_completion_shape",
            message="OCR gateway returned an unsupported completion payload shape",
            details={"body": self._safe_body_preview(body)},
        )

    def _extract_finish_reason(self, body: dict, *, protocol: str) -> str | None:
        if protocol == "responses":
            return body.get("status")
        choices = body.get("choices", [])
        if not choices:
            return None
        return choices[0].get("finish_reason")

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return response.text[:500] or "OCR gateway returned an unexpected error"
        error = payload.get("error", {})
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return response.text[:500] or "OCR gateway returned an unexpected error"

    def _safe_body_preview(self, body: dict) -> dict:
        preview = dict(body)
        if "choices" in preview:
            preview["choices"] = "<omitted>"
        return preview

    def _build_client(self) -> httpx.Client:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        return httpx.Client(
            base_url=self.config.base_url.rstrip("/"),
            headers=headers,
            timeout=self.config.timeout_seconds,
        )
