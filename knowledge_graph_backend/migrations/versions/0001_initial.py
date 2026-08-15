"""Initial evidence, review, snapshot, and graph-version schema.

Revision ID: 0001_initial
Revises: None
"""
from alembic import op

from app import models  # noqa: F401
from app.database import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The metadata is the versioned schema at this initial revision. Future
    # revisions must use explicit operations and must not modify this revision.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

