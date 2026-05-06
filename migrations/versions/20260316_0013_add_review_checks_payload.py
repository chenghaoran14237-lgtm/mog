"""add review checks payload

Revision ID: 20260316_0013
Revises: 20260316_0012
Create Date: 2026-03-16 20:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0013"
down_revision = "20260316_0012"
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
            "review_checks_payload",
            sa.JSON(),
            nullable=False,
            server_default=_json_array_default(),
        ),
    )
    op.add_column(
        "review_audits",
        sa.Column(
            "check_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("review_audits", "check_count")
    op.drop_column("review_sessions", "review_checks_payload")
