"""Update user health scaling

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-01

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def upgrade():
    # Update max_health for all users
    # Base: 30000, Increment: 3000 per level (level 1 = 30000)
    # Formula: 30000 + (level - 1) * 3000
    # "user" is a reserved keyword in Postgres, must be quoted
    op.execute('UPDATE "user" SET max_health = 30000 + (level - 1) * 3000')
    
    # Heal all users to new max_health
    op.execute('UPDATE "user" SET health = max_health')

def downgrade():
    # Revert to old scaling
    # Base: 100, Increment: 10
    op.execute('UPDATE "user" SET max_health = 100 + (level - 1) * 10')
    # Cap health at new max_health
    op.execute('UPDATE "user" SET health = CASE WHEN health > max_health THEN max_health ELSE health END')
