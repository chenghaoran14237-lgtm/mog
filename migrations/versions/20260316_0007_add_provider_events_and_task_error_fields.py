"""add provider events and task error fields

Revision ID: 20260316_0007
Revises: 20260316_0006
Create Date: 2026-03-16 17:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0007"
down_revision = "20260316_0006"
branch_labels = None
depends_on = None


def _json_object_default() -> sa.TextClause:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "mysql":
        return sa.text("(JSON_OBJECT())")
    return sa.text("'{}'")


def upgrade() -> None:
    op.add_column("tasks", sa.Column("last_error_category", sa.String(length=100), nullable=True))
    op.add_column("tasks", sa.Column("last_error_retryable", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    op.create_table(
        "provider_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=_json_object_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_provider_events_task_id", "provider_events", ["task_id"], unique=False)
    op.create_index("ix_provider_events_user_id", "provider_events", ["user_id"], unique=False)
    op.create_index("ix_provider_events_provider_type", "provider_events", ["provider_type"], unique=False)
    op.create_index("ix_provider_events_request_id", "provider_events", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_provider_events_request_id", table_name="provider_events")
    op.drop_index("ix_provider_events_provider_type", table_name="provider_events")
    op.drop_index("ix_provider_events_user_id", table_name="provider_events")
    op.drop_index("ix_provider_events_task_id", table_name="provider_events")
    op.drop_table("provider_events")
    op.drop_column("tasks", "last_error_retryable")
    op.drop_column("tasks", "last_error_category")
