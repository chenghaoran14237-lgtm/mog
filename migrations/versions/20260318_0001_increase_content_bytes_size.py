"""increase content_bytes size to LONGBLOB

Revision ID: 20260318_0001
Revises: d682234d8b15
Create Date: 2026-03-18 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_0001"
down_revision = "d682234d8b15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change content_bytes from BLOB to LONGBLOB to support larger files
    # LONGBLOB can store up to 4GB
    op.execute("ALTER TABLE record_files MODIFY content_bytes LONGBLOB NOT NULL")


def downgrade() -> None:
    # Revert back to BLOB (this may fail if there are files larger than 65KB)
    op.execute("ALTER TABLE record_files MODIFY content_bytes BLOB NOT NULL")
