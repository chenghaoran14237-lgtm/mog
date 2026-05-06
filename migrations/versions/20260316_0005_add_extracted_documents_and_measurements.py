"""add extracted documents and measurements

Revision ID: 20260316_0005
Revises: 20260316_0004
Create Date: 2026-03-16 15:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0005"
down_revision = "20260316_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extracted_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ocr_result_id", sa.Integer(), sa.ForeignKey("ocr_results.id"), nullable=False),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("records.id"), nullable=False),
        sa.Column("record_file_id", sa.Integer(), sa.ForeignKey("record_files.id"), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_extracted_documents_ocr_result_id", "extracted_documents", ["ocr_result_id"], unique=True)
    op.create_index("ix_extracted_documents_record_id", "extracted_documents", ["record_id"], unique=False)
    op.create_index("ix_extracted_documents_record_file_id", "extracted_documents", ["record_file_id"], unique=False)

    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("extracted_document_id", sa.Integer(), sa.ForeignKey("extracted_documents.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("value_text", sa.String(length=100), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_measurements_extracted_document_id", "measurements", ["extracted_document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_measurements_extracted_document_id", table_name="measurements")
    op.drop_table("measurements")
    op.drop_index("ix_extracted_documents_record_file_id", table_name="extracted_documents")
    op.drop_index("ix_extracted_documents_record_id", table_name="extracted_documents")
    op.drop_index("ix_extracted_documents_ocr_result_id", table_name="extracted_documents")
    op.drop_table("extracted_documents")
