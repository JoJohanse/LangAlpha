"""Add news tag snapshots and daily brief tables.

Revision ID: 012
Revises: 011
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS news_article_tags (
            article_id VARCHAR(128) PRIMARY KEY,
            title TEXT NOT NULL,
            article_url TEXT,
            source_name VARCHAR(255),
            published_at TIMESTAMPTZ,
            tickers JSONB NOT NULL DEFAULT '[]'::jsonb,
            sector VARCHAR(64),
            topic VARCHAR(64),
            region VARCHAR(64),
            tags JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_news_article_tags_published_at
        ON news_article_tags(published_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_news_article_tags_sector
        ON news_article_tags(sector)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_news_article_tags_topic
        ON news_article_tags(topic)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_briefs (
            brief_id UUID PRIMARY KEY,
            brief_date DATE NOT NULL,
            brief_type VARCHAR(16) NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            headline TEXT,
            content TEXT,
            error_message TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            generated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (brief_date, brief_type)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_daily_briefs_date_type
        ON daily_briefs(brief_date DESC, brief_type)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_daily_briefs_status
        ON daily_briefs(status)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS daily_briefs CASCADE")
    op.execute("DROP TABLE IF EXISTS news_article_tags CASCADE")

