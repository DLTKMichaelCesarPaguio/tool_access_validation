-- Add unique constraint on (tool_id, work_email) to enable ON CONFLICT upserts.
-- Safe to apply: confirmed no existing duplicates on this key pair as of 2026-06-10.
ALTER TABLE user_tool_access
    ADD CONSTRAINT uq_tool_user UNIQUE (tool_id, work_email);
