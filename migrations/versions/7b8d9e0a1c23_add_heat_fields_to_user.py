"""Add heat fields to user

Revision ID: 7b8d9e0a1c23
Revises: 2f1c0a9c8d11
Create Date: 2025-12-28

"""

from alembic import op
import sqlalchemy as sa


revision = "7b8d9e0a1c23"
down_revision = "2f1c0a9c8d11"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("heat_points", sa.Integer(), nullable=True, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("heat_updated_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("heat_updated_at")
        batch_op.drop_column("heat_points")

