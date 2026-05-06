from __future__ import annotations

from app.models.ocr_result import OCRResult
from app.providers.ocr.block_structure import OCRBlockPayload


class OCRBlockService:
    """OCR block payload access helpers."""

    @staticmethod
    def extract_block_payload(ocr_result: OCRResult) -> OCRBlockPayload | None:
        if not ocr_result.raw_payload:
            return None

        block_data = ocr_result.raw_payload.get("block_payload")
        if not block_data:
            return None

        try:
            return OCRBlockPayload.model_validate(block_data)
        except Exception:
            return None

    @staticmethod
    def has_block_support(ocr_result: OCRResult) -> bool:
        return ocr_result.raw_payload is not None and "block_payload" in ocr_result.raw_payload
