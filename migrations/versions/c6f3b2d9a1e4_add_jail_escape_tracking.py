"""add_jail_escape_tracking

Revision ID: c6f3b2d9a1e4
Revises: 9124fe2bf48a
Create Date: 2026-01-11 21:33:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c6f3b2d9a1e4'
down_revision = '9124fe2bf48a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'jail_escape_attempts',
                sa.Integer(),
                nullable=False,
                server_default=sa.text('0')))
        batch_op.add_column(
            sa.Column(
                'jail_escape_attempts_date',
                sa.Date(),
                nullable=True))
        batch_op.add_column(
            sa.Column(
                'jail_escape_last_at',
                sa.DateTime(),
                nullable=True))

        batch_op.add_column(
            sa.Column(
                'jail_gilboa_attempts',
                sa.Integer(),
                nullable=False,
                server_default=sa.text('0')))
        batch_op.add_column(
            sa.Column(
                'jail_gilboa_attempts_date',
                sa.Date(),
                nullable=True))
        batch_op.add_column(
            sa.Column(
                'jail_gilboa_last_at',
                sa.DateTime(),
                nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('jail_gilboa_last_at')
        batch_op.drop_column('jail_gilboa_attempts_date')
        batch_op.drop_column('jail_gilboa_attempts')

        batch_op.drop_column('jail_escape_last_at')
        batch_op.drop_column('jail_escape_attempts_date')
        batch_op.drop_column('jail_escape_attempts')
