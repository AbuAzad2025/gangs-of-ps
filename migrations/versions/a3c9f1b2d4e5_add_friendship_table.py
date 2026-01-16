"""add_friendship_table

Revision ID: a3c9f1b2d4e5
Revises: 6b5c4d3e2f1g
Create Date: 2026-01-13 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3c9f1b2d4e5'
down_revision = '6b5c4d3e2f1g'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'friendship',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user1_id', sa.Integer(), nullable=False),
        sa.Column('user2_id', sa.Integer(), nullable=False),
        sa.Column('requester_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['requester_id'], ['user.id']),
        sa.ForeignKeyConstraint(['user1_id'], ['user.id']),
        sa.ForeignKeyConstraint(['user2_id'], ['user.id']),
        sa.UniqueConstraint('user1_id', 'user2_id', name='uq_friendship_user_pair'),
    )
    op.create_index(
        'ix_friendship_user1_id',
        'friendship',
        ['user1_id'],
        unique=False)
    op.create_index(
        'ix_friendship_user2_id',
        'friendship',
        ['user2_id'],
        unique=False)
    op.create_index(
        'ix_friendship_requester_id',
        'friendship',
        ['requester_id'],
        unique=False)
    op.create_index(
        'ix_friendship_status',
        'friendship',
        ['status'],
        unique=False)
    op.create_index(
        'ix_friendship_created_at',
        'friendship',
        ['created_at'],
        unique=False)


def downgrade():
    op.drop_index('ix_friendship_created_at', table_name='friendship')
    op.drop_index('ix_friendship_status', table_name='friendship')
    op.drop_index('ix_friendship_requester_id', table_name='friendship')
    op.drop_index('ix_friendship_user2_id', table_name='friendship')
    op.drop_index('ix_friendship_user1_id', table_name='friendship')
    op.drop_table('friendship')
