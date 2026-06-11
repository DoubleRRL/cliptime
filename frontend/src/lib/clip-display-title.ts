import type { ConsoleClip } from "@/components/console/types";

const CARD_TITLE_MAX_LEN = 48;

function firstSentence(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "";
  const match = trimmed.match(/^[^.!?\n]+[.!?]?/);
  return (match?.[0] ?? trimmed).trim();
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen - 1).trim()}…`;
}

function stripSpeakerPrefix(text: string): string {
  return text.replace(/^Speaker\s+[A-Z0-9]+:\s*/i, "").trim();
}

function sanitizeForCard(text: string): string {
  return truncate(stripSpeakerPrefix(text), CARD_TITLE_MAX_LEN);
}

/** Posting-friendly title with fallback chain for legacy clips. */
export function getClipDisplayTitle(clip: Pick<ConsoleClip, "postTitle" | "title" | "text">): string {
  if (clip.postTitle?.trim()) return sanitizeForCard(clip.postTitle.trim());
  if (clip.title?.trim() && clip.title !== clip.text) {
    return sanitizeForCard(clip.title.trim());
  }
  const sentence = firstSentence(clip.text || "");
  if (sentence) return sanitizeForCard(sentence);
  return "Untitled clip";
}

export { stripSpeakerPrefix, sanitizeForCard, CARD_TITLE_MAX_LEN };
