"""Add hostess AI memory and training flags

Revision ID: c91f8a3d2b10
Revises: bfefe2677f46
Create Date: 2025-12-27

"""

from alembic import op
import sqlalchemy as sa


revision = 'c91f8a3d2b10'
down_revision = 'bfefe2677f46'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    try:
        hostess_cols = {c["name"] for c in insp.get_columns("hostesses")}
    except Exception:
        hostess_cols = set()

    if "self_learning_enabled" not in hostess_cols:
        op.add_column("hostesses", sa.Column("self_learning_enabled", sa.Boolean(), server_default=sa.true(), nullable=True))
    if "memory_enabled" not in hostess_cols:
        op.add_column("hostesses", sa.Column("memory_enabled", sa.Boolean(), server_default=sa.true(), nullable=True))
    if "last_trained_at" not in hostess_cols:
        op.add_column("hostesses", sa.Column("last_trained_at", sa.DateTime(), nullable=True))

    existing_tables = set()
    try:
        existing_tables = set(insp.get_table_names())
    except Exception:
        existing_tables = set()

    if "hostess_chat_messages" not in existing_tables:
        op.create_table(
            "hostess_chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("hostess_id", sa.Integer(), sa.ForeignKey("hostesses.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        )

    existing_indexes = set()
    try:
        existing_indexes = {i["name"] for i in insp.get_indexes("hostess_chat_messages")}
    except Exception:
        existing_indexes = set()
    if "ix_hostess_chat_messages_hostess_id" not in existing_indexes:
        op.create_index("ix_hostess_chat_messages_hostess_id", "hostess_chat_messages", ["hostess_id"], unique=False)
    if "ix_hostess_chat_messages_user_id" not in existing_indexes:
        op.create_index("ix_hostess_chat_messages_user_id", "hostess_chat_messages", ["user_id"], unique=False)

    if "hostess_memories" not in existing_tables:
        op.create_table(
            "hostess_memories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("hostess_id", sa.Integer(), sa.ForeignKey("hostesses.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("importance", sa.Integer(), server_default="1", nullable=True),
            sa.Column("source", sa.String(length=16), server_default="auto", nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        )

    try:
        existing_indexes = {i["name"] for i in insp.get_indexes("hostess_memories")}
    except Exception:
        existing_indexes = set()
    if "ix_hostess_memories_hostess_id" not in existing_indexes:
        op.create_index("ix_hostess_memories_hostess_id", "hostess_memories", ["hostess_id"], unique=False)
    if "ix_hostess_memories_user_id" not in existing_indexes:
        op.create_index("ix_hostess_memories_user_id", "hostess_memories", ["user_id"], unique=False)
    if "ix_hostess_memories_key" not in existing_indexes:
        op.create_index("ix_hostess_memories_key", "hostess_memories", ["key"], unique=False)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set()
    try:
        tables = set(insp.get_table_names())
    except Exception:
        tables = set()

    if "hostess_memories" in tables:
        try:
            for idx in insp.get_indexes("hostess_memories"):
                if idx.get("name") in {"ix_hostess_memories_key", "ix_hostess_memories_user_id", "ix_hostess_memories_hostess_id"}:
                    op.drop_index(idx["name"], table_name="hostess_memories")
        except Exception:
            pass
        op.drop_table("hostess_memories")

    if "hostess_chat_messages" in tables:
        try:
            for idx in insp.get_indexes("hostess_chat_messages"):
                if idx.get("name") in {"ix_hostess_chat_messages_user_id", "ix_hostess_chat_messages_hostess_id"}:
                    op.drop_index(idx["name"], table_name="hostess_chat_messages")
        except Exception:
            pass
        op.drop_table("hostess_chat_messages")

    try:
        hostess_cols = {c["name"] for c in insp.get_columns("hostesses")}
    except Exception:
        hostess_cols = set()
    if "last_trained_at" in hostess_cols:
        op.drop_column("hostesses", "last_trained_at")
    if "memory_enabled" in hostess_cols:
        op.drop_column("hostesses", "memory_enabled")
    if "self_learning_enabled" in hostess_cols:
        op.drop_column("hostesses", "self_learning_enabled")
