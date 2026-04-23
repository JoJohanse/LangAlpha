"""Add snapshot fields to market_event_articles.

Revision ID: 011
Revises: 010
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE market_event_articles
        ADD COLUMN IF NOT EXISTS title TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE market_event_articles
        ADD COLUMN IF NOT EXISTS article_url TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE market_event_articles
        ADD COLUMN IF NOT EXISTS source_name VARCHAR(255)
        """
    )
    op.execute(
        """
        ALTER TABLE market_event_articles
        ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE market_event_articles
        DROP COLUMN IF EXISTS published_at
        """
    )
    op.execute(
        """
        ALTER TABLE market_event_articles
        DROP COLUMN IF EXISTS source_name
        """
    )
    op.execute(
        """
        ALTER TABLE market_event_articles
        DROP COLUMN IF EXISTS article_url
        """
    )
    op.execute(
        """
        ALTER TABLE market_event_articles
        DROP COLUMN IF EXISTS title
        """
    )
