"""Initial schema for SFCrime.

Revision ID: a3c1df38bc8a
Revises: None
Create Date: 2026-01-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "a3c1df38bc8a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _location_udt_name(bind: sa.Connection, table_name: str) -> str | None:
    return bind.execute(
        sa.text(
            "SELECT udt_name "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = :table_name "
            "AND column_name = 'location'"
        ),
        {"table_name": table_name},
    ).scalar_one_or_none()


def upgrade() -> None:
    # PostGIS is required for Geometry columns.
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))

    op.create_table(
        "sync_checkpoints",
        sa.Column("source", sa.String(length=50), primary_key=True, nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_sync_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("record_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        if_not_exists=True,
    )

    op.create_table(
        "dispatch_calls",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("cad_number", sa.String(length=20), nullable=False),
        sa.Column("call_type_code", sa.String(length=20), nullable=True),
        sa.Column("call_type_description", sa.String(length=255), nullable=True),
        sa.Column("priority", sa.String(length=1), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("on_scene_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("district", sa.String(length=50), nullable=True),
        sa.Column("disposition", sa.String(length=20), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("cad_number"),
        if_not_exists=True,
    )

    op.create_table(
        "incident_reports",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.String(length=20), nullable=False),
        sa.Column("incident_number", sa.String(length=20), nullable=True),
        sa.Column("incident_category", sa.String(length=100), nullable=True),
        sa.Column("incident_subcategory", sa.String(length=100), nullable=True),
        sa.Column("incident_description", sa.String(length=500), nullable=True),
        sa.Column("resolution", sa.String(length=100), nullable=True),
        sa.Column("incident_date", sa.Date(), nullable=True),
        sa.Column("incident_time", sa.Time(), nullable=True),
        sa.Column("report_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("police_district", sa.String(length=50), nullable=True),
        sa.Column("analysis_neighborhood", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("incident_id"),
        if_not_exists=True,
    )

    bind = op.get_bind()

    # If an older schema used geography columns, upgrade them in-place to geometry.
    if _location_udt_name(bind, "dispatch_calls") == "geography":
        op.drop_index("idx_calls_location", table_name="dispatch_calls", if_exists=True)
        op.alter_column(
            "dispatch_calls",
            "location",
            type_=Geometry("POINT", srid=4326),
            postgresql_using="ST_SetSRID(location::geometry, 4326)",
        )
        op.create_index(
            "idx_calls_location",
            "dispatch_calls",
            ["location"],
            postgresql_using="gist",
            if_not_exists=True,
        )

    if _location_udt_name(bind, "incident_reports") == "geography":
        op.drop_index("idx_reports_location", table_name="incident_reports", if_exists=True)
        op.alter_column(
            "incident_reports",
            "location",
            type_=Geometry("POINT", srid=4326),
            postgresql_using="ST_SetSRID(location::geometry, 4326)",
        )
        op.create_index(
            "idx_reports_location",
            "incident_reports",
            ["location"],
            postgresql_using="gist",
            if_not_exists=True,
        )

    # Indexes - dispatch calls
    op.create_index(
        "ix_dispatch_calls_priority",
        "dispatch_calls",
        ["priority"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_dispatch_calls_district",
        "dispatch_calls",
        ["district"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_dispatch_calls_last_updated_at",
        "dispatch_calls",
        ["last_updated_at"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_calls_location",
        "dispatch_calls",
        ["location"],
        postgresql_using="gist",
        if_not_exists=True,
    )
    op.create_index(
        "idx_calls_cursor",
        "dispatch_calls",
        [sa.text("received_at DESC"), sa.text("id DESC")],
        if_not_exists=True,
    )

    # Indexes - incident reports
    op.create_index(
        "ix_incident_reports_incident_category",
        "incident_reports",
        ["incident_category"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_incident_reports_incident_date",
        "incident_reports",
        ["incident_date"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_incident_reports_police_district",
        "incident_reports",
        ["police_district"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_reports_location",
        "incident_reports",
        ["location"],
        postgresql_using="gist",
        if_not_exists=True,
    )
    op.create_index(
        "idx_reports_cursor",
        "incident_reports",
        [sa.text("report_datetime DESC"), sa.text("id DESC")],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_reports_cursor", table_name="incident_reports", if_exists=True)
    op.drop_index("idx_reports_location", table_name="incident_reports", if_exists=True)
    op.drop_index(
        "ix_incident_reports_police_district",
        table_name="incident_reports",
        if_exists=True,
    )
    op.drop_index(
        "ix_incident_reports_incident_date",
        table_name="incident_reports",
        if_exists=True,
    )
    op.drop_index(
        "ix_incident_reports_incident_category", table_name="incident_reports", if_exists=True
    )

    op.drop_index("idx_calls_cursor", table_name="dispatch_calls", if_exists=True)
    op.drop_index("idx_calls_location", table_name="dispatch_calls", if_exists=True)
    op.drop_index(
        "ix_dispatch_calls_last_updated_at",
        table_name="dispatch_calls",
        if_exists=True,
    )
    op.drop_index("ix_dispatch_calls_district", table_name="dispatch_calls", if_exists=True)
    op.drop_index("ix_dispatch_calls_priority", table_name="dispatch_calls", if_exists=True)

    op.drop_table("incident_reports", if_exists=True)
    op.drop_table("dispatch_calls", if_exists=True)
    op.drop_table("sync_checkpoints", if_exists=True)
