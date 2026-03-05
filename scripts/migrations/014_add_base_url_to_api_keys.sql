-- Add base_url column to user_api_keys for BYOK custom endpoint support.
-- Plain TEXT (not encrypted) — URLs aren't secrets.
ALTER TABLE user_api_keys ADD COLUMN IF NOT EXISTS base_url TEXT;
