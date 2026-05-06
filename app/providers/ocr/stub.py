from app.providers.base import OCRExtractionResult, OCRProvider, ProviderConfig


class StubOCRProvider(OCRProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config or ProviderConfig(provider_type="ocr", name="stub"))

    def extract(self, file_bytes: bytes, content_type: str | None = None) -> OCRExtractionResult:
        return OCRExtractionResult(
            provider_name=self.config.name,
            raw_text=f"stub:{len(file_bytes)} bytes",
            raw_payload={
                "content_type": content_type,
                "byte_count": len(file_bytes),
            },
        )
