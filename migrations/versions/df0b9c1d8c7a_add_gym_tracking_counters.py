"""add_gym_tracking_counters

Revision ID: df0b9c1d8c7a
Revises: c6f3b2d9a1e4
Create Date: 2026-01-11 22:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'df0b9c1d8c7a'
down_revision = 'c6f3b2d9a1e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gym_sessions_count', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('gym_sessions_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('gym_speedups_count', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('gym_speedups_date', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('gym_speedups_date')
        batch_op.drop_column('gym_speedups_count')
        batch_op.drop_column('gym_sessions_date')
        batch_op.drop_column('gym_sessions_count')

