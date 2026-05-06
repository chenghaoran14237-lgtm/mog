from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    extracted_document_id: Mapped[int] = mapped_column(
        ForeignKey("extracted_documents.id"),
        nullable=False,
        index=True,
    )
    document_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_versions.id"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    value_text: Mapped[str] = mapped_column(String(100), nullable=False)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    extracted_document: Mapped["ExtractedDocument"] = relationship(back_populates="measurements")
    document_version: Mapped[DocumentVersion | None] = relationship(back_populates="measurements")
