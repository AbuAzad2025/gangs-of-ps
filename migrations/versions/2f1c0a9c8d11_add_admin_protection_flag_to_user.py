"""Add admin protection flag to user

Revision ID: 2f1c0a9c8d11
Revises: 1a3c9b7d2e10
Create Date: 2025-12-28

"""

from alembic import op
import sqlalchemy as sa


revision = "2f1c0a9c8d11"
down_revision = "1a3c9b7d2e10"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_admin_protected", sa.Boolean(), nullable=True, server_default=sa.text("false")))


def downgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("is_admin_protected")

