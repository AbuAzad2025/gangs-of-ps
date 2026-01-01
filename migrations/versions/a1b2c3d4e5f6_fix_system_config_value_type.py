"""fix system_config value type

Revision ID: a1b2c3d4e5f6
Revises: f9e8d7c6b5a4
Create Date: 2026-01-01 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f9e8d7c6b5a4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_config', schema=None) as batch_op:
        batch_op.alter_column('value',
               existing_type=sa.String(length=255),
               type_=sa.Text(),
               existing_nullable=True)


def downgrade():
    with op.batch_alter_table('system_config', schema=None) as batch_op:
        batch_op.alter_column('value',
               existing_type=sa.Text(),
               type_=sa.String(length=255),
               existing_nullable=True)
