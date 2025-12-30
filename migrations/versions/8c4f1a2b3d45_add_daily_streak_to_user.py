"""Add daily streak to user

Revision ID: 8c4f1a2b3d45
Revises: 7b8d9e0a1c23
Create Date: 2025-12-28

"""

from alembic import op
import sqlalchemy as sa


revision = "8c4f1a2b3d45"
down_revision = "7b8d9e0a1c23"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("daily_streak", sa.Integer(), nullable=True, server_default=sa.text("0")))


def downgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("daily_streak")

