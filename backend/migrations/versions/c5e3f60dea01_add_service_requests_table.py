"""Add service_requests table.

Revision ID: c5e3f60dea01
Revises: b4d2ef49cd9b
Create Date: 2026-01-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "c5e3f60dea01"
down_revision: str | None = "b4d2ef49cd9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("service_request_id", sa.String(length=20), nullable=False),
        sa.Column("service_name", sa.String(length=100), nullable=True),
        sa.Column("service_subtype", sa.String(length=100), nullable=True),
        sa.Column("service_details", sa.String(length=255), nullable=True),
        sa.Column("status_description", sa.String(length=50), nullable=True),
        sa.Column("status_notes", sa.Text(), nullable=True),
        sa.Column("agency_responsible", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("street", sa.String(length=100), nullable=True),
        sa.Column("neighborhood", sa.String(length=100), nullable=True),
        sa.Column("supervisor_district", sa.String(length=10), nullable=True),
        sa.Column("police_district", sa.String(length=50), nullable=True),
        sa.Column("media_url", sa.String(length=512), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("service_request_id"),
        if_not_exists=True,
    )

    # Indexes
    op.create_index(
        "ix_service_requests_service_name",
        "service_requests",
        ["service_name"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_service_requests_status",
        "service_requests",
        ["status_description"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_service_requests_neighborhood",
        "service_requests",
        ["neighborhood"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_service_requests_last_updated_at",
        "service_requests",
        ["last_updated_at"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_service_requests_location",
        "service_requests",
        ["location"],
        postgresql_using="gist",
        if_not_exists=True,
    )
    op.create_index(
        "idx_service_requests_cursor",
        "service_requests",
        [sa.text("requested_at DESC"), sa.text("id DESC")],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_service_requests_cursor", table_name="service_requests", if_exists=True)
    op.drop_index("idx_service_requests_location", table_name="service_requests", if_exists=True)
    op.drop_index("ix_service_requests_last_updated_at", table_name="service_requests", if_exists=True)
    op.drop_index("ix_service_requests_neighborhood", table_name="service_requests", if_exists=True)
    op.drop_index("ix_service_requests_status", table_name="service_requests", if_exists=True)
    op.drop_index("ix_service_requests_service_name", table_name="service_requests", if_exists=True)
    op.drop_table("service_requests", if_exists=True)
