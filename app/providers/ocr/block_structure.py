from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OCRBlock(BaseModel):
    """OCR raw block representation."""

    block_id: str = Field(..., description="Unique block identifier")
    page_index: int = Field(0, description="Zero-based page index")
    reading_order: int = Field(..., description="Reading order within the extraction result")
    source_kind: Literal["line", "paragraph", "table_row", "cell_group", "unknown"] = Field(
        "unknown",
        description="Block source type",
    )
    raw_text: str = Field("", description="Original OCR text")
    clean_text: str = Field("", description="Minimally cleaned text")
    bbox: list[float] | None = Field(None, description="Bounding box [x0, y0, x1, y1]")
    confidence: float | None = Field(None, description="Confidence score between 0 and 1")
    line_index_within_page: int | None = Field(None, description="Zero-based line index within the page")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Provider-specific metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "block_id": "page_0_line_5",
                "page_index": 0,
                "reading_order": 5,
                "source_kind": "line",
                "raw_text": "WBC 4.13 10^9/L",
                "clean_text": "WBC 4.13 10^9/L",
                "bbox": [100.0, 200.0, 500.0, 220.0],
                "confidence": 0.95,
                "line_index_within_page": 5,
            }
        }
    }


class OCRBlockPayload(BaseModel):
    """Normalized OCR block payload."""

    blocks: list[OCRBlock] = Field(default_factory=list, description="OCR block list")
    page_count: int = Field(1, description="Total number of pages")
    total_blocks: int = Field(0, description="Total number of blocks")
    extraction_metadata: dict[str, Any] = Field(default_factory=dict, description="Extraction metadata")

    def model_post_init(self, __context: Any) -> None:
        if self.total_blocks == 0:
            self.total_blocks = len(self.blocks)
