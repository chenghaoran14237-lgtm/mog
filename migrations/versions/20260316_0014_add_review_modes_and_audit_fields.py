"""add review modes and audit fields

Revision ID: 20260316_0014
Revises: 20260316_0013
Create Date: 2026-03-16 21:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0014"
down_revision = "20260316_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_sessions",
        sa.Column("requested_review_mode", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "review_sessions",
        sa.Column(
            "effective_review_mode",
            sa.String(length=50),
            nullable=False,
            server_default="consistency_review",
        ),
    )

    op.add_column(
        "review_audits",
        sa.Column("requested_review_mode", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "inferred_review_mode",
            sa.String(length=50),
            nullable=False,
            server_default="consistency_review",
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "mode_reason",
            sa.String(length=255),
            nullable=False,
            server_default="legacy_review_mode_not_recorded",
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "conflict_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("review_audits", "conflict_count")
    op.drop_column("review_audits", "mode_reason")
    op.drop_column("review_audits", "inferred_review_mode")
    op.drop_column("review_audits", "requested_review_mode")
    op.drop_column("review_sessions", "effective_review_mode")
    op.drop_column("review_sessions", "requested_review_mode")
