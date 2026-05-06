from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ExtractedDocument(Base):
    __tablename__ = "extracted_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ocr_result_id: Mapped[int] = mapped_column(ForeignKey("ocr_results.id"), nullable=False, index=True, unique=True)
    current_ocr_result_id: Mapped[int | None] = mapped_column(ForeignKey("ocr_results.id"), nullable=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id"), nullable=False, index=True)
    record_file_id: Mapped[int] = mapped_column(ForeignKey("record_files.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, default="generic_record")
    document_category: Mapped[str] = mapped_column(String(64), nullable=False, default="narrative_context")
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="normalized")
    report_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="extracted_document",
        cascade="all, delete-orphan",
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
