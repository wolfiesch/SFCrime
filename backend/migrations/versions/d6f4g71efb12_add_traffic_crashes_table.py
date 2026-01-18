"""Add traffic_crashes table.

Revision ID: d6f4g71efb12
Revises: c5e3f60dea01
Create Date: 2026-01-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "d6f4g71efb12"
down_revision: str | None = "c5e3f60dea01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "traffic_crashes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("unique_id", sa.String(length=20), nullable=False),
        sa.Column("case_id", sa.String(length=20), nullable=True),
        sa.Column("collision_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collision_severity", sa.String(length=100), nullable=True),
        sa.Column("type_of_collision", sa.String(length=100), nullable=True),
        sa.Column("number_killed", sa.Integer(), nullable=True),
        sa.Column("number_injured", sa.Integer(), nullable=True),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("primary_road", sa.String(length=100), nullable=True),
        sa.Column("secondary_road", sa.String(length=100), nullable=True),
        sa.Column("distance", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=True),
        sa.Column("weather", sa.String(length=50), nullable=True),
        sa.Column("road_surface", sa.String(length=50), nullable=True),
        sa.Column("road_condition", sa.String(length=100), nullable=True),
        sa.Column("lighting", sa.String(length=50), nullable=True),
        sa.Column("party1_type", sa.String(length=50), nullable=True),
        sa.Column("party2_type", sa.String(length=50), nullable=True),
        sa.Column("pedestrian_action", sa.String(length=100), nullable=True),
        sa.Column("neighborhood", sa.String(length=100), nullable=True),
        sa.Column("supervisor_district", sa.String(length=10), nullable=True),
        sa.Column("police_district", sa.String(length=50), nullable=True),
        sa.Column("reporting_district", sa.String(length=50), nullable=True),
        sa.Column("beat_number", sa.String(length=10), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("unique_id"),
        if_not_exists=True,
    )

    # Indexes
    op.create_index(
        "ix_traffic_crashes_severity",
        "traffic_crashes",
        ["collision_severity"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_traffic_crashes_type",
        "traffic_crashes",
        ["type_of_collision"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_traffic_crashes_neighborhood",
        "traffic_crashes",
        ["neighborhood"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_traffic_crashes_last_updated_at",
        "traffic_crashes",
        ["last_updated_at"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_traffic_crashes_location",
        "traffic_crashes",
        ["location"],
        postgresql_using="gist",
        if_not_exists=True,
    )
    op.create_index(
        "idx_traffic_crashes_cursor",
        "traffic_crashes",
        [sa.text("collision_datetime DESC"), sa.text("id DESC")],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_traffic_crashes_cursor", table_name="traffic_crashes", if_exists=True)
    op.drop_index("idx_traffic_crashes_location", table_name="traffic_crashes", if_exists=True)
    op.drop_index("ix_traffic_crashes_last_updated_at", table_name="traffic_crashes", if_exists=True)
    op.drop_index("ix_traffic_crashes_neighborhood", table_name="traffic_crashes", if_exists=True)
    op.drop_index("ix_traffic_crashes_type", table_name="traffic_crashes", if_exists=True)
    op.drop_index("ix_traffic_crashes_severity", table_name="traffic_crashes", if_exists=True)
    op.drop_table("traffic_crashes", if_exists=True)
