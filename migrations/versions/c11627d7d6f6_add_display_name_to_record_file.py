"""add_display_name_to_record_file

Revision ID: c11627d7d6f6
Revises: 20260318_0001
Create Date: 2026-03-18 16:37:52.576873
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = 'c11627d7d6f6'
down_revision = '20260318_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('record_files', sa.Column('display_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('record_files', 'display_name')
