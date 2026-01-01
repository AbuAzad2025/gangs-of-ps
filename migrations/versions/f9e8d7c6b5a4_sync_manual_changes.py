"""sync_manual_changes

Revision ID: f9e8d7c6b5a4
Revises: e2adb7665786
Create Date: 2026-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'f9e8d7c6b5a4'
down_revision = 'e2adb7665786'
branch_labels = None
depends_on = None


def upgrade():
    # Helper to check if column exists
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # 1. Add gym_activity to user
    user_columns = [c['name'] for c in inspector.get_columns('user')]
    if 'gym_activity' not in user_columns:
        op.add_column('user', sa.Column('gym_activity', sa.String(length=512), nullable=True))

    # 2. Add market_asset columns
    market_columns = [c['name'] for c in inspector.get_columns('market_asset')]
    if 'high_24h' not in market_columns:
        op.add_column('market_asset', sa.Column('high_24h', sa.Float(), nullable=True, server_default='0.0'))
    if 'low_24h' not in market_columns:
        op.add_column('market_asset', sa.Column('low_24h', sa.Float(), nullable=True, server_default='0.0'))
    if 'volume_24h' not in market_columns:
        op.add_column('market_asset', sa.Column('volume_24h', sa.Float(), nullable=True, server_default='0.0'))


def downgrade():
    # We can remove them, but checking existence is safer
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    market_columns = [c['name'] for c in inspector.get_columns('market_asset')]
    if 'volume_24h' in market_columns:
        op.drop_column('market_asset', 'volume_24h')
    if 'low_24h' in market_columns:
        op.drop_column('market_asset', 'low_24h')
    if 'high_24h' in market_columns:
        op.drop_column('market_asset', 'high_24h')
        
    user_columns = [c['name'] for c in inspector.get_columns('user')]
    if 'gym_activity' in user_columns:
        op.drop_column('user', 'gym_activity')
