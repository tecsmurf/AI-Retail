"""Chains: organisations, regions, per-user store access, audit log.

Everything that exists before this migration (stores, users, POS rows) is put
in one default organisation, so a single-company install keeps working with no
manual step. Store codes and POS lines become unique per organisation instead
of globally.

Downgrade removes the organisation columns again. Users with the two roles
that only exist from this revision (regional_manager, store_manager) are set
to ``viewer``. If two organisations hold the same store code or POS line the
downgrade fails on the old unique rules rather than deleting anything.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11
"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    orgs = op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.bulk_insert(orgs, [{"id": DEFAULT_ORG_ID, "name": "Default organisation", "slug": "default",
                           "created_at": _now()}])

    op.create_table(
        "regions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_regions_org_name"),
    )
    op.create_index("ix_regions_org_id", "regions", ["org_id"])

    # Add org_id as nullable, backfill, then make it required. (A server
    # default would differ per database: SQLite stores UUIDs as 32 hex chars.)
    for table in ("users", "stores", "pos_transactions"):
        with op.batch_alter_table(table) as b:
            b.add_column(sa.Column("org_id", sa.Uuid(), nullable=True))
        t = sa.table(table, sa.column("org_id", sa.Uuid()))
        op.execute(t.update().values(org_id=DEFAULT_ORG_ID))

    with op.batch_alter_table("users") as b:
        b.alter_column("org_id", existing_type=sa.Uuid(), nullable=False)
        b.create_foreign_key("fk_users_org_id", "organizations", ["org_id"], ["id"], ondelete="CASCADE")
        b.create_index("ix_users_org_id", ["org_id"])
        b.add_column(sa.Column("full_name", sa.String(200), nullable=True))
        b.alter_column("role", existing_type=sa.String(20), type_=sa.String(32), existing_nullable=False)

    with op.batch_alter_table("stores") as b:
        b.alter_column("org_id", existing_type=sa.Uuid(), nullable=False)
        b.create_foreign_key("fk_stores_org_id", "organizations", ["org_id"], ["id"], ondelete="CASCADE")
        b.create_index("ix_stores_org_id", ["org_id"])
        b.add_column(sa.Column("region_id", sa.Uuid(), nullable=True))
        b.create_foreign_key("fk_stores_region_id", "regions", ["region_id"], ["id"], ondelete="SET NULL")
        b.create_index("ix_stores_region_id", ["region_id"])
        b.drop_index("ix_stores_store_code")
        b.create_index("ix_stores_store_code", ["store_code"])
        b.create_unique_constraint("uq_stores_org_code", ["org_id", "store_code"])

    with op.batch_alter_table("pos_transactions") as b:
        b.alter_column("org_id", existing_type=sa.Uuid(), nullable=False)
        b.create_foreign_key("fk_pos_transactions_org_id", "organizations", ["org_id"], ["id"], ondelete="CASCADE")
        b.create_index("ix_pos_transactions_org_id", ["org_id"])
        b.drop_constraint("uq_pos_line", type_="unique")
        b.create_unique_constraint("uq_pos_line", ["org_id", "store_id", "order_id", "product_id"])

    op.create_table(
        "user_store_access",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "user_region_access",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("region_id", sa.Uuid(), sa.ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor", sa.String(320), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=True),
        sa.Column("target_id", sa.String(80), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("user_region_access")
    op.drop_table("user_store_access")

    with op.batch_alter_table("pos_transactions") as b:
        b.drop_constraint("uq_pos_line", type_="unique")
        b.drop_index("ix_pos_transactions_org_id")
        b.drop_constraint("fk_pos_transactions_org_id", type_="foreignkey")
        b.drop_column("org_id")
        b.create_unique_constraint("uq_pos_line", ["store_id", "order_id", "product_id"])

    with op.batch_alter_table("stores") as b:
        b.drop_constraint("uq_stores_org_code", type_="unique")
        b.drop_index("ix_stores_store_code")
        b.drop_index("ix_stores_region_id")
        b.drop_index("ix_stores_org_id")
        b.drop_constraint("fk_stores_region_id", type_="foreignkey")
        b.drop_constraint("fk_stores_org_id", type_="foreignkey")
        b.drop_column("region_id")
        b.drop_column("org_id")
        b.create_index("ix_stores_store_code", ["store_code"], unique=True)

    users = sa.table("users", sa.column("role", sa.String()))
    op.execute(users.update().where(users.c.role.in_(["regional_manager", "store_manager"])).values(role="viewer"))
    with op.batch_alter_table("users") as b:
        b.drop_index("ix_users_org_id")
        b.drop_constraint("fk_users_org_id", type_="foreignkey")
        b.drop_column("full_name")
        b.drop_column("org_id")
        b.alter_column("role", existing_type=sa.String(32), type_=sa.String(20), existing_nullable=False)

    op.drop_index("ix_regions_org_id", table_name="regions")
    op.drop_table("regions")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
