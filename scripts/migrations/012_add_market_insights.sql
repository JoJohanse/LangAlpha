-- 012: Add market_insights table for AI-generated market insight reports
-- Generated insights are stored here and served via /api/v1/insights/*

CREATE TABLE IF NOT EXISTS market_insights (
    market_insight_id UUID PRIMARY KEY,
    user_id          UUID,           -- NULL = system-generated global insight; non-NULL = user-generated (future)
    type             VARCHAR(30) NOT NULL DEFAULT 'daily_brief',  -- daily_brief, sector_analysis, etc. (extensible)
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',      -- pending, generating, completed, failed
    headline         TEXT,
    summary          TEXT,
    content          JSONB,          -- [{title, body}] curated news items
    topics           JSONB,          -- [{text, trend}]
    sources          JSONB,          -- [{title, url}] from Tavily
    model            VARCHAR(10),    -- mini, pro, auto
    error_message    TEXT,
    generation_time_ms INTEGER,
    metadata         JSONB,          -- extensible metadata (instruction used, schema version, etc.)
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at     TIMESTAMPTZ
);

-- Fast lookup for "get latest completed global insight by type"
CREATE INDEX IF NOT EXISTS idx_market_insights_latest
    ON market_insights (type, created_at DESC)
    WHERE status = 'completed' AND user_id IS NULL;

-- Future: per-user insights lookup
CREATE INDEX IF NOT EXISTS idx_market_insights_user
    ON market_insights (user_id, type, created_at DESC)
    WHERE status = 'completed' AND user_id IS NOT NULL;
