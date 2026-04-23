"""Drop standalone daily_briefs table (migrate to insight-based daily sessions).

Revision ID: 013
Revises: 012
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS daily_briefs CASCADE")


def downgrade() -> None:
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
