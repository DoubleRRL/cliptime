"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";

export type TranscriptWord = {
  text: string;
  start: number;
  end: number;
};

type SyncedTranscriptProps = {
  taskId: string;
  clipId: string;
  fallbackText: string;
  clipDurationSeconds: number;
  currentTime: number;
  onSeek: (seconds: number) => void;
};

function parseTimestamp(value: string): number {
  const parts = value.split(":").map(Number);
  if (parts.length !== 2 || parts.some((part) => Number.isNaN(part))) return 0;
  return parts[0] * 60 + parts[1];
}

function buildFallbackWords(text: string, duration: number): TranscriptWord[] {
  const sentences = text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);

  if (sentences.length === 0) {
    return text.trim()
      ? [{ text: text.trim(), start: 0, end: Math.max(duration, 0.1) }]
      : [];
  }

  const slice = duration / sentences.length;
  return sentences.map((sentence, index) => ({
    text: sentence,
    start: index * slice,
    end: (index + 1) * slice,
  }));
}

export function SyncedTranscript({
  taskId,
  clipId,
  fallbackText,
  clipDurationSeconds,
  currentTime,
  onSeek,
}: SyncedTranscriptProps) {
  const [words, setWords] = useState<TranscriptWord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const loadWords = async () => {
      try {
        const response = await fetch(
          `/api/tasks/${taskId}/clips/${clipId}/transcript-words`,
        );
        if (!response.ok) throw new Error("Failed to load words");
        const data = await response.json();
        const loaded = (data.words || []) as TranscriptWord[];
        if (!cancelled) {
          setWords(
            loaded.length > 0
              ? loaded
              : buildFallbackWords(fallbackText, clipDurationSeconds),
          );
        }
      } catch {
        if (!cancelled) {
          setWords(buildFallbackWords(fallbackText, clipDurationSeconds));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadWords();
    return () => {
      cancelled = true;
    };
  }, [taskId, clipId, fallbackText, clipDurationSeconds]);

  const activeIndex = useMemo(() => {
    return words.findIndex(
      (word) => currentTime >= word.start && currentTime < word.end,
    );
  }, [words, currentTime]);

  const handleWordClick = useCallback(
    (word: TranscriptWord) => {
      onSeek(word.start);
    },
    [onSeek],
  );

  if (loading) {
    return (
      <p className="text-sm text-[var(--console-text-muted)]">Loading transcript…</p>
    );
  }

  if (words.length === 0) {
    return (
      <p className="text-sm text-[var(--console-text-muted)]">
        No transcript available for this clip.
      </p>
    );
  }

  return (
    <p className="text-sm leading-relaxed text-[var(--console-text-muted)]">
      {words.map((word, index) => {
        const isActive = index === activeIndex;
        const endsSentence = /[.!?]$/.test(word.text.trim());

        return (
          <span key={`${word.text}-${index}-${word.start}`}>
            <button
              type="button"
              onClick={() => handleWordClick(word)}
              className={cn(
                "rounded-sm px-0.5 transition-colors hover:text-[var(--console-text)]",
                isActive
                  ? "bg-[var(--console-terracotta)]/25 font-medium text-[var(--console-text)]"
                  : "text-[var(--console-text-muted)]",
              )}
            >
              {word.text}
            </button>
            {endsSentence ? " " : " "}
          </span>
        );
      })}
    </p>
  );
}

export function clipDurationFromTimes(startTime: string, endTime: string): number {
  return Math.max(0.1, parseTimestamp(endTime) - parseTimestamp(startTime));
}
