"""Widen market_insights.model from VARCHAR(10) to VARCHAR(100).

Model names like "qwen3.5-flash" (13 chars), "qwen3.6-plus" (12 chars),
and "DeepSeek-V4-Flash" (17 chars) exceed the original VARCHAR(10).

Revision ID: 014
Revises: 013
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE market_insights
        ALTER COLUMN model TYPE VARCHAR(100)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE market_insights
        ALTER COLUMN model TYPE VARCHAR(10)
        USING LEFT(model, 10)
    """)
