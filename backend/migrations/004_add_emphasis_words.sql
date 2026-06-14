-- Migration: Cache AI-detected emphasis words per clip for consistent re-renders.

ALTER TABLE generated_clips ADD COLUMN IF NOT EXISTS emphasis_words_json TEXT;
