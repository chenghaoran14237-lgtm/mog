"""add ocr revisions and document provenance

Revision ID: 20260316_0011
Revises: 20260316_0010
Create Date: 2026-03-16 23:40:00
"""

from __future__ import annotations

from collections import defaultdict

from alembic import op
import sqlalchemy as sa


revision = "20260316_0011"
down_revision = "20260316_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ocr_results",
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "ocr_results",
        sa.Column("supersedes_ocr_result_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ocr_results",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_ocr_results_supersedes_ocr_result_id", "ocr_results", ["supersedes_ocr_result_id"], unique=False)
    op.create_index("ix_ocr_results_is_current", "ocr_results", ["is_current"], unique=False)

    op.add_column(
        "extracted_documents",
        sa.Column("current_ocr_result_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_extracted_documents_current_ocr_result_id", "extracted_documents", ["current_ocr_result_id"], unique=False)

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, record_file_id, status
            FROM ocr_results
            ORDER BY record_file_id ASC, id ASC
            """
        )
    ).fetchall()

    grouped_rows: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for row in rows:
        grouped_rows[row.record_file_id].append((row.id, row.status))

    for record_file_id, items in grouped_rows.items():
        previous_id: int | None = None
        completed_ids: list[int] = []
        for revision_number, (ocr_result_id, status) in enumerate(items, start=1):
            connection.execute(
                sa.text(
                    """
                    UPDATE ocr_results
                    SET revision_number = :revision_number,
                        supersedes_ocr_result_id = :supersedes_ocr_result_id
                    WHERE id = :ocr_result_id
                    """
                ),
                {
                    "revision_number": revision_number,
                    "supersedes_ocr_result_id": previous_id,
                    "ocr_result_id": ocr_result_id,
                },
            )
            if status == "completed":
                completed_ids.append(ocr_result_id)
            previous_id = ocr_result_id

        if completed_ids:
            connection.execute(
                sa.text("UPDATE ocr_results SET is_current = 1 WHERE id = :ocr_result_id"),
                {"ocr_result_id": completed_ids[-1]},
            )

    connection.execute(sa.text("UPDATE extracted_documents SET current_ocr_result_id = ocr_result_id"))
    op.create_index("ix_ocr_results_record_file_id_revision_number", "ocr_results", ["record_file_id", "revision_number"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_extracted_documents_current_ocr_result_id", table_name="extracted_documents")
    op.drop_column("extracted_documents", "current_ocr_result_id")

    op.drop_index("ix_ocr_results_record_file_id_revision_number", table_name="ocr_results")
    op.drop_index("ix_ocr_results_is_current", table_name="ocr_results")
    op.drop_index("ix_ocr_results_supersedes_ocr_result_id", table_name="ocr_results")
    op.drop_column("ocr_results", "is_current")
    op.drop_column("ocr_results", "supersedes_ocr_result_id")
    op.drop_column("ocr_results", "revision_number")
