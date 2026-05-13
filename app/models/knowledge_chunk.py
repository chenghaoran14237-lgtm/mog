from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False, default="medical_audit", index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="audit_rule", index=True)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
