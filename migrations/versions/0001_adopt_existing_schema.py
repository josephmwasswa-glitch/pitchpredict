"""Adopt the current PitchPredict schema and ensure fixtures.external_id is indexed uniquely.

Revision ID: 0001_adopt_existing_schema
Revises:
"""
from alembic import op
from sqlalchemy import inspect, text

from app import models  # noqa: F401
from app.database import Base

revision = "0001_adopt_existing_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("fixtures"):
        Base.metadata.create_all(bind=bind)
        return

    columns = {column["name"] for column in inspector.get_columns("fixtures")}
    if "external_id" not in columns:
        op.add_column("fixtures", __import__("sqlalchemy").Column("external_id", __import__("sqlalchemy").Integer(), nullable=True))

    inspector = inspect(bind)
    indexes = {
        item["name"]: item
        for item in inspector.get_indexes("fixtures")
        if item.get("name") == "ix_fixtures_external_id"
    }
    existing = indexes.get("ix_fixtures_external_id")
    if existing and existing.get("unique"):
        Base.metadata.create_all(bind=bind)
        return

    if existing:
        op.drop_index("ix_fixtures_external_id", table_name="fixtures")

    duplicates = bind.execute(text(
        "SELECT external_id FROM fixtures "
        "WHERE external_id IS NOT NULL "
        "GROUP BY external_id HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicates:
        raise RuntimeError(
            "Cannot create unique fixtures.external_id index: duplicate "
            f"external_id value {duplicates[0]!r} exists. Resolve duplicates first."
        )

    op.create_index(
        "ix_fixtures_external_id",
        "fixtures",
        ["external_id"],
        unique=True,
    )
    Base.metadata.create_all(bind=bind)


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("fixtures"):
        indexes = {item["name"] for item in inspector.get_indexes("fixtures")}
        if "ix_fixtures_external_id" in indexes:
            op.drop_index("ix_fixtures_external_id", table_name="fixtures")
    # Keep external_id and table data intact during downgrade.
