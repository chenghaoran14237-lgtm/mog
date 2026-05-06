from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("extracted_documents.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_id: Mapped[int | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_from_ocr_result_id: Mapped[int] = mapped_column(ForeignKey("ocr_results.id"), nullable=False, index=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    document: Mapped["ExtractedDocument"] = relationship(back_populates="versions")
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="document_version",
        cascade="all, delete-orphan",
    )
