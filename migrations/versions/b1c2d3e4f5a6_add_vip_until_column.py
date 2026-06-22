"""add vip_until column

Revision ID: b1c2d3e4f5a6
Revises: a3c9f1b2d4e5
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = 'a3c9f1b2d4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('vip_until', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('user', 'vip_until')
