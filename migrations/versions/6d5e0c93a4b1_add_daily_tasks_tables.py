"""Add daily tasks tables

Revision ID: 6d5e0c93a4b1
Revises: c91f8a3d2b10
Create Date: 2025-12-27

"""

from alembic import op
import sqlalchemy as sa


revision = "6d5e0c93a4b1"
down_revision = "c91f8a3d2b10"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    try:
        tables = set(insp.get_table_names())
    except Exception:
        tables = set()

    if "daily_task" not in tables:
        op.create_table(
            "daily_task",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("description", sa.String(length=255), nullable=False),
            sa.Column("target_type", sa.String(length=50), nullable=False),
            sa.Column("target_count", sa.Integer(), server_default=sa.text("1"), nullable=True),
            sa.Column("reward_money", sa.Integer(), server_default=sa.text("0"), nullable=True),
            sa.Column("reward_exp", sa.Integer(), server_default=sa.text("0"), nullable=True),
            sa.Column("min_level", sa.Integer(), server_default=sa.text("1"), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=True),
        )

    existing_daily_indexes = set()
    try:
        existing_daily_indexes = {i["name"] for i in insp.get_indexes("daily_task")}
    except Exception:
        existing_daily_indexes = set()

    if "ix_daily_task_is_active" not in existing_daily_indexes:
        op.create_index("ix_daily_task_is_active", "daily_task", ["is_active"], unique=False)
    if "ix_daily_task_min_level" not in existing_daily_indexes:
        op.create_index("ix_daily_task_min_level", "daily_task", ["min_level"], unique=False)
    if "ix_daily_task_target_type" not in existing_daily_indexes:
        op.create_index("ix_daily_task_target_type", "daily_task", ["target_type"], unique=False)

    if "user_daily_task" not in tables:
        op.create_table(
            "user_daily_task",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("daily_task.id"), nullable=False),
            sa.Column("progress", sa.Integer(), server_default=sa.text("0"), nullable=True),
            sa.Column("is_completed", sa.Boolean(), server_default=sa.false(), nullable=True),
            sa.Column("date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=True),
        )

    existing_user_daily_indexes = set()
    try:
        existing_user_daily_indexes = {i["name"] for i in insp.get_indexes("user_daily_task")}
    except Exception:
        existing_user_daily_indexes = set()

    if "ix_user_daily_task_user_id" not in existing_user_daily_indexes:
        op.create_index("ix_user_daily_task_user_id", "user_daily_task", ["user_id"], unique=False)
    if "ix_user_daily_task_date" not in existing_user_daily_indexes:
        op.create_index("ix_user_daily_task_date", "user_daily_task", ["date"], unique=False)
    if "ix_user_daily_task_is_completed" not in existing_user_daily_indexes:
        op.create_index("ix_user_daily_task_is_completed", "user_daily_task", ["is_completed"], unique=False)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    try:
        tables = set(insp.get_table_names())
    except Exception:
        tables = set()

    if "user_daily_task" in tables:
        try:
            for idx in insp.get_indexes("user_daily_task"):
                if idx.get("name") in {
                    "ix_user_daily_task_user_id",
                    "ix_user_daily_task_date",
                    "ix_user_daily_task_is_completed",
                }:
                    op.drop_index(idx["name"], table_name="user_daily_task")
        except Exception:
            pass
        op.drop_table("user_daily_task")

    if "daily_task" in tables:
        try:
            for idx in insp.get_indexes("daily_task"):
                if idx.get("name") in {
                    "ix_daily_task_is_active",
                    "ix_daily_task_min_level",
                    "ix_daily_task_target_type",
                }:
                    op.drop_index(idx["name"], table_name="daily_task")
        except Exception:
            pass
        op.drop_table("daily_task")

