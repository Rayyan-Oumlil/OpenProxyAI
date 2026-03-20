"""add admin audit logs table

Revision ID: d4e5f6a7b8c9
Revises: e6f7a8b9c0d1
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "d4e5f6a7b8c9"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("before", pg.JSONB, nullable=True),
        sa.Column("after", pg.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_audit_logs_org_created", "admin_audit_logs", ["org_id", "created_at"])
    op.create_index("ix_admin_audit_logs_actor", "admin_audit_logs", ["actor_id"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])

def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_action")
    op.drop_index("ix_admin_audit_logs_actor")
    op.drop_index("ix_admin_audit_logs_org_created")
    op.drop_table("admin_audit_logs")
