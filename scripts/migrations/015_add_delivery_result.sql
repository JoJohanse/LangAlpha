-- Add delivery_result column to automation_executions
ALTER TABLE automation_executions
    ADD COLUMN IF NOT EXISTS delivery_result JSONB;
