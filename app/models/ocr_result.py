from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class OCRResult(Base):
    """Persisted OCR result and provider metadata.

    raw_payload stores provider metadata such as model, protocol, usage, and
    optional block_payload when block-level OCR structure is available.
    """

    __tablename__ = "ocr_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_file_id: Mapped[int] = mapped_column(ForeignKey("record_files.id"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_ocr_result_id: Mapped[int | None] = mapped_column(ForeignKey("ocr_results.id"), nullable=True, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    record_file: Mapped["RecordFile"] = relationship(back_populates="ocr_results")
