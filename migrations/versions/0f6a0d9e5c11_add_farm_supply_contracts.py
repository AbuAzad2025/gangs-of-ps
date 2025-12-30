"""Add farm supply contracts

Revision ID: 0f6a0d9e5c11
Revises: c2e7a9b0a3c4
Create Date: 2025-12-27

"""

from alembic import op
import sqlalchemy as sa


revision = "0f6a0d9e5c11"
down_revision = "c2e7a9b0a3c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "farm_supply_contract",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("location.id"), nullable=False),
        sa.Column("bonus_percent", sa.Float(), server_default=sa.text("0.1"), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_farm_supply_contract_user_id", "farm_supply_contract", ["user_id"], unique=False)
    op.create_index("ix_farm_supply_contract_location_id", "farm_supply_contract", ["location_id"], unique=False)
    op.create_index("ix_farm_supply_contract_status", "farm_supply_contract", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_farm_supply_contract_status", table_name="farm_supply_contract")
    op.drop_index("ix_farm_supply_contract_location_id", table_name="farm_supply_contract")
    op.drop_index("ix_farm_supply_contract_user_id", table_name="farm_supply_contract")
    op.drop_table("farm_supply_contract")

