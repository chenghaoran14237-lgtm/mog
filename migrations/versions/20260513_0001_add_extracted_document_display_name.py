"""add display name to extracted documents

Revision ID: 20260513_0001
Revises: 20260508_0001
Create Date: 2026-05-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260513_0001"
down_revision = "20260508_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("extracted_documents", sa.Column("display_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("extracted_documents", "display_name")
