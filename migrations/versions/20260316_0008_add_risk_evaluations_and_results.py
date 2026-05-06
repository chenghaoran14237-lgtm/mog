"""add risk evaluations and risk results

Revision ID: 20260316_0008
Revises: 20260316_0007
Create Date: 2026-03-16 19:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0008"
down_revision = "20260316_0007"
branch_labels = None
depends_on = None


def _json_object_default() -> sa.TextClause:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "mysql":
        return sa.text("(JSON_OBJECT())")
    return sa.text("'{}'")


def upgrade() -> None:
    op.create_table(
        "risk_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("extracted_documents.id"), nullable=False),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("records.id"), nullable=False),
        sa.Column("record_file_id", sa.Integer(), sa.ForeignKey("record_files.id"), nullable=False),
        sa.Column("rule_set_version", sa.String(length=100), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("highest_severity", sa.String(length=50), nullable=True),
        sa.Column("audit_payload", sa.JSON(), nullable=False, server_default=_json_object_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_risk_evaluations_user_id", "risk_evaluations", ["user_id"], unique=False)
    op.create_index("ix_risk_evaluations_task_id", "risk_evaluations", ["task_id"], unique=False)
    op.create_index("ix_risk_evaluations_document_id", "risk_evaluations", ["document_id"], unique=False)
    op.create_index("ix_risk_evaluations_record_id", "risk_evaluations", ["record_id"], unique=False)
    op.create_index("ix_risk_evaluations_record_file_id", "risk_evaluations", ["record_file_id"], unique=False)

    op.create_table(
        "risk_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("risk_evaluations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("extracted_documents.id"), nullable=False),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("records.id"), nullable=False),
        sa.Column("record_file_id", sa.Integer(), sa.ForeignKey("record_files.id"), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("explanation", sa.String(length=500), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=_json_object_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_risk_results_evaluation_id", "risk_results", ["evaluation_id"], unique=False)
    op.create_index("ix_risk_results_user_id", "risk_results", ["user_id"], unique=False)
    op.create_index("ix_risk_results_document_id", "risk_results", ["document_id"], unique=False)
    op.create_index("ix_risk_results_record_id", "risk_results", ["record_id"], unique=False)
    op.create_index("ix_risk_results_record_file_id", "risk_results", ["record_file_id"], unique=False)
    op.create_index("ix_risk_results_rule_id", "risk_results", ["rule_id"], unique=False)
    op.create_index("ix_risk_results_severity", "risk_results", ["severity"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_risk_results_severity", table_name="risk_results")
    op.drop_index("ix_risk_results_rule_id", table_name="risk_results")
    op.drop_index("ix_risk_results_record_file_id", table_name="risk_results")
    op.drop_index("ix_risk_results_record_id", table_name="risk_results")
    op.drop_index("ix_risk_results_document_id", table_name="risk_results")
    op.drop_index("ix_risk_results_user_id", table_name="risk_results")
    op.drop_index("ix_risk_results_evaluation_id", table_name="risk_results")
    op.drop_table("risk_results")

    op.drop_index("ix_risk_evaluations_record_file_id", table_name="risk_evaluations")
    op.drop_index("ix_risk_evaluations_record_id", table_name="risk_evaluations")
    op.drop_index("ix_risk_evaluations_document_id", table_name="risk_evaluations")
    op.drop_index("ix_risk_evaluations_task_id", table_name="risk_evaluations")
    op.drop_index("ix_risk_evaluations_user_id", table_name="risk_evaluations")
    op.drop_table("risk_evaluations")
