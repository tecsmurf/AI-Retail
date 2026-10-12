"""v2: users, durable jobs, video assets, provenance and idempotency keys.

Existing rows are preserved. Derived/provenance fields are backfilled:

* ``events.source``: ``demo`` for the v1 random seed (``DEMO_*`` ids),
  ``legacy_cv`` for events imported from the v1 ``cv_events.jsonl``,
  ``sample`` for the bundled sample JSONL (``ID_*`` ids or ``PURPLLE_MUM_*``
  zone ids), ``api`` otherwise.
* ``customer_journeys.made_purchase`` is reset to false where no POS
  transaction was linked (v1 set it from "visited billing", which is not proof
  of a purchase).
* ``pos_transactions.ordered_at_utc`` is computed from the local order date
  and time assuming Asia/Kolkata (all v1 stores are in Mumbai).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""
from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    with op.batch_alter_table("stores") as b:
        b.add_column(sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"))
        b.add_column(sa.Column("pos_store_code", sa.String(50), nullable=True))
        b.create_index("ix_stores_pos_store_code", ["pos_store_code"])

    with op.batch_alter_table("cameras") as b:
        b.add_column(sa.Column("entry_line", sa.JSON(), nullable=True))
        b.add_column(sa.Column("reference_frame_key", sa.String(500), nullable=True))
        b.add_column(sa.Column("reference_frame_width", sa.Integer(), nullable=True))
        b.add_column(sa.Column("reference_frame_height", sa.Integer(), nullable=True))
        b.add_column(sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"))
        b.create_index("ix_cameras_store_id", ["store_id"])
        b.create_unique_constraint("uq_cameras_store_code", ["store_id", "camera_code"])

    with op.batch_alter_table("zones") as b:
        b.add_column(sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        b.create_index("ix_zones_store_id", ["store_id"])
        b.create_index("ix_zones_camera_id", ["camera_id"])

    op.create_table(
        "video_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", sa.Uuid(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(300), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("recorded_start", sa.DateTime(), nullable=True),
        sa.Column("recorded_start_assumed", sa.Boolean(), nullable=False),
        sa.Column("probe", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_video_assets_store_id", "video_assets", ["store_id"])
    op.create_index("ix_video_assets_camera_id", "video_assets", ["camera_id"])
    op.create_index("ix_video_assets_status", "video_assets", ["status"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", sa.Uuid(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_id", sa.Uuid(), sa.ForeignKey("video_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("stage", sa.String(50), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_by", sa.String(200), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("model_sha256", sa.String(64), nullable=True),
        sa.Column("pipeline_version", sa.String(20), nullable=True),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("artifacts", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_processing_jobs_store_id", "processing_jobs", ["store_id"])
    op.create_index("ix_processing_jobs_camera_id", "processing_jobs", ["camera_id"])
    op.create_index("ix_processing_jobs_video_id", "processing_jobs", ["video_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_index("ix_jobs_status_created", "processing_jobs", ["status", "created_at"])

    op.create_table(
        "occupancy_samples",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "job_id", sa.Uuid(), sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("camera_code", sa.String(50), nullable=False),
        sa.Column("zone_name", sa.String(200), nullable=False),
        sa.Column("zone_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_occupancy_samples_store_id", "occupancy_samples", ["store_id"])
    op.create_index("ix_occupancy_samples_job_id", "occupancy_samples", ["job_id"])
    op.create_index("ix_occupancy_store_zone_ts", "occupancy_samples", ["store_id", "zone_name", "timestamp"])

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(200), primary_key=True),
        sa.Column("hostname", sa.String(200), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("current_job_id", sa.Uuid(), nullable=True),
        sa.Column("model_loaded", sa.Boolean(), nullable=False),
        sa.Column("model_error", sa.Text(), nullable=True),
        sa.Column("device", sa.String(50), nullable=True),
        sa.Column("rss_mb", sa.Float(), nullable=True),
        sa.Column("jobs_completed", sa.Integer(), nullable=False),
        sa.Column("jobs_failed", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(50), nullable=True),
    )

    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("source", sa.String(20), nullable=False, server_default="api"))
        b.add_column(sa.Column("event_key", sa.String(80), nullable=True))
        b.add_column(sa.Column("job_id", sa.Uuid(), nullable=True))
        b.add_column(sa.Column("track_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("video_offset_seconds", sa.Float(), nullable=True))
        b.create_index("ix_events_source", ["source"])
        b.create_index("ix_events_job_id", ["job_id"])
        b.create_unique_constraint("uq_events_store_event_key", ["store_id", "event_key"])
        b.create_foreign_key(
            "fk_events_job_id", "processing_jobs", ["job_id"], ["id"], ondelete="CASCADE"
        )

    events = sa.table(
        "events",
        sa.column("customer_id", sa.String),
        sa.column("zone_id", sa.String),
        sa.column("source", sa.String),
    )
    # Bundled sample JSONL: zone/queue events reference "PURPLLE_MUM_*" zone ids.
    op.execute(
        events.update().where(events.c.zone_id.like("PURPLLE\\_MUM\\_%", escape="\\")).values(source="sample")
    )
    op.execute(events.update().where(events.c.customer_id.like("DEMO\\_%", escape="\\")).values(source="demo"))
    op.execute(
        events.update()
        .where(events.c.customer_id.like("store\\_%\\_CAM%\\_T%", escape="\\"))
        .values(source="legacy_cv")
    )
    op.execute(events.update().where(events.c.customer_id.like("ID\\_%", escape="\\")).values(source="sample"))

    with op.batch_alter_table("customer_journeys") as b:
        b.add_column(sa.Column("job_id", sa.Uuid(), nullable=True))
        b.add_column(sa.Column("camera_id", sa.String(100), nullable=True))
        b.add_column(sa.Column("source", sa.String(20), nullable=False, server_default="cv"))
        b.add_column(sa.Column("observed_entry", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("observed_exit", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.create_index("ix_customer_journeys_job_id", ["job_id"])
        b.create_index("ix_customer_journeys_source", ["source"])
        b.create_foreign_key(
            "fk_customer_journeys_job_id", "processing_jobs", ["job_id"], ["id"], ondelete="CASCADE"
        )
    journeys = sa.table(
        "customer_journeys",
        sa.column("made_purchase", sa.Boolean),
        sa.column("pos_transaction_id", sa.String),
        sa.column("source", sa.String),
    )
    op.execute(
        journeys.update().where(journeys.c.pos_transaction_id.is_(None)).values(made_purchase=False)
    )
    op.execute(journeys.update().values(source="legacy_cv"))

    with op.batch_alter_table("journey_events") as b:
        b.create_index("ix_journey_events_journey_id", ["journey_id"])

    with op.batch_alter_table("pos_transactions") as b:
        b.add_column(sa.Column("ordered_at_utc", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("source", sa.String(20), nullable=False, server_default="api"))
        b.create_index("ix_pos_transactions_ordered_at_utc", ["ordered_at_utc"])
        b.create_unique_constraint("uq_pos_line", ["store_id", "order_id", "product_id"])

    conn = op.get_bind()
    pos = sa.table(
        "pos_transactions",
        sa.column("id", sa.Uuid),
        sa.column("order_date", sa.Date),
        sa.column("order_time", sa.Time),
        sa.column("ordered_at_utc", sa.DateTime),
    )
    ist = timedelta(hours=5, minutes=30)
    rows = conn.execute(sa.select(pos.c.id, pos.c.order_date, pos.c.order_time)).all()
    for row in rows:
        local = datetime.combine(row.order_date, row.order_time)
        conn.execute(pos.update().where(pos.c.id == row.id).values(ordered_at_utc=local - ist))

    with op.batch_alter_table("anomalies") as b:
        b.add_column(sa.Column("dedupe_key", sa.String(200), nullable=True))
        b.create_unique_constraint("uq_anomalies_dedupe", ["store_id", "dedupe_key"])


def downgrade() -> None:
    with op.batch_alter_table("anomalies") as b:
        b.drop_constraint("uq_anomalies_dedupe", type_="unique")
        b.drop_column("dedupe_key")
    with op.batch_alter_table("pos_transactions") as b:
        b.drop_constraint("uq_pos_line", type_="unique")
        b.drop_index("ix_pos_transactions_ordered_at_utc")
        b.drop_column("source")
        b.drop_column("ordered_at_utc")
    with op.batch_alter_table("journey_events") as b:
        b.drop_index("ix_journey_events_journey_id")
    with op.batch_alter_table("customer_journeys") as b:
        b.drop_constraint("fk_customer_journeys_job_id", type_="foreignkey")
        b.drop_index("ix_customer_journeys_source")
        b.drop_index("ix_customer_journeys_job_id")
        for col in ("observed_exit", "observed_entry", "source", "camera_id", "job_id"):
            b.drop_column(col)
    with op.batch_alter_table("events") as b:
        b.drop_constraint("fk_events_job_id", type_="foreignkey")
        b.drop_constraint("uq_events_store_event_key", type_="unique")
        b.drop_index("ix_events_job_id")
        b.drop_index("ix_events_source")
        for col in ("video_offset_seconds", "track_id", "job_id", "event_key", "source"):
            b.drop_column(col)
    op.drop_table("worker_heartbeats")
    op.drop_table("occupancy_samples")
    op.drop_table("processing_jobs")
    op.drop_table("video_assets")
    with op.batch_alter_table("zones") as b:
        b.drop_index("ix_zones_camera_id")
        b.drop_index("ix_zones_store_id")
        b.drop_column("updated_at")
        b.drop_column("priority")
    with op.batch_alter_table("cameras") as b:
        b.drop_constraint("uq_cameras_store_code", type_="unique")
        b.drop_index("ix_cameras_store_id")
        for col in ("config_version", "reference_frame_height", "reference_frame_width",
                    "reference_frame_key", "entry_line"):
            b.drop_column(col)
    with op.batch_alter_table("stores") as b:
        b.drop_index("ix_stores_pos_store_code")
        b.drop_column("pos_store_code")
        b.drop_column("timezone")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
