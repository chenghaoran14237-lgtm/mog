import json
from typing import Any, Iterator

import httpx

from app.providers.base import LLMProvider, ProviderConfig
from app.providers.errors import ProviderError


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        if not config.base_url:
            raise ValueError("base_url is required for OpenAI-compatible LLM provider")
        if not config.model:
            raise ValueError("model is required for OpenAI-compatible LLM provider")
        if not config.api_key:
            raise ValueError("api_key is required for OpenAI-compatible LLM provider")

    def complete(self, prompt: str) -> dict[str, Any]:
        """Simple completion (converts to chat format internally)"""
        messages = [{"role": "user", "content": prompt}]
        response_text = self.chat(messages)
        return {"provider": self.config.name, "result": response_text}

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """Chat completion - tries chat/completions first, falls back to responses"""
        try:
            return self._send_chat_completion(messages, temperature)
        except ProviderError as e:
            if e.code in ["http_404", "chat_completions_not_supported"] or "legacy protocol" in e.message.lower():
                return self._send_responses_completion(messages, temperature)
            raise

    def stream_chat(self, messages: list[dict], temperature: float = 0.7) -> Iterator[str]:
        try:
            yield from self._stream_chat_completion(messages, temperature)
            return
        except ProviderError as e:
            if e.code in ["http_404", "chat_completions_not_supported"] or "legacy protocol" in e.message.lower():
                yield from self._stream_responses_completion(messages, temperature)
                return
            raise

    def _build_client(self) -> httpx.Client:
        """Build HTTP client with same config as OCR provider"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        return httpx.Client(
            base_url=self.config.base_url.rstrip("/"),
            headers=headers,
            timeout=self.config.timeout_seconds,
        )

    def _send_chat_completion(self, messages: list[dict], temperature: float) -> str:
        """Standard OpenAI /chat/completions endpoint"""
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }

        with self._build_client() as client:
            try:
                response = client.post("/chat/completions", json=payload)
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    provider_type="llm",
                    provider_name=self.config.name,
                    category="network_error",
                    code="gateway_timeout",
                    message="Timed out while waiting for LLM response",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    provider_type="llm",
                    provider_name=self.config.name,
                    category="network_error",
                    code="gateway_connection_failed",
                    message="Failed to reach LLM gateway",
                    retryable=True,
                ) from exc

        self._raise_for_status(response.status_code, response.text)

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ProviderError(
                provider_type="llm",
                provider_name=self.config.name,
                category="api_error",
                code="missing_choices",
                message="LLM gateway returned no completion choices",
                retryable=False,
            )

        return choices[0]["message"]["content"]

    def _send_responses_completion(self, messages: list[dict], temperature: float) -> str:
        """Alternative /responses endpoint"""
        # Convert messages to responses format
        instructions = ""
        input_messages = []

        for msg in messages:
            if msg["role"] == "system":
                instructions = msg["content"]
            else:
                input_messages.append({
                    "role": msg["role"],
                    "content": [{"type": "input_text", "text": msg["content"]}]
                })

        payload = {
            "model": self.config.model,
            "instructions": instructions,
            "input": input_messages,
        }

        with self._build_client() as client:
            try:
                response = client.post("/responses", json=payload)
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    provider_type="llm",
                    provider_name=self.config.name,
                    category="network_error",
                    code="gateway_timeout",
                    message="Timed out while waiting for LLM response",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    provider_type="llm",
                    provider_name=self.config.name,
                    category="network_error",
                    code="gateway_connection_failed",
                    message="Failed to reach LLM gateway",
                    retryable=True,
                ) from exc

        self._raise_for_status(response.status_code, response.text)

        data = response.json()

        # Extract text from responses format
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        # Try output array format
        output = data.get("output", [])
        parts = []
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

        raise ProviderError(
            provider_type="llm",
            provider_name=self.config.name,
            category="api_error",
            code="unsupported_response_format",
            message="LLM API returned unsupported response format",
            retryable=False,
        )

    def _stream_chat_completion(self, messages: list[dict], temperature: float) -> Iterator[str]:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        with self._build_client() as client:
            try:
                with client.stream("POST", "/chat/completions", json=payload) as response:
                    self._raise_for_status(response.status_code, "")
                    for line in response.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        if line.strip() == "[DONE]":
                            break
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        for choice in payload.get("choices", []):
                            delta = choice.get("delta", {})
                            content = delta.get("content")
                            if isinstance(content, str) and content:
                                yield content
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    provider_type="llm",
                    provider_name=self.config.name,
                    category="network_error",
                    code="gateway_timeout",
                    message="Timed out while waiting for LLM response stream",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    provider_type="llm",
                    provider_name=self.config.name,
                    category="network_error",
                    code="gateway_connection_failed",
                    message="Failed to reach LLM gateway stream",
                    retryable=True,
                ) from exc

    def _stream_responses_completion(self, messages: list[dict], temperature: float) -> Iterator[str]:
        instructions = ""
        input_messages = []

        for msg in messages:
            if msg["role"] == "system":
                instructions = msg["content"]
            else:
                input_messages.append({
                    "role": msg["role"],
                    "content": [{"type": "input_text", "text": msg["content"]}],
                })

        payload = {
            "model": self.config.model,
            "instructions": instructions,
            "input": input_messages,
            "stream": True,
        }

        with self._build_client() as client:
            try:
                with client.stream("POST", "/responses", json=payload) as response:
                    self._raise_for_status(response.status_code, "")
                    for line in response.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        if line.strip() == "[DONE]":
                            break
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if payload.get("type") == "response.output_text.delta":
                            delta = payload.get("delta")
                            if isinstance(delta, str) and delta:
                                yield delta
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    provider_type="llm",
                    provider_name=self.config.name,
                    category="network_error",
                    code="gateway_timeout",
                    message="Timed out while waiting for LLM response stream",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    provider_type="llm",
                    provider_name=self.config.name,
                    category="network_error",
                    code="gateway_connection_failed",
                    message="Failed to reach LLM gateway stream",
                    retryable=True,
                ) from exc

    def _raise_for_status(self, status_code: int, response_text: str) -> None:
        if status_code == 404:
            raise ProviderError(
                provider_type="llm",
                provider_name=self.config.name,
                category="api_error",
                code="chat_completions_not_supported",
                message="LLM gateway does not support requested endpoint",
                retryable=False,
            )
        if status_code in {401, 403}:
            raise ProviderError(
                provider_type="llm",
                provider_name=self.config.name,
                category="api_error",
                code="gateway_authentication_failed",
                message="LLM gateway authentication failed",
                retryable=False,
            )
        if status_code in {408, 429} or status_code >= 500:
            raise ProviderError(
                provider_type="llm",
                provider_name=self.config.name,
                category="api_error",
                code=f"http_{status_code}",
                message=f"LLM gateway request failed: {response_text[:200]}",
                retryable=True,
            )
        if status_code >= 400:
            raise ProviderError(
                provider_type="llm",
                provider_name=self.config.name,
                category="api_error",
                code=f"http_{status_code}",
                message=f"LLM API error: {response_text[:200]}",
                retryable=False,
            )
