-- Idempotent schema patches for databases bootstrapped from init.sql
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_highlight_color" VARCHAR(9) DEFAULT '#8B5CF6';
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_pill_color" VARCHAR(9) DEFAULT '#1A1A1ACC';
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_llm_model" VARCHAR(200);
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_position_y" REAL DEFAULT 0.77;
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_tight_cuts" BOOLEAN DEFAULT true;
