from alembic import op
import sqlalchemy as sa


revision = '2c1c9b9e5e10'
down_revision = '1a2d7d8b3c9f'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    try:
        existing_cols = {c["name"] for c in inspector.get_columns("user")}
    except Exception:
        existing_cols = set()

    def ensure_column(col_name: str, column: sa.Column):
        if col_name in existing_cols:
            return
        op.add_column("user", column)
        existing_cols.add(col_name)

    ensure_column("jail_escape_attempts", sa.Column("jail_escape_attempts", sa.Integer(), server_default=sa.text("0"), nullable=True))
    ensure_column("jail_escape_attempts_date", sa.Column("jail_escape_attempts_date", sa.Date(), nullable=True))
    ensure_column("jail_escape_last_at", sa.Column("jail_escape_last_at", sa.DateTime(), nullable=True))
    ensure_column("jail_gilboa_attempts", sa.Column("jail_gilboa_attempts", sa.Integer(), server_default=sa.text("0"), nullable=True))
    ensure_column("jail_gilboa_attempts_date", sa.Column("jail_gilboa_attempts_date", sa.Date(), nullable=True))
    ensure_column("jail_gilboa_last_at", sa.Column("jail_gilboa_last_at", sa.DateTime(), nullable=True))
    ensure_column("gym_sessions_count", sa.Column("gym_sessions_count", sa.Integer(), server_default=sa.text("0"), nullable=True))
    ensure_column("gym_sessions_date", sa.Column("gym_sessions_date", sa.Date(), nullable=True))
    ensure_column("gym_speedups_count", sa.Column("gym_speedups_count", sa.Integer(), server_default=sa.text("0"), nullable=True))
    ensure_column("gym_speedups_date", sa.Column("gym_speedups_date", sa.Date(), nullable=True))

    ensure_column("organized_crime_cooldown_until", sa.Column("organized_crime_cooldown_until", sa.DateTime(), nullable=True))
    ensure_column("is_chat_banned", sa.Column("is_chat_banned", sa.Boolean(), server_default=sa.false(), nullable=True))
    ensure_column("failed_login_attempts", sa.Column("failed_login_attempts", sa.Integer(), server_default=sa.text("0"), nullable=True))
    ensure_column("locked_until", sa.Column("locked_until", sa.DateTime(), nullable=True))


def downgrade():
    pass

