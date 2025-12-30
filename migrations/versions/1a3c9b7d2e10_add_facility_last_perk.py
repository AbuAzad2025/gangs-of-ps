"""Add last perk timestamp to facilities

Revision ID: 1a3c9b7d2e10
Revises: 0f6a0d9e5c11
Create Date: 2025-12-27

"""

from alembic import op
import sqlalchemy as sa


revision = "1a3c9b7d2e10"
down_revision = "0f6a0d9e5c11"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_facility", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_perk_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("user_facility", schema=None) as batch_op:
        batch_op.drop_column("last_perk_at")

