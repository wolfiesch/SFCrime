"""Add fire_calls table.

Revision ID: b4d2ef49cd9b
Revises: a3c1df38bc8a
Create Date: 2026-01-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "b4d2ef49cd9b"
down_revision: str | None = "a3c1df38bc8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fire_calls",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("incident_number", sa.String(length=20), nullable=False),
        sa.Column("call_type", sa.String(length=100), nullable=True),
        sa.Column("call_type_group", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.String(length=1), nullable=True),
        sa.Column("number_of_alarms", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("on_scene_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transport_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hospital_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disposition", sa.String(length=100), nullable=True),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("zipcode", sa.String(length=10), nullable=True),
        sa.Column("neighborhood", sa.String(length=100), nullable=True),
        sa.Column("supervisor_district", sa.String(length=10), nullable=True),
        sa.Column("battalion", sa.String(length=10), nullable=True),
        sa.Column("station_area", sa.String(length=10), nullable=True),
        sa.Column("unit_type", sa.String(length=20), nullable=True),
        sa.Column("is_als_unit", sa.Boolean(), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("incident_number"),
        if_not_exists=True,
    )

    # Indexes
    op.create_index(
        "ix_fire_calls_priority",
        "fire_calls",
        ["priority"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_fire_calls_neighborhood",
        "fire_calls",
        ["neighborhood"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_fire_calls_last_updated_at",
        "fire_calls",
        ["last_updated_at"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_fire_calls_location",
        "fire_calls",
        ["location"],
        postgresql_using="gist",
        if_not_exists=True,
    )
    op.create_index(
        "idx_fire_calls_cursor",
        "fire_calls",
        [sa.text("received_at DESC"), sa.text("id DESC")],
        if_not_exists=True,
    )
    op.create_index(
        "idx_fire_calls_type",
        "fire_calls",
        ["call_type"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_fire_calls_type", table_name="fire_calls", if_exists=True)
    op.drop_index("idx_fire_calls_cursor", table_name="fire_calls", if_exists=True)
    op.drop_index("idx_fire_calls_location", table_name="fire_calls", if_exists=True)
    op.drop_index(
        "ix_fire_calls_last_updated_at",
        table_name="fire_calls",
        if_exists=True,
    )
    op.drop_index("ix_fire_calls_neighborhood", table_name="fire_calls", if_exists=True)
    op.drop_index("ix_fire_calls_priority", table_name="fire_calls", if_exists=True)
    op.drop_table("fire_calls", if_exists=True)
