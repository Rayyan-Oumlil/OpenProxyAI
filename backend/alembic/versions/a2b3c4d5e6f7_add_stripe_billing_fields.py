"""add_stripe_billing_fields

Revision ID: a2b3c4d5e6f7
Revises: f1a9c3e7d5b2
Create Date: 2026-03-19 00:00:00.000000

Adds Stripe billing columns to organizations and creates the stripe_events
idempotency table to prevent duplicate webhook processing.
"""

from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "f1a9c3e7d5b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add Stripe fields to organizations — all nullable (free orgs never subscribe)
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("stripe_subscription_id", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("stripe_subscription_status", sa.String(50), nullable=True))
    op.create_unique_constraint("uq_organizations_stripe_customer_id", "organizations", ["stripe_customer_id"])
    op.create_unique_constraint("uq_organizations_stripe_subscription_id", "organizations", ["stripe_subscription_id"])

    # Create idempotency table for processed Stripe webhook events
    op.create_table(
        "stripe_events",
        sa.Column("id", sa.dialects.postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_stripe_events_event_id"),
    )
    op.create_index("ix_stripe_events_event_id", "stripe_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_stripe_events_event_id", table_name="stripe_events")
    op.drop_table("stripe_events")
    op.drop_constraint("uq_organizations_stripe_subscription_id", "organizations", type_="unique")
    op.drop_constraint("uq_organizations_stripe_customer_id", "organizations", type_="unique")
    op.drop_column("organizations", "stripe_subscription_status")
    op.drop_column("organizations", "stripe_subscription_id")
    op.drop_column("organizations", "stripe_customer_id")
