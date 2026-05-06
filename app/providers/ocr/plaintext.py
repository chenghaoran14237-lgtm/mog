from app.providers.base import OCRExtractionResult, OCRProvider, ProviderConfig
from app.providers.ocr.block_structure import OCRBlock, OCRBlockPayload


class PlaintextOCRProvider(OCRProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config or ProviderConfig(provider_type="ocr", name="plaintext"))

    def extract(self, file_bytes: bytes, content_type: str | None = None) -> OCRExtractionResult:
        decoded_text = file_bytes.decode("utf-8", errors="replace").strip()
        return OCRExtractionResult(
            provider_name=self.config.name,
            raw_text=decoded_text,
            raw_payload={
                "content_type": content_type,
                "character_count": len(decoded_text),
            },
            block_payload=self._build_block_payload(decoded_text),
        )

    def _build_block_payload(self, raw_text: str) -> OCRBlockPayload:
        block = OCRBlock(
            block_id="page_0_block_0",
            page_index=0,
            reading_order=0,
            source_kind="paragraph",
            raw_text=raw_text,
            clean_text=raw_text.strip(),
        )
        return OCRBlockPayload(
            blocks=[block],
            page_count=1,
            extraction_metadata={
                "provider": self.config.name,
                "block_generation_strategy": "single_block",
            },
        )
