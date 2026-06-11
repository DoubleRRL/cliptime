-- Migration: Add progress tracking fields to tasks table.
-- Note: each statement must be self-contained (the runner splits on ';').

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100);
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS progress_message TEXT;

UPDATE tasks SET progress = 0 WHERE progress IS NULL;

COMMENT ON COLUMN tasks.progress IS 'Task progress percentage (0-100)';
COMMENT ON COLUMN tasks.progress_message IS 'Human-readable progress message';
