"""add document versions and bind risk to versions

Revision ID: 20260316_0010
Revises: 20260316_0009
Create Date: 2026-03-16 23:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0010"
down_revision = "20260316_0009"
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
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("extracted_documents.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_id", sa.Integer(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_from_ocr_result_id", sa.Integer(), sa.ForeignKey("ocr_results.id"), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False, server_default=_json_object_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"], unique=False)
    op.create_index("ix_document_versions_version_number", "document_versions", ["version_number"], unique=False)
    op.create_index("ix_document_versions_is_current", "document_versions", ["is_current"], unique=False)
    op.create_index("ix_document_versions_created_from_ocr_result_id", "document_versions", ["created_from_ocr_result_id"], unique=False)
    op.create_index("ix_document_versions_snapshot_hash", "document_versions", ["snapshot_hash"], unique=False)
    op.create_index("ix_document_versions_supersedes_version_id", "document_versions", ["supersedes_version_id"], unique=False)

    if _dialect_name() == "mysql":
        op.execute(
            """
            INSERT INTO document_versions (
                document_id,
                version_number,
                supersedes_version_id,
                is_current,
                created_from_ocr_result_id,
                snapshot_hash,
                normalized_payload,
                created_at
            )
            SELECT
                id,
                1,
                NULL,
                1,
                ocr_result_id,
                CONCAT('legacy-version-', id),
                normalized_payload,
                created_at
            FROM extracted_documents
            """
        )
    else:
        op.execute(
            """
            INSERT INTO document_versions (
                document_id,
                version_number,
                supersedes_version_id,
                is_current,
                created_from_ocr_result_id,
                snapshot_hash,
                normalized_payload,
                created_at
            )
            SELECT
                id,
                1,
                NULL,
                1,
                ocr_result_id,
                'legacy-version-' || id,
                normalized_payload,
                created_at
            FROM extracted_documents
            """
        )

    op.add_column("measurements", sa.Column("document_version_id", sa.Integer(), nullable=True))
    op.create_index("ix_measurements_document_version_id", "measurements", ["document_version_id"], unique=False)
    op.execute(
        """
        UPDATE measurements
        SET document_version_id = (
            SELECT id
            FROM document_versions
            WHERE document_versions.document_id = measurements.extracted_document_id
              AND document_versions.is_current = 1
            ORDER BY document_versions.id DESC
            LIMIT 1
        )
        """
    )

    op.add_column("risk_evaluations", sa.Column("document_version_id", sa.Integer(), nullable=True))
    op.create_index("ix_risk_evaluations_document_version_id", "risk_evaluations", ["document_version_id"], unique=False)
    op.execute(
        """
        UPDATE risk_evaluations
        SET document_version_id = (
            SELECT id
            FROM document_versions
            WHERE document_versions.document_id = risk_evaluations.document_id
              AND document_versions.is_current = 1
            ORDER BY document_versions.id DESC
            LIMIT 1
        )
        """
    )

    op.add_column("risk_results", sa.Column("document_version_id", sa.Integer(), nullable=True))
    op.create_index("ix_risk_results_document_version_id", "risk_results", ["document_version_id"], unique=False)
    op.execute(
        """
        UPDATE risk_results
        SET document_version_id = (
            SELECT document_version_id
            FROM risk_evaluations
            WHERE risk_evaluations.id = risk_results.evaluation_id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_risk_results_document_version_id", table_name="risk_results")
    op.drop_column("risk_results", "document_version_id")

    op.drop_index("ix_risk_evaluations_document_version_id", table_name="risk_evaluations")
    op.drop_column("risk_evaluations", "document_version_id")

    op.drop_index("ix_measurements_document_version_id", table_name="measurements")
    op.drop_column("measurements", "document_version_id")

    op.drop_index("ix_document_versions_supersedes_version_id", table_name="document_versions")
    op.drop_index("ix_document_versions_snapshot_hash", table_name="document_versions")
    op.drop_index("ix_document_versions_created_from_ocr_result_id", table_name="document_versions")
    op.drop_index("ix_document_versions_is_current", table_name="document_versions")
    op.drop_index("ix_document_versions_version_number", table_name="document_versions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
