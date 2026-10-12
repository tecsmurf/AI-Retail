"""Baseline: the v1 schema exactly as ``Base.metadata.create_all`` produced it.

Databases created by PurpleSol v1 (which called create_all at startup and had
no Alembic history) are *stamped* at this revision by ``python -m app.migrate``
and then upgraded, so their data is preserved.

Revision ID: 0001
Revises:
Create Date: 2026-10-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("layout_image_url", sa.Text(), nullable=True),
        sa.Column("layout_width", sa.Integer(), nullable=True),
        sa.Column("layout_height", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stores_store_code", "stores", ["store_code"], unique=True)

    op.create_table(
        "cameras",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("camera_type", sa.String(50), nullable=False),
        sa.Column("stream_url", sa.Text(), nullable=True),
        sa.Column("resolution_width", sa.Integer(), nullable=True),
        sa.Column("resolution_height", sa.Integer(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("position_on_layout", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_cameras_camera_code", "cameras", ["camera_code"])

    op.create_table(
        "zones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("zone_type", sa.String(50), nullable=False),
        sa.Column("is_revenue_zone", sa.Boolean(), nullable=False),
        sa.Column("polygon_points", sa.JSON(), nullable=True),
        sa.Column("camera_id", sa.Uuid(), sa.ForeignKey("cameras.id"), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_zones_zone_code", "zones", ["zone_code"])

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(100), nullable=False),
        sa.Column("camera_id", sa.String(100), nullable=True),
        sa.Column("zone_id", sa.String(100), nullable=True),
        sa.Column("zone_name", sa.String(200), nullable=True),
        sa.Column("zone_type", sa.String(50), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("bbox_x", sa.Float(), nullable=True),
        sa.Column("bbox_y", sa.Float(), nullable=True),
        sa.Column("bbox_w", sa.Float(), nullable=True),
        sa.Column("bbox_h", sa.Float(), nullable=True),
        sa.Column("hotspot_x", sa.Float(), nullable=True),
        sa.Column("hotspot_y", sa.Float(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("age_bucket", sa.String(20), nullable=True),
        sa.Column("is_staff", sa.Boolean(), nullable=False),
        sa.Column("queue_wait_seconds", sa.Float(), nullable=True),
        sa.Column("queue_position", sa.Integer(), nullable=True),
        sa.Column("queue_abandoned", sa.Boolean(), nullable=True),
        sa.Column("group_id", sa.String(50), nullable=True),
        sa.Column("group_size", sa.Integer(), nullable=True),
        sa.Column("dwell_seconds", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_events_store_id", "events", ["store_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_customer_id", "events", ["customer_id"])
    op.create_index("ix_events_timestamp", "events", ["timestamp"])
    op.create_index("ix_events_store_time", "events", ["store_id", "timestamp"])
    op.create_index("ix_events_store_type", "events", ["store_id", "event_type"])
    op.create_index("ix_events_customer", "events", ["store_id", "customer_id", "timestamp"])

    op.create_table(
        "customer_journeys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.String(100), nullable=False),
        sa.Column("entry_time", sa.DateTime(), nullable=False),
        sa.Column("exit_time", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("zones_visited", sa.JSON(), nullable=True),
        sa.Column("zone_count", sa.Integer(), nullable=False),
        sa.Column("total_dwell_seconds", sa.Float(), nullable=True),
        sa.Column("made_purchase", sa.Boolean(), nullable=False),
        sa.Column("visited_billing", sa.Boolean(), nullable=False),
        sa.Column("journey_type", sa.String(50), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("age_bucket", sa.String(20), nullable=True),
        sa.Column("pos_transaction_id", sa.String(100), nullable=True),
        sa.Column("purchase_amount", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_customer_journeys_store_id", "customer_journeys", ["store_id"])
    op.create_index("ix_customer_journeys_customer_id", "customer_journeys", ["customer_id"])
    op.create_index("ix_journeys_store_time", "customer_journeys", ["store_id", "entry_time"])

    op.create_table(
        "journey_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "journey_id", sa.Uuid(), sa.ForeignKey("customer_journeys.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("zone_name", sa.String(200), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("dwell_seconds", sa.Float(), nullable=True),
    )

    op.create_table(
        "pos_transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.String(50), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("order_time", sa.Time(), nullable=False),
        sa.Column("product_id", sa.String(50), nullable=False),
        sa.Column("brand_name", sa.String(200), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pos_transactions_order_id", "pos_transactions", ["order_id"])
    op.create_index("ix_pos_transactions_store_id", "pos_transactions", ["store_id"])
    op.create_index("ix_pos_store_date", "pos_transactions", ["store_id", "order_date"])

    op.create_table(
        "anomalies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("zone_name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("threshold_value", sa.Float(), nullable=True),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_anomalies_store_id", "anomalies", ["store_id"])
    op.create_index("ix_anomalies_anomaly_type", "anomalies", ["anomaly_type"])
    op.create_index("ix_anomalies_detected_at", "anomalies", ["detected_at"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("anomaly_id", sa.Uuid(), sa.ForeignKey("anomalies.id"), nullable=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_alerts_store_id", "alerts", ["store_id"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])


def downgrade() -> None:
    for table in (
        "alerts",
        "anomalies",
        "pos_transactions",
        "journey_events",
        "customer_journeys",
        "events",
        "zones",
        "cameras",
        "stores",
    ):
        op.drop_table(table)
