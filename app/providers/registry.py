from collections.abc import Mapping
from typing import Any

from app.core.config import Settings, get_settings
from app.providers.base import (
    LLMProvider,
    NormalizationProvider,
    OCRProvider,
    ProviderConfig,
    StorageProvider,
)
from app.providers.errors import ProviderConfigurationError
from app.providers.ocr.openai_compatible_vision import OpenAICompatibleVisionOCRProvider
from app.providers.ocr.baidu_ocr import BaiduOCRProvider
from app.providers.llm.stub import StubLLMProvider
from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider
from app.providers.normalization.rule_based import RuleBasedNormalizationProvider
from app.providers.normalization.llm_direct import LLMDirectNormalizationProvider
from app.providers.ocr.plaintext import PlaintextOCRProvider
from app.providers.ocr.stub import StubOCRProvider
from app.providers.storage.database_inline import DatabaseInlineStorageProvider


class ProviderRegistry:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._registries: dict[str, Mapping[str, type[Any]]] = {
            "ocr": {
                "stub": StubOCRProvider,
                "plaintext": PlaintextOCRProvider,
                "openai_compatible_vision": OpenAICompatibleVisionOCRProvider,
                "baidu_ocr": BaiduOCRProvider,
            },
            "normalization": {
                "rule_based": RuleBasedNormalizationProvider,
                "llm_direct": LLMDirectNormalizationProvider,
            },
            "storage": {
                "database_inline": DatabaseInlineStorageProvider,
            },
            "llm": {
                "stub": StubLLMProvider,
                "openai_compatible": OpenAICompatibleLLMProvider,
            },
        }

    def get_config(self, provider_type: str) -> ProviderConfig:
        matrix = self.settings.provider_matrix()
        profile = matrix.get(provider_type)
        if profile is None:
            raise ProviderConfigurationError(
                provider_type=provider_type,
                provider_name="unknown",
                code="provider_type_not_configured",
                message=f"Provider type '{provider_type}' is not configured",
            )
        return profile

    def build_ocr_provider(self) -> OCRProvider:
        return self._build("ocr")

    def build_normalization_provider(self) -> NormalizationProvider:
        return self._build("normalization")

    def build_storage_provider(self) -> StorageProvider:
        return self._build("storage")

    def build_llm_provider(self) -> LLMProvider:
        return self._build("llm")

    def _build(self, provider_type: str):
        config = self.get_config(provider_type)
        registry = self._registries.get(provider_type, {})
        provider_cls = registry.get(config.name)
        if provider_cls is None:
            available = ", ".join(sorted(registry))
            raise ProviderConfigurationError(
                provider_type=provider_type,
                provider_name=config.name,
                code="unsupported_provider",
                message=f"Unsupported {provider_type} provider '{config.name}'. Available: {available}",
            )
        return provider_cls(config=config)
