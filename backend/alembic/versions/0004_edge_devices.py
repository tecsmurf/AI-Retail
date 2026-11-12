"""In-store edge boxes: devices, live coverage, live occupancy samples.

``occupancy_samples.job_id`` becomes nullable: samples from a live stream do
not belong to a video-processing job. Downgrade deletes those live samples
(they cannot be represented in the older schema) and drops the edge tables;
events already received from boxes are kept.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edge_devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("pairing_code_hash", sa.String(64), nullable=True),
        sa.Column("pairing_expires_at", sa.DateTime(), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("hostname", sa.String(200), nullable=True),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_ip", sa.String(64), nullable=True),
        sa.Column("camera_status", sa.JSON(), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=True),
        sa.Column("snapshot_requests", sa.JSON(), nullable=True),
        sa.Column("events_received", sa.Integer(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("paired_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_edge_devices_token_hash"),
    )
    op.create_index("ix_edge_devices_org_id", "edge_devices", ["org_id"])
    op.create_index("ix_edge_devices_store_id", "edge_devices", ["store_id"])
    op.create_index("ix_edge_devices_pairing_code_hash", "edge_devices", ["pairing_code_hash"])

    op.create_table(
        "edge_coverage",
        sa.Column("camera_id", sa.Uuid(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("hour", sa.DateTime(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seconds", sa.Float(), nullable=False),
    )
    op.create_index("ix_edge_coverage_store_id", "edge_coverage", ["store_id"])

    with op.batch_alter_table("occupancy_samples") as b:
        b.alter_column("job_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM occupancy_samples WHERE job_id IS NULL")
    with op.batch_alter_table("occupancy_samples") as b:
        b.alter_column("job_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("ix_edge_coverage_store_id", table_name="edge_coverage")
    op.drop_table("edge_coverage")
    op.drop_index("ix_edge_devices_pairing_code_hash", table_name="edge_devices")
    op.drop_index("ix_edge_devices_store_id", table_name="edge_devices")
    op.drop_index("ix_edge_devices_org_id", table_name="edge_devices")
    op.drop_table("edge_devices")
