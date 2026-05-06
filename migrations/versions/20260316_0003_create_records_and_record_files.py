"""create records and record files tables

Revision ID: 20260316_0003
Revises: 20260316_0002
Create Date: 2026-03-16 13:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0003"
down_revision = "20260316_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "record_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("records.id"), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_provider", sa.String(length=100), nullable=True),
        sa.Column("storage_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_record_files_record_id", "record_files", ["record_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_record_files_record_id", table_name="record_files")
    op.drop_table("record_files")
    op.drop_table("records")
