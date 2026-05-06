"""add review sessions and audit

Revision ID: 20260316_0012
Revises: 20260316_0011
Create Date: 2026-03-16 20:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0012"
down_revision = "20260316_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("include_risk_context", sa.Boolean(), nullable=False),
        sa.Column("include_summary_context", sa.Boolean(), nullable=False),
        sa.Column("input_bundle_payload", sa.JSON(), nullable=False),
        sa.Column("answer_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_sessions_user_id", "review_sessions", ["user_id"], unique=False)
    op.create_index("ix_review_sessions_status", "review_sessions", ["status"], unique=False)

    op.create_table(
        "review_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_session_id", sa.Integer(), nullable=False),
        sa.Column("audit_mode", sa.String(length=100), nullable=False),
        sa.Column("checks_performed", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["review_session_id"], ["review_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_audits_review_session_id", "review_audits", ["review_session_id"], unique=True)

    op.create_table(
        "review_conflict_findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_session_id", sa.Integer(), nullable=False),
        sa.Column("finding_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_metric_names", sa.JSON(), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["review_session_id"], ["review_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_conflict_findings_review_session_id",
        "review_conflict_findings",
        ["review_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_conflict_findings_finding_type",
        "review_conflict_findings",
        ["finding_type"],
        unique=False,
    )
    op.create_index(
        "ix_review_conflict_findings_severity",
        "review_conflict_findings",
        ["severity"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_review_conflict_findings_severity", table_name="review_conflict_findings")
    op.drop_index("ix_review_conflict_findings_finding_type", table_name="review_conflict_findings")
    op.drop_index("ix_review_conflict_findings_review_session_id", table_name="review_conflict_findings")
    op.drop_table("review_conflict_findings")

    op.drop_index("ix_review_audits_review_session_id", table_name="review_audits")
    op.drop_table("review_audits")

    op.drop_index("ix_review_sessions_status", table_name="review_sessions")
    op.drop_index("ix_review_sessions_user_id", table_name="review_sessions")
    op.drop_table("review_sessions")
