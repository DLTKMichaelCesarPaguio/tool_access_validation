-- Allow multiple logins per user per tool.
-- Replaces the (tool_id, work_email) unique constraint with
-- (tool_id, work_email, COALESCE(username, '')) so that the same
-- email with different usernames gets its own row.
ALTER TABLE user_tool_access DROP CONSTRAINT IF EXISTS uq_tool_user;
DROP INDEX IF EXISTS uq_tool_user;
CREATE UNIQUE INDEX uq_tool_user
    ON user_tool_access (tool_id, work_email, COALESCE(username, ''));
