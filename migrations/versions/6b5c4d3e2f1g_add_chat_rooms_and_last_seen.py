"""add chat rooms and last seen

Revision ID: 6b5c4d3e2f1g
Revises: 5a4b3c2d1e0f
Create Date: 2026-01-13 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b5c4d3e2f1g'
down_revision = '5a4b3c2d1e0f'
branch_labels = None
depends_on = None


def upgrade():
    # Add room column to public_chat
    with op.batch_alter_table('public_chat', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'room',
                sa.String(
                    length=50),
                nullable=True,
                server_default='general'))
        batch_op.create_index(
            batch_op.f('ix_public_chat_room'),
            ['room'],
            unique=False)

    # Add last_seen column to user
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'last_seen',
                sa.DateTime(),
                nullable=True))
        batch_op.create_index(
            batch_op.f('ix_user_last_seen'),
            ['last_seen'],
            unique=False)


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_last_seen'))
        batch_op.drop_column('last_seen')

    with op.batch_alter_table('public_chat', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_public_chat_room'))
        batch_op.drop_column('room')
