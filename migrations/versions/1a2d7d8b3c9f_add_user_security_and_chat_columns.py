from alembic import op
import sqlalchemy as sa


revision = '1a2d7d8b3c9f'
down_revision = 'df0b9c1d8c7a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'failed_login_attempts',
                sa.Integer(),
                server_default=sa.text('0'),
                nullable=True))
        batch_op.add_column(
            sa.Column(
                'locked_until',
                sa.DateTime(),
                nullable=True))
        batch_op.add_column(
            sa.Column(
                'is_chat_banned',
                sa.Boolean(),
                server_default=sa.false(),
                nullable=True))
        batch_op.add_column(
            sa.Column(
                'organized_crime_cooldown_until',
                sa.DateTime(),
                nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('organized_crime_cooldown_until')
        batch_op.drop_column('is_chat_banned')
        batch_op.drop_column('locked_until')
        batch_op.drop_column('failed_login_attempts')
