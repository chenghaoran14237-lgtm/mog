from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator

from app.providers.ocr.block_structure import OCRBlockPayload


@dataclass(slots=True)
class ProviderConfig:
    provider_type: str
    name: str
    base_url: str | None = None
    model: str | None = None
    variant: str | None = None
    api_key: str | None = None
    secret_ref: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 0
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OCRExtractionResult:
    provider_name: str
    raw_text: str
    raw_payload: dict[str, Any]
    # Optional enhancement. Providers that can expose block-level OCR structure
    # should populate this field; unsupported providers may leave it as None and
    # downstream consumers can continue using raw_text.
    block_payload: OCRBlockPayload | None = None


@dataclass(slots=True)
class NormalizationResult:
    provider_name: str
    document_type: str = "generic_record"
    document_category: str = "narrative_context"
    report_date: datetime | None = None
    supports_measurements: bool = False
    supports_trend_analysis: bool = False
    supports_llm_context: bool = True
    normalized_payload: dict[str, Any] = field(default_factory=dict)
    measurements: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class StorageWriteResult:
    provider_name: str
    storage_key: str | None
    content_bytes: bytes
    metadata: dict[str, Any]


class OCRProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def extract(self, file_bytes: bytes, content_type: str | None = None) -> OCRExtractionResult:
        """Extract OCR text, optionally enriched with block_payload."""
        raise NotImplementedError


class LLMProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def complete(self, prompt: str) -> dict[str, Any]:
        raise NotImplementedError

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """Chat completion with message history

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature

        Returns:
            Assistant response text
        """
        # Default implementation: convert messages to single prompt
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        result = self.complete(prompt)
        return result.get("result", "")

    def stream_chat(self, messages: list[dict], temperature: float = 0.7) -> Iterator[str]:
        """Stream chat completion chunks.

        Providers without native streaming support may override this fallback.
        """
        response = self.chat(messages=messages, temperature=temperature)
        if response:
            yield response


class NormalizationProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def normalize(self, raw_text: str) -> NormalizationResult:
        raise NotImplementedError


class StorageProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def store(
        self,
        *,
        content_bytes: bytes,
        content_type: str | None,
        original_filename: str,
    ) -> StorageWriteResult:
        raise NotImplementedError
