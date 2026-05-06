"""add audit report graph tables

Revision ID: 20260506_0001
Revises: c11627d7d6f6
Create Date: 2026-05-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260506_0001"
down_revision = "c11627d7d6f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_report_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("selected_document_version_ids", sa.JSON(), nullable=False),
        sa.Column("graph_state", sa.JSON(), nullable=False),
        sa.Column("final_report", sa.JSON(), nullable=True),
        sa.Column("iteration_count", sa.Integer(), nullable=False),
        sa.Column("max_iterations", sa.Integer(), nullable=False),
        sa.Column("stop_reason", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_report_runs_user_id"), "audit_report_runs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_report_runs_status"), "audit_report_runs", ["status"], unique=False)

    op.create_table(
        "audit_report_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("node_name", sa.String(length=100), nullable=True),
        sa.Column("edge_source", sa.String(length=100), nullable=True),
        sa.Column("edge_target", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["audit_report_runs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_report_events_run_id"), "audit_report_events", ["run_id"], unique=False)
    op.create_index(op.f("ix_audit_report_events_user_id"), "audit_report_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_report_events_sequence"), "audit_report_events", ["sequence"], unique=False)
    op.create_index(op.f("ix_audit_report_events_event_type"), "audit_report_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_audit_report_events_node_name"), "audit_report_events", ["node_name"], unique=False)

    op.create_table(
        "audit_report_node_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("node_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("visit_count", sa.Integer(), nullable=False),
        sa.Column("last_event_id", sa.Integer(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["last_event_id"], ["audit_report_events.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["audit_report_runs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "node_name", name="uq_audit_report_node_state"),
    )
    op.create_index(op.f("ix_audit_report_node_states_run_id"), "audit_report_node_states", ["run_id"], unique=False)
    op.create_index(op.f("ix_audit_report_node_states_user_id"), "audit_report_node_states", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_report_node_states_node_name"), "audit_report_node_states", ["node_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_report_node_states_node_name"), table_name="audit_report_node_states")
    op.drop_index(op.f("ix_audit_report_node_states_user_id"), table_name="audit_report_node_states")
    op.drop_index(op.f("ix_audit_report_node_states_run_id"), table_name="audit_report_node_states")
    op.drop_table("audit_report_node_states")
    op.drop_index(op.f("ix_audit_report_events_node_name"), table_name="audit_report_events")
    op.drop_index(op.f("ix_audit_report_events_event_type"), table_name="audit_report_events")
    op.drop_index(op.f("ix_audit_report_events_sequence"), table_name="audit_report_events")
    op.drop_index(op.f("ix_audit_report_events_user_id"), table_name="audit_report_events")
    op.drop_index(op.f("ix_audit_report_events_run_id"), table_name="audit_report_events")
    op.drop_table("audit_report_events")
    op.drop_index(op.f("ix_audit_report_runs_status"), table_name="audit_report_runs")
    op.drop_index(op.f("ix_audit_report_runs_user_id"), table_name="audit_report_runs")
    op.drop_table("audit_report_runs")
