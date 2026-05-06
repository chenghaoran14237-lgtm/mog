"""add review answer modes and guideline fields

Revision ID: 20260316_0016
Revises: 20260316_0015
Create Date: 2026-03-16 23:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0016"
down_revision = "20260316_0015"
branch_labels = None
depends_on = None


def _json_array_default() -> sa.TextClause:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "mysql":
        return sa.text("(JSON_ARRAY())")
    return sa.text("'[]'")


def upgrade() -> None:
    op.add_column(
        "review_sessions",
        sa.Column(
            "requested_answer_mode",
            sa.String(length=20),
            nullable=False,
            server_default="template",
        ),
    )
    op.add_column(
        "review_sessions",
        sa.Column(
            "effective_answer_mode",
            sa.String(length=20),
            nullable=False,
            server_default="template",
        ),
    )
    op.add_column(
        "review_sessions",
        sa.Column(
            "guideline_context_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "review_sessions",
        sa.Column(
            "guideline_context_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "review_audits",
        sa.Column(
            "effective_review_mode",
            sa.String(length=50),
            nullable=False,
            server_default="consistency_review",
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "requested_answer_mode",
            sa.String(length=20),
            nullable=False,
            server_default="template",
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "effective_answer_mode",
            sa.String(length=20),
            nullable=False,
            server_default="template",
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "generation_notes",
            sa.JSON(),
            nullable=False,
            server_default=_json_array_default(),
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "guideline_context_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "guideline_context_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column("render_fallback_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_audits", "render_fallback_reason")
    op.drop_column("review_audits", "guideline_context_used")
    op.drop_column("review_audits", "guideline_context_requested")
    op.drop_column("review_audits", "generation_notes")
    op.drop_column("review_audits", "effective_answer_mode")
    op.drop_column("review_audits", "requested_answer_mode")
    op.drop_column("review_audits", "effective_review_mode")
    op.drop_column("review_sessions", "guideline_context_used")
    op.drop_column("review_sessions", "guideline_context_requested")
    op.drop_column("review_sessions", "effective_answer_mode")
    op.drop_column("review_sessions", "requested_answer_mode")
