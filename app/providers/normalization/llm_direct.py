from __future__ import annotations

import json
import re
from collections.abc import Iterable

import httpx

from app.providers.base import NormalizationProvider, NormalizationResult, ProviderConfig
from app.providers.errors import ProviderError, ProviderExternalServiceError, ProviderNonRetryableError
from app.providers.normalization.rule_based import RuleBasedNormalizationProvider
from app.services.document_semantics import (
    NARRATIVE_CONTEXT,
    STRUCTURED_METRICS,
    category_capabilities,
    extract_report_date,
    infer_document_category,
)


class LLMDirectNormalizationProvider(NormalizationProvider):
    """Extract structured measurements directly from OCR text with an LLM."""

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(
            config
            or ProviderConfig(
                provider_type="normalization",
                name="llm_direct",
            )
        )

    def normalize(self, raw_text: str) -> NormalizationResult:
        rule_based_result = self._rule_based_baseline(raw_text)
        prompt = self._build_extraction_prompt(raw_text)
        try:
            llm_response = self._call_llm(prompt)
        except ProviderError as exc:
            return self._fallback_result(rule_based_result, exc)

        parsed_payload = None
        measurements: list[dict]
        try:
            parsed_payload = json.loads(llm_response)
            measurements = self._sanitize_measurements(parsed_payload.get("measurements", []))
        except json.JSONDecodeError:
            measurements = self._sanitize_measurements(self._try_fix_json(llm_response))

        if not isinstance(parsed_payload, dict) and not measurements:
            return self._fallback_result(
                rule_based_result,
                ProviderNonRetryableError(
                    provider_type="normalization",
                    provider_name=self.config.name,
                    code="invalid_json_response",
                    message="LLM normalization response was not valid JSON",
                ),
            )

        measurements = self._merge_measurements(rule_based_result.measurements, measurements)
        prose_facts = self._sanitize_prose_facts((parsed_payload or {}).get("prose_facts", []))
        if not prose_facts:
            prose_facts = list(rule_based_result.normalized_payload.get("prose_facts", []))

        report_date = extract_report_date(raw_text, parsed_payload)
        if report_date is None:
            report_date = rule_based_result.report_date
        document_category = infer_document_category(
            raw_text=raw_text,
            measurements=measurements,
            document_type=None,
            normalized_payload=parsed_payload or {},
        )
        if self._should_promote_to_structured_metrics(raw_text, measurements):
            document_category = STRUCTURED_METRICS
        document_type = "lab_report" if document_category == STRUCTURED_METRICS else "clinical_note"
        if document_category == NARRATIVE_CONTEXT:
            measurements = []
        capabilities = category_capabilities(document_category)
        normalized_payload = self._build_normalized_payload(
            raw_text=raw_text,
            parsed_payload=parsed_payload,
            report_date=report_date,
            document_category=document_category,
            measurements=measurements,
            prose_facts=prose_facts,
            llm_response=llm_response,
            rule_based_result=rule_based_result,
        )

        return NormalizationResult(
            provider_name=self.config.name,
            document_type=document_type,
            document_category=document_category,
            report_date=report_date,
            supports_measurements=capabilities["supports_measurements"],
            supports_trend_analysis=capabilities["supports_trend_analysis"],
            supports_llm_context=capabilities["supports_llm_context"],
            normalized_payload=normalized_payload,
            measurements=measurements,
        )

    def _build_extraction_prompt(self, raw_text: str) -> str:
        return f"""从下面 OCR 文本中提取完整的标准化信息，返回 JSON。

Return valid JSON only, with this schema:
{{
  "document_summary": "用原文语言概括文档重点",
  "report_date": "2026-04-03",
  "measurements": [
    {{
      "name": "空腹血糖",
      "canonical_name": "glucose",
      "value_numeric": 5.2,
      "value_text": "5.2 mmol/L",
      "unit": "mmol/L",
      "reference_range": "3.9-6.1"
    }}
  ],
  "prose_facts": [
    {{
      "fact_type": "complaint/diagnosis/history/recommendation/observation/status",
      "display_text": "头晕3天",
      "matched_text": "患者诉头晕3天",
      "attributes": {{}}
    }}
  ]
}}

Rules:
- Include every measurement you can confidently identify.
- Preserve important non-measurement clinical facts in `prose_facts`, especially symptoms, diagnoses, treatments, follow-up advice, and status statements.
- `document_summary` should be a concise summary in the source language.
- `name` must preserve the original metric label from OCR text exactly. Do not translate Chinese to English and do not rewrite English to Chinese.
- `canonical_name` is optional. Use a stable English alias only when it is obvious; otherwise use null.
- Preserve the source wording and script in `value_text`, `unit`, and `reference_range`.
- Preserve the source wording and script in `display_text` and `matched_text`.
- Use null when a numeric value or unit is unavailable.
- Prefer the original source language for all string fields taken from OCR text.
- Do not include any prose outside the JSON object.

OCR text:
{raw_text}
"""

    def _call_llm(self, prompt: str) -> str:
        base_url = self.config.base_url or "https://api.openai.com/v1"
        api_key = self.config.api_key or ""
        model = self.config.model or "gpt-4o-mini"

        if not api_key:
            raise ProviderNonRetryableError(
                provider_type="normalization",
                provider_name=self.config.name,
                code="missing_api_key",
                message="LLM API key not configured",
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            return self._call_chat_completions_api(base_url, model, prompt, headers)
        except ProviderNonRetryableError as exc:
            if exc.code != "chat_completions_not_supported":
                raise
        return self._call_responses_api(base_url, model, prompt, headers)

    def _call_responses_api(self, base_url: str, model: str, prompt: str, headers: dict) -> str:
        payload = {
            "model": model,
            "instructions": self._system_instruction(),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
        }

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.post(
                    f"{base_url.rstrip('/')}/responses",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderExternalServiceError(
                provider_type="normalization",
                provider_name=self.config.name,
                code="llm_timeout",
                message="LLM request timed out",
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._raise_status_error(exc, endpoint="/responses", unsupported_code="responses_not_supported")
        except httpx.HTTPError as exc:
            raise ProviderExternalServiceError(
                provider_type="normalization",
                provider_name=self.config.name,
                code="llm_request_failed",
                message=f"LLM request failed: {exc}",
                retryable=True,
            ) from exc

        body = response.json()
        output_text = body.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = body.get("output", [])
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text = content.get("text")
                    if isinstance(text, str) and text.strip():
                        return text

        raise ProviderNonRetryableError(
            provider_type="normalization",
            provider_name=self.config.name,
            code="invalid_response_format",
            message="Could not extract text from /responses API",
        )

    def _call_chat_completions_api(self, base_url: str, model: str, prompt: str, headers: dict) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self._system_instruction()},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }

        if "gpt" in model.lower() or "o1" in model.lower():
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderExternalServiceError(
                provider_type="normalization",
                provider_name=self.config.name,
                code="llm_timeout",
                message="LLM request timed out",
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._raise_status_error(exc, endpoint="/chat/completions", unsupported_code="chat_completions_not_supported")
        except httpx.HTTPError as exc:
            raise ProviderExternalServiceError(
                provider_type="normalization",
                provider_name=self.config.name,
                code="llm_request_failed",
                message=f"LLM request failed: {exc}",
                retryable=True,
            ) from exc

        body = response.json()
        choices = body.get("choices", [])
        if not choices:
            raise ProviderNonRetryableError(
                provider_type="normalization",
                provider_name=self.config.name,
                code="missing_choices",
                message="LLM gateway returned no completion choices",
            )

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, Iterable):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str) and item.strip():
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text)
            if parts:
                return "\n".join(parts)

        raise ProviderNonRetryableError(
            provider_type="normalization",
            provider_name=self.config.name,
            code="invalid_response_format",
            message="Could not extract text from /chat/completions API",
        )

    def _raise_status_error(self, exc: httpx.HTTPStatusError, *, endpoint: str, unsupported_code: str) -> None:
        message = self._extract_error_message(exc.response)
        status_code = exc.response.status_code

        if status_code == 404 or self._looks_like_missing_endpoint(message, endpoint):
            raise ProviderNonRetryableError(
                provider_type="normalization",
                provider_name=self.config.name,
                code=unsupported_code,
                message=message or f"{endpoint} endpoint not found",
            ) from exc
        if status_code in {401, 403}:
            raise ProviderNonRetryableError(
                provider_type="normalization",
                provider_name=self.config.name,
                code="authentication_failed",
                message=message or "LLM authentication failed",
            ) from exc
        if status_code < 500 and status_code not in {408, 429}:
            raise ProviderNonRetryableError(
                provider_type="normalization",
                provider_name=self.config.name,
                code="llm_request_rejected",
                message=message or f"LLM request rejected with status {status_code}",
                details={"status_code": status_code},
            ) from exc
        raise ProviderExternalServiceError(
            provider_type="normalization",
            provider_name=self.config.name,
            code="llm_request_failed",
            message=f"LLM request failed: {message or exc}",
            retryable=True,
        ) from exc

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except json.JSONDecodeError:
            return response.text[:500].strip()

        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

        message = body.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        return response.text[:500].strip()

    def _looks_like_missing_endpoint(self, message: str, endpoint: str) -> bool:
        normalized = (message or "").lower()
        endpoint_name = endpoint.rsplit("/", maxsplit=1)[-1].lower()
        if "no matched path found" in normalized:
            return True
        if "unsupported legacy protocol" in normalized and endpoint.lower() in normalized:
            return True
        if "not found" in normalized and endpoint_name in normalized:
            return True
        if "does not exist" in normalized and endpoint_name in normalized:
            return True
        return False

    def _system_instruction(self) -> str:
        return (
            "You extract structured clinical measurements and must return valid JSON only. "
            "Preserve source-language metric labels and never translate OCR content."
        )

    def _sanitize_measurements(self, raw_measurements: object) -> list[dict]:
        if not isinstance(raw_measurements, list):
            return []

        sanitized: list[dict] = []
        for item in raw_measurements:
            if not isinstance(item, dict):
                continue
            name = self._clean_optional_text(item.get("name"))
            source_name = self._clean_optional_text(item.get("source_name")) or name
            canonical_name = self._clean_optional_text(item.get("canonical_name"))
            value_text = self._clean_optional_text(item.get("value_text"))
            value_numeric = self._coerce_float(item.get("value_numeric"))
            unit = self._clean_optional_text(item.get("unit"))
            reference_range = self._clean_optional_text(item.get("reference_range"))

            if not name and source_name:
                name = source_name
            if not name:
                continue
            if not value_text:
                value_text = str(value_numeric) if value_numeric is not None else ""
                if unit:
                    value_text = f"{value_text} {unit}".strip()
            if not value_text:
                continue

            sanitized.append(
                {
                    "name": name,
                    "source_name": source_name or name,
                    "canonical_name": canonical_name,
                    "value_numeric": value_numeric,
                    "value_text": value_text,
                    "unit": unit,
                    "reference_range": reference_range,
                    "parser": "llm_direct",
                }
            )
        return sanitized

    def _sanitize_prose_facts(self, raw_facts: object) -> list[dict]:
        if not isinstance(raw_facts, list):
            return []

        sanitized: list[dict] = []
        for item in raw_facts:
            if not isinstance(item, dict):
                continue
            fact_type = self._clean_optional_text(item.get("fact_type")) or "note"
            display_text = self._clean_optional_text(item.get("display_text"))
            matched_text = self._clean_optional_text(item.get("matched_text"))
            parser = self._clean_optional_text(item.get("parser")) or "llm_direct"
            attributes = item.get("attributes")
            if not isinstance(attributes, dict):
                attributes = {}
            if not display_text and not matched_text:
                continue
            sanitized.append(
                {
                    "fact_type": fact_type,
                    "display_text": display_text or matched_text,
                    "matched_text": matched_text or display_text,
                    "attributes": attributes,
                    "parser": parser,
                }
            )
        return sanitized

    def _build_normalized_payload(
        self,
        *,
        raw_text: str,
        parsed_payload: dict | None,
        report_date,
        document_category: str,
        measurements: list[dict],
        prose_facts: list[dict],
        llm_response: str,
        rule_based_result: NormalizationResult,
    ) -> dict:
        payload = dict(parsed_payload) if isinstance(parsed_payload, dict) else {}
        payload["raw_text"] = raw_text
        payload["report_date"] = report_date.isoformat() if report_date else None
        payload["document_category"] = document_category
        payload["measurement_count"] = len(measurements)
        payload["prose_fact_count"] = len(prose_facts)
        payload["measurements"] = measurements
        if prose_facts or "prose_facts" in payload:
            payload["prose_facts"] = prose_facts
        payload["extraction_method"] = "llm_direct_hybrid"
        payload["source_language_preserved"] = True
        payload["rule_based_candidate_measurement_count"] = len(rule_based_result.measurements)
        payload["llm_response"] = llm_response[:500]
        return payload

    def _rule_based_baseline(self, raw_text: str) -> NormalizationResult:
        return RuleBasedNormalizationProvider().normalize(raw_text)

    def _fallback_result(self, rule_based_result: NormalizationResult, exc: ProviderError) -> NormalizationResult:
        payload = dict(rule_based_result.normalized_payload)
        payload["extraction_method"] = "rule_based_fallback"
        payload["source_provider"] = self.config.name
        payload["fallback_reason"] = {
            "category": exc.category,
            "code": exc.code,
            "message": exc.message[:300],
            "retryable": exc.retryable,
        }
        return NormalizationResult(
            provider_name=f"{self.config.name}+rule_based_fallback",
            document_type=rule_based_result.document_type,
            document_category=rule_based_result.document_category,
            report_date=rule_based_result.report_date,
            supports_measurements=rule_based_result.supports_measurements,
            supports_trend_analysis=rule_based_result.supports_trend_analysis,
            supports_llm_context=rule_based_result.supports_llm_context,
            normalized_payload=payload,
            measurements=rule_based_result.measurements,
        )

    def _merge_measurements(self, rule_based_measurements: list[dict], llm_measurements: list[dict]) -> list[dict]:
        merged: list[dict] = []
        seen: set[tuple[str, str, str | None]] = set()
        for item in [*rule_based_measurements, *llm_measurements]:
            key = (
                str(item.get("name") or "").strip().lower(),
                str(item.get("value_text") or "").strip().lower(),
                item.get("unit"),
            )
            if not key[0] or not key[1] or key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    def _should_promote_to_structured_metrics(self, raw_text: str, measurements: list[dict]) -> bool:
        if not measurements:
            return False

        reliable_measurements = [
            item
            for item in measurements
            if (
                item.get("value_numeric") is not None
                or str(item.get("value_text") or "").strip()
            )
            and (
                str(item.get("unit") or "").strip()
                or str(item.get("reference_range") or "").strip()
            )
        ]
        if not reliable_measurements:
            return False

        compact_line_count = len([line for line in raw_text.splitlines() if line.strip()])
        looks_like_lab_row = (
            "=" in raw_text
            or compact_line_count <= max(3, len(reliable_measurements) * 2)
            or any(token in raw_text.lower() for token in ("wbc", "rbc", "hgb", "plt", "glucose", "ast", "alt"))
        )
        return looks_like_lab_row

    def _clean_optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _coerce_float(self, value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _try_fix_json(self, llm_response: str) -> list[dict]:
        json_match = re.search(r"\{.*\}", llm_response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return data.get("measurements", [])
            except Exception:
                pass
        return []
