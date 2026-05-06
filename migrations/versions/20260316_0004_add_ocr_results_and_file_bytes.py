"""add ocr results and file bytes

Revision ID: 20260316_0004
Revises: 20260316_0003
Create Date: 2026-03-16 14:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0004"
down_revision = "20260316_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("record_files", sa.Column("content_bytes", sa.LargeBinary(), nullable=True))
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE record_files SET content_bytes = :empty WHERE content_bytes IS NULL"), {"empty": b""})
    with op.batch_alter_table("record_files") as batch_op:
        batch_op.alter_column("content_bytes", existing_type=sa.LargeBinary(), nullable=False)

    op.create_table(
        "ocr_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("record_file_id", sa.Integer(), sa.ForeignKey("record_files.id"), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ocr_results_record_file_id", "ocr_results", ["record_file_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ocr_results_record_file_id", table_name="ocr_results")
    op.drop_table("ocr_results")
    with op.batch_alter_table("record_files") as batch_op:
        batch_op.drop_column("content_bytes")
