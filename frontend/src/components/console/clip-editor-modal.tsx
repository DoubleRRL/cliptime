"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import type { ConsoleClip, ConsoleSessionSettings } from "@/components/console/types";
import {
  SyncedTranscript,
  clipDurationFromTimes,
} from "@/components/console/synced-transcript";
import {
  CaptionStylePreview,
  type CaptionStyleTemplate,
} from "@/components/console/caption-style-preview";
import { getClipDisplayTitle } from "@/lib/clip-display-title";
import { getScoreBadgeClass } from "@/lib/virality-score";
import {
  FONT_COLOR_PRESETS,
  HIGHLIGHT_COLOR_PRESETS,
  PILL_COLOR_PRESETS,
} from "@/lib/caption-color-presets";
import { formatSupportMessage, parseApiError } from "@/lib/api-error";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

type ClipEditorModalProps = {
  taskId: string | null;
  clip: ConsoleClip | null;
  sessionSettings: ConsoleSessionSettings | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClipUpdated: (clip: ConsoleClip) => void;
  onClipCreated: (clip: ConsoleClip) => void;
};

function parseTimestamp(value: string): number {
  const parts = value.split(":").map(Number);
  if (parts.length !== 2 || parts.some((part) => Number.isNaN(part))) return 0;
  return parts[0] * 60 + parts[1];
}

function formatTimestamp(totalSeconds: number): string {
  const total = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function mapApiClip(raw: Record<string, unknown>, previous?: ConsoleClip | null): ConsoleClip {
  return {
    id: String(raw.id),
    title: String(raw.title || raw.text || previous?.title || "Clip"),
    postTitle: String(raw.post_title || previous?.postTitle || ""),
    startTime: String(raw.start_time || previous?.startTime || ""),
    endTime: String(raw.end_time || previous?.endTime || ""),
    durationSeconds: Number(raw.duration ?? previous?.durationSeconds ?? 0),
    viralityScore: Number(raw.virality_score ?? previous?.viralityScore ?? 0),
    hookScore: Number(raw.hook_score ?? previous?.hookScore ?? 0),
    engagementScore: Number(raw.engagement_score ?? previous?.engagementScore ?? 0),
    valueScore: Number(raw.value_score ?? previous?.valueScore ?? 0),
    shareabilityScore: Number(raw.shareability_score ?? previous?.shareabilityScore ?? 0),
    clipOrder: Number(raw.clip_order ?? previous?.clipOrder ?? 0),
    filename: String(raw.filename || previous?.filename || ""),
    videoUrl: raw.video_url ? `/api${String(raw.video_url)}` : previous?.videoUrl || "",
    text: String(raw.text ?? previous?.text ?? ""),
    reasoning: String(raw.reasoning ?? previous?.reasoning ?? ""),
    hookType: raw.hook_type ? String(raw.hook_type) : previous?.hookType ?? null,
    selected: previous?.selected ?? false,
    parentClipId: raw.parent_clip_id
      ? String(raw.parent_clip_id)
      : previous?.parentClipId,
  };
}

function ColorSwatches({
  label,
  value,
  presets,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  presets: ReadonlyArray<{ label: string; value: string }>;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-[var(--console-text-muted)]">
        <span>{label}</span>
        <span className="font-mono uppercase">{value}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <button
            key={preset.value}
            type="button"
            title={preset.label}
            disabled={disabled}
            onClick={() => onChange(preset.value)}
            className={cn(
              "h-7 w-7 rounded-full border-2 transition-transform hover:scale-105",
              value.toUpperCase() === preset.value.toUpperCase()
                ? "border-[var(--console-terracotta)]"
                : "border-transparent",
            )}
            style={{ backgroundColor: preset.value.slice(0, 7) }}
          />
        ))}
      </div>
    </div>
  );
}

