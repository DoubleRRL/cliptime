-- Add Riverside-style caption color preferences
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_highlight_color" VARCHAR(9) DEFAULT '#8B5CF6';
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_pill_color" VARCHAR(9) DEFAULT '#1A1A1ACC';
