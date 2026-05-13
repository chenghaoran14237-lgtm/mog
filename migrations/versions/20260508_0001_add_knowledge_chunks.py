"""add knowledge chunks for rag audit retrieval

Revision ID: 20260508_0001
Revises: 20260428_0002
Create Date: 2026-05-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_0001"
down_revision = "20260428_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_title", sa.String(length=255), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_chunks_scope"), "knowledge_chunks", ["scope"], unique=False)
    op.create_index(op.f("ix_knowledge_chunks_source_type"), "knowledge_chunks", ["source_type"], unique=False)
    op.create_index(op.f("ix_knowledge_chunks_is_active"), "knowledge_chunks", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_chunks_is_active"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_source_type"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_scope"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