export function ClipEditorModal({
  taskId,
  clip,
  sessionSettings,
  open,
  onOpenChange,
  onClipUpdated,
  onClipCreated,
}: ClipEditorModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [startDelta, setStartDelta] = useState(0);
  const [endDelta, setEndDelta] = useState(0);
  const [captionTemplate, setCaptionTemplate] = useState("riverside");
  const [fontSize, setFontSize] = useState(28);
  const [fontColor, setFontColor] = useState("#FFFFFF");
  const [highlightColor, setHighlightColor] = useState("#8B5CF6");
  const [pillColor, setPillColor] = useState("#1A1A1ACC");
  const [templates, setTemplates] = useState<CaptionStyleTemplate[]>([]);
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);

  useEffect(() => {
    if (!open || !clip) return;
    setStartDelta(0);
    setEndDelta(0);
    setError(null);
    setCurrentTime(0);
    setCaptionTemplate(sessionSettings?.captionTemplate ?? "riverside");
    setFontSize(sessionSettings?.fontSize ?? 28);
    setFontColor(sessionSettings?.fontColor ?? "#FFFFFF");
    setHighlightColor("#8B5CF6");
    setPillColor("#1A1A1ACC");
  }, [open, clip, sessionSettings?.captionTemplate, sessionSettings?.fontSize, sessionSettings?.fontColor]);

  useEffect(() => {
    if (!open) return;
    const loadTemplates = async () => {
      try {
        const response = await fetch("/api/caption-templates");
        if (!response.ok) return;
        const data = await response.json();
        const options = (data.templates || data || []) as CaptionStyleTemplate[];
        if (options.length > 0) setTemplates(options);
      } catch {
        // Keep defaults when templates endpoint is unavailable.
      }
    };
    void loadTemplates();
  }, [open]);

  const activeTemplate = useMemo(
    () => templates.find((template) => template.id === captionTemplate) ?? null,
    [templates, captionTemplate],
  );

  const previewStart = clip
    ? formatTimestamp(parseTimestamp(clip.startTime) + startDelta)
    : "00:00";
  const previewEnd = clip ? formatTimestamp(parseTimestamp(clip.endTime) - endDelta) : "00:00";
  const displayTitle = clip ? getClipDisplayTitle(clip) : "";

  const videoSrc = clip?.videoUrl || null;

  const clipDuration = clip ? clipDurationFromTimes(clip.startTime, clip.endTime) : 0;

  const handleSeek = useCallback((seconds: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(0, seconds);
    void video.play().catch(() => undefined);
  }, []);

  const handleApply = async () => {
    if (!clip || !taskId) return;

    setIsApplying(true);
    setError(null);

    try {
      const response = await fetch(`/api/tasks/${taskId}/clips/${clip.id}/re-render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_delta_seconds: startDelta,
          end_delta_seconds: endDelta,
          caption_template: captionTemplate,
          font_family: sessionSettings?.fontFamily ?? "TikTokSans-Regular",
          font_size: fontSize,
          font_color: fontColor,
          highlight_color: highlightColor,
          background_color: pillColor,
        }),
      });

      if (!response.ok) {
        const parsed = await parseApiError(response, "Failed to save clip");
        throw new Error(formatSupportMessage(parsed));
      }

      const data = await response.json();
      const raw = data.clip as Record<string, unknown>;
      const mapped = mapApiClip(raw, clip);

      if (data.forked) {
        onClipCreated(mapped);
      } else {
        onClipUpdated(mapped);
      }

      setStartDelta(0);
      setEndDelta(0);
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "Failed to save clip");
    } finally {
      setIsApplying(false);
    }
  };

  const dialogOpen = open && Boolean(clip && taskId);

  return (
    <Dialog open={dialogOpen} onOpenChange={onOpenChange}>
      <DialogContent className="console-theme max-h-[90vh] overflow-y-auto border-[var(--console-border)] bg-[var(--console-beige)] text-[var(--console-text)] sm:max-w-3xl">
        {clip && taskId ? (
          <>
            <DialogHeader>
              <div className="flex flex-wrap items-center gap-2 pr-8">
                <DialogTitle className="text-[var(--console-text)]">{displayTitle}</DialogTitle>
                {startDelta !== 0 || endDelta !== 0 ? (
                  <span className="text-sm text-[var(--console-terracotta)]">
                    → {previewStart}–{previewEnd}
                  </span>
                ) : null}
                {clip.viralityScore > 0 && (
                  <Badge className={getScoreBadgeClass(clip.viralityScore)}>
                    Score {clip.viralityScore}
                  </Badge>
                )}
                {clip.hookType && (
                  <Badge
                    variant="outline"
                    className="border-[var(--console-border)] text-[var(--console-text-muted)]"
                  >
                    {clip.hookType.replace(/_/g, " ")}
                  </Badge>
                )}
              </div>
              <DialogDescription className="text-[var(--console-text-muted)]">
                {clip.startTime}–{clip.endTime}
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-6 md:grid-cols-[minmax(0,240px)_1fr]">
              <div className="mx-auto w-full max-w-[240px]">
                <div className="relative aspect-[9/16] overflow-hidden rounded-xl bg-black shadow-2xl">
                  {videoSrc ? (
                    <video
                      ref={videoRef}
                      key={videoSrc}
                      src={videoSrc}
                      controls
                      className="h-full w-full object-cover"
                      playsInline
                      onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-[var(--console-text-muted)]">
                      Preview unavailable
                    </div>
                  )}
                  <CaptionStylePreview
                    fontFamily={sessionSettings?.fontFamily ?? "TikTokSans-Regular"}
                    fontSize={fontSize}
                    fontColor={fontColor}
                    highlightColor={highlightColor}
                    pillColor={pillColor}
                    template={activeTemplate}
                  />
                  {isApplying && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60">
                      <Loader2 className="h-8 w-8 animate-spin text-[var(--console-terracotta)]" />
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-5">
                <div className="space-y-3">
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
                    Trim
                  </p>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-[var(--console-text-muted)]">
                      <span>Start</span>
                      <span>
                        {startDelta > 0
                          ? `−${startDelta}s from start`
                          : startDelta < 0
                            ? `+${Math.abs(startDelta)}s before start`
                            : "No change"}
                      </span>
                    </div>
                    <Slider
                      min={-30}
                      max={30}
                      step={1}
                      value={[startDelta]}
                      onValueChange={(value) => setStartDelta(value[0] ?? 0)}
                      disabled={isApplying}
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-[var(--console-text-muted)]">
                      <span>End</span>
                      <span>
                        {endDelta > 0
                          ? `−${endDelta}s from end`
                          : endDelta < 0
                            ? `+${Math.abs(endDelta)}s after end`
                            : "No change"}
                      </span>
                    </div>
                    <Slider
                      min={-30}
                      max={30}
                      step={1}
                      value={[endDelta]}
                      onValueChange={(value) => setEndDelta(value[0] ?? 0)}
                      disabled={isApplying}
                    />
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
                    Style
                  </p>
                  <Select
                    value={captionTemplate}
                    onValueChange={setCaptionTemplate}
                    disabled={isApplying}
                  >
                    <SelectTrigger className="border-[var(--console-border)] bg-[var(--console-charcoal)]">
                      <SelectValue placeholder="Caption template" />
                    </SelectTrigger>
                    <SelectContent>
                      {(templates.length > 0
                        ? templates
                        : [{ id: captionTemplate, name: captionTemplate }]
                      ).map((template) => (
                        <SelectItem key={template.id} value={template.id}>
                          {template.name ?? template.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-[var(--console-text-muted)]">
                      <span>Font size</span>
                      <span>{fontSize}px</span>
                    </div>
                    <Slider
                      min={18}
                      max={42}
                      step={1}
                      value={[fontSize]}
                      onValueChange={(value) => setFontSize(value[0] ?? fontSize)}
                      disabled={isApplying}
                    />
                  </div>
                  <ColorSwatches
                    label="Text color"
                    value={fontColor}
                    presets={FONT_COLOR_PRESETS}
                    onChange={setFontColor}
                    disabled={isApplying}
                  />
                  <ColorSwatches
                    label="Highlight color"
                    value={highlightColor}
                    presets={HIGHLIGHT_COLOR_PRESETS}
                    onChange={setHighlightColor}
                    disabled={isApplying}
                  />
                  <ColorSwatches
                    label="Pill background"
                    value={pillColor}
                    presets={PILL_COLOR_PRESETS}
                    onChange={setPillColor}
                    disabled={isApplying}
                  />
                </div>

                {error && <p className="text-sm text-red-400">{error}</p>}

                <Button
                  type="button"
                  className="w-full bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]"
                  disabled={isApplying}
                  onClick={handleApply}
                >
                  {isApplying ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving…
                    </>
                  ) : (
                    "Save as new clip"
                  )}
                </Button>
              </div>
            </div>

            <div className="space-y-3 border-t border-[var(--console-border)] pt-4">
              <p className="text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
                Transcript
              </p>
              <SyncedTranscript
                taskId={taskId}
                clipId={clip.id}
                fallbackText={clip.text || clip.title}
                clipDurationSeconds={clipDuration}
                currentTime={currentTime}
                onSeek={handleSeek}
              />
              {clip.reasoning && (
                <details className="rounded-lg border border-[var(--console-border)] bg-[var(--console-charcoal)]/40 p-3">
                  <summary className="cursor-pointer text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
                    Why this clip
                  </summary>
                  <p className="mt-2 text-sm italic leading-relaxed text-[var(--console-text-muted)]">
                    {clip.reasoning}
                  </p>
                </details>
              )}
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
