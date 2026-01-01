"""comprehensive_daily_limits

Revision ID: d4e5f6g7h8i9
Revises: b3d4e5f6g7h8
Create Date: 2026-01-01 23:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'b3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    # Helper to check if column exists
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # 1. Add daily_limit to Crime
    # Check if table 'crime' exists first
    tables = inspector.get_table_names()
    if 'crime' in tables:
        crime_columns = [c['name'] for c in inspector.get_columns('crime')]
        if 'daily_limit' not in crime_columns:
            with op.batch_alter_table('crime', schema=None) as batch_op:
                batch_op.add_column(sa.Column('daily_limit', sa.Integer(), nullable=True))

    # 2. Add daily_count and last_reset_date to UserCrimeCooldown
    if 'user_crime_cooldown' in tables:
        ucc_columns = [c['name'] for c in inspector.get_columns('user_crime_cooldown')]
        with op.batch_alter_table('user_crime_cooldown', schema=None) as batch_op:
            if 'daily_count' not in ucc_columns:
                batch_op.add_column(sa.Column('daily_count', sa.Integer(), nullable=True))
            if 'last_reset_date' not in ucc_columns:
                batch_op.add_column(sa.Column('last_reset_date', sa.Date(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'user_crime_cooldown' in tables:
        ucc_columns = [c['name'] for c in inspector.get_columns('user_crime_cooldown')]
        with op.batch_alter_table('user_crime_cooldown', schema=None) as batch_op:
            if 'last_reset_date' in ucc_columns:
                batch_op.drop_column('last_reset_date')
            if 'daily_count' in ucc_columns:
                batch_op.drop_column('daily_count')

    if 'crime' in tables:
        crime_columns = [c['name'] for c in inspector.get_columns('crime')]
        if 'daily_limit' in crime_columns:
            with op.batch_alter_table('crime', schema=None) as batch_op:
                batch_op.drop_column('daily_limit')
