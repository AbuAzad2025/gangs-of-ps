"""Add factory jobs

Revision ID: 4b2d6c1e3f10
Revises: 6d5e0c93a4b1
Create Date: 2025-12-27

"""

from alembic import op
import sqlalchemy as sa


revision = "4b2d6c1e3f10"
down_revision = "6d5e0c93a4b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "factory_job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("metal_used", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("diamonds_used", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("output_amount", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="running", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_factory_job_user_id", "factory_job", ["user_id"], unique=False)
    op.create_index("ix_factory_job_status", "factory_job", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_factory_job_status", table_name="factory_job")
    op.drop_index("ix_factory_job_user_id", table_name="factory_job")
    op.drop_table("factory_job")

