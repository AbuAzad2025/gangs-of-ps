"""Add user facilities

Revision ID: c2e7a9b0a3c4
Revises: 8c2a9f1e0d77
Create Date: 2025-12-27

"""

from alembic import op
import sqlalchemy as sa


revision = "c2e7a9b0a3c4"
down_revision = "8c2a9f1e0d77"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_facility",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("facility_key", sa.String(length=32), nullable=False),
        sa.Column("level", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )
    op.create_index("ix_user_facility_user_id", "user_facility", ["user_id"], unique=False)
    op.create_index("ix_user_facility_facility_key", "user_facility", ["facility_key"], unique=False)
    op.create_unique_constraint("uq_user_facility_user_key", "user_facility", ["user_id", "facility_key"])


def downgrade():
    op.drop_constraint("uq_user_facility_user_key", "user_facility", type_="unique")
    op.drop_index("ix_user_facility_facility_key", table_name="user_facility")
    op.drop_index("ix_user_facility_user_id", table_name="user_facility")
    op.drop_table("user_facility")

