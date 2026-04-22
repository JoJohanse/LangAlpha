"""Add market event tables for phase1 MVP.

Revision ID: 010
Revises: 009
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS market_events (
            event_id UUID PRIMARY KEY,
            title TEXT NOT NULL,
            short_summary TEXT,
            importance_score NUMERIC(5,2) NOT NULL DEFAULT 0,
            sentiment VARCHAR(20),
            start_time TIMESTAMPTZ,
            primary_symbol VARCHAR(32),
            symbols JSONB NOT NULL DEFAULT '[]'::jsonb,
            tags JSONB NOT NULL DEFAULT '[]'::jsonb,
            article_count INT NOT NULL DEFAULT 0,
            ai_takeaway TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_events_start_time
        ON market_events(start_time DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_events_importance
        ON market_events(importance_score DESC, start_time DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_events_primary_symbol
        ON market_events(primary_symbol)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS market_event_articles (
            event_id UUID NOT NULL REFERENCES market_events(event_id) ON DELETE CASCADE,
            article_id VARCHAR(128) NOT NULL,
            relevance_score NUMERIC(5,2),
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (event_id, article_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_event_articles_article_id
        ON market_event_articles(article_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS symbol_event_links (
            event_id UUID NOT NULL REFERENCES market_events(event_id) ON DELETE CASCADE,
            symbol VARCHAR(32) NOT NULL,
            event_time TIMESTAMPTZ NOT NULL,
            impact_direction VARCHAR(20),
            impact_score NUMERIC(5,2),
            display_title TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (event_id, symbol)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_symbol_event_links_symbol_time
        ON symbol_event_links(symbol, event_time DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS symbol_event_links CASCADE")
    op.execute("DROP TABLE IF EXISTS market_event_articles CASCADE")
    op.execute("DROP TABLE IF EXISTS market_events CASCADE")
