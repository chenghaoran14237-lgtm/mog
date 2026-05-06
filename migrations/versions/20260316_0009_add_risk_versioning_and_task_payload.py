"""add risk versioning and task payload

Revision ID: 20260316_0009
Revises: 20260316_0008
Create Date: 2026-03-16 21:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0009"
down_revision = "20260316_0008"
branch_labels = None
depends_on = None


def _json_object_default() -> sa.TextClause:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "mysql":
        return sa.text("(JSON_OBJECT())")
    return sa.text("'{}'")


def _dialect_name() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    op.add_column("tasks", sa.Column("task_payload", sa.JSON(), nullable=False, server_default=_json_object_default()))

    op.add_column("risk_evaluations", sa.Column("source_snapshot_hash", sa.String(length=64), nullable=False, server_default=sa.text("''")))
    op.add_column("risk_evaluations", sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("risk_evaluations", sa.Column("supersedes_evaluation_id", sa.Integer(), nullable=True))
    op.add_column("risk_evaluations", sa.Column("superseded_by_evaluation_id", sa.Integer(), nullable=True))
    op.add_column("risk_evaluations", sa.Column("superseded_reason", sa.String(length=100), nullable=True))
    op.add_column("risk_evaluations", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_risk_evaluations_source_snapshot_hash", "risk_evaluations", ["source_snapshot_hash"], unique=False)
    op.create_index("ix_risk_evaluations_is_current", "risk_evaluations", ["is_current"], unique=False)
    op.create_index("ix_risk_evaluations_supersedes_evaluation_id", "risk_evaluations", ["supersedes_evaluation_id"], unique=False)
    op.create_index("ix_risk_evaluations_superseded_by_evaluation_id", "risk_evaluations", ["superseded_by_evaluation_id"], unique=False)

    if _dialect_name() == "mysql":
        op.execute("UPDATE risk_evaluations SET source_snapshot_hash = CONCAT('legacy-', id)")
    else:
        op.execute("UPDATE risk_evaluations SET source_snapshot_hash = 'legacy-' || id")
    op.execute("UPDATE risk_evaluations SET is_current = 0")
    if _dialect_name() == "mysql":
        op.execute(
            """
            UPDATE risk_evaluations AS target
            JOIN (
                SELECT MAX(id) AS id
                FROM risk_evaluations
                GROUP BY document_id
            ) AS latest
              ON latest.id = target.id
            SET target.is_current = 1
            """
        )
    else:
        op.execute(
            """
            UPDATE risk_evaluations
            SET is_current = 1
            WHERE id IN (
                SELECT MAX(id)
                FROM risk_evaluations
                GROUP BY document_id
            )
            """
        )


def downgrade() -> None:
    op.drop_index("ix_risk_evaluations_superseded_by_evaluation_id", table_name="risk_evaluations")
    op.drop_index("ix_risk_evaluations_supersedes_evaluation_id", table_name="risk_evaluations")
    op.drop_index("ix_risk_evaluations_is_current", table_name="risk_evaluations")
    op.drop_index("ix_risk_evaluations_source_snapshot_hash", table_name="risk_evaluations")

    op.drop_column("risk_evaluations", "superseded_at")
    op.drop_column("risk_evaluations", "superseded_reason")
    op.drop_column("risk_evaluations", "superseded_by_evaluation_id")
    op.drop_column("risk_evaluations", "supersedes_evaluation_id")
    op.drop_column("risk_evaluations", "is_current")
    op.drop_column("risk_evaluations", "source_snapshot_hash")

    op.drop_column("tasks", "task_payload")
