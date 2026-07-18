"""editable notes and server-side annotations

Revision ID: 0002_editable_notes
Revises: 0001_initial
Create Date: 2026-07-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_editable_notes"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("results", sa.Column("bookmarks_json", sa.JSON(), nullable=True))
    op.add_column("results", sa.Column("highlights_json", sa.JSON(), nullable=True))
    op.add_column("results", sa.Column("memos_json", sa.JSON(), nullable=True))
    op.add_column("results", sa.Column("transcript_edited_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "transcript_edited_at")
    op.drop_column("results", "memos_json")
    op.drop_column("results", "highlights_json")
    op.drop_column("results", "bookmarks_json")
    op.drop_column("jobs", "title")
