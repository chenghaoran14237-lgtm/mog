from app.providers.base import LLMProvider, ProviderConfig


class StubLLMProvider(LLMProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config or ProviderConfig(provider_type="llm", name="stub"))

    def complete(self, prompt: str) -> dict[str, str]:
        return {"provider": self.config.name, "result": prompt}
