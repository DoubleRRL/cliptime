-- AlterTable
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_caption_template" VARCHAR(50) DEFAULT 'default';
