"""add summary runs

Revision ID: 20260316_0015
Revises: 20260316_0014
Create Date: 2026-03-16 23:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0015"
down_revision = "20260316_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "summary_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("summary_mode", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("requested_metrics", sa.JSON(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("render_mode", sa.String(length=20), nullable=False, server_default="template"),
        sa.Column("input_bundle_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("generation_notes", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_summary_runs_user_id", "summary_runs", ["user_id"])
    op.create_index("ix_summary_runs_summary_mode", "summary_runs", ["summary_mode"])
    op.create_index("ix_summary_runs_status", "summary_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_summary_runs_status", table_name="summary_runs")
    op.drop_index("ix_summary_runs_summary_mode", table_name="summary_runs")
    op.drop_index("ix_summary_runs_user_id", table_name="summary_runs")
    op.drop_table("summary_runs")
