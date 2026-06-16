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
import {
  clampPreviewWidth,
  CLIP_EDITOR_MAX_PREVIEW_WIDTH,
  DEFAULT_PREVIEW_WIDTH,
  MIN_PREVIEW_WIDTH,
  Resizable9By16Frame,
} from "@/components/console/resizable-9-16-frame";
import { getClipDisplayTitle } from "@/lib/clip-display-title";
import { getScoreBadgeClass } from "@/lib/virality-score";
import {
  FONT_COLOR_PRESETS,
  HIGHLIGHT_COLOR_PRESETS,
  TEXT_BACKGROUND_PRESETS,
} from "@/lib/caption-color-presets";
import { resolveRenderFontSize } from "@/lib/caption-fit";
import { RIVERSIDE_CAPTION_DEFAULTS } from "@/lib/caption-defaults";
import { formatSupportMessage, parseApiError } from "@/lib/api-error";
import { cn } from "@/lib/utils";
import { Download, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  applyCaptionTemplateDefaults,
  getCaptionTemplateCapabilities,
} from "@/lib/caption-template-capabilities";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const DEFAULT_HIGHLIGHT_COLOR = "#8B5CF6";
const DEFAULT_TEXT_BACKGROUND_COLOR = "#1A1A1ACC";
const RERENDER_TOAST_ID = "clip-rerender";
const STYLE_PREVIEW_STORAGE_KEY = "cliptime:showStylePreview";
const PREVIEW_WIDTH_STORAGE_KEY = "cliptime:clipEditorPreviewWidth";

function readStoredPreviewWidth(): number {
  if (typeof window === "undefined") return DEFAULT_PREVIEW_WIDTH;
  const stored = window.sessionStorage.getItem(PREVIEW_WIDTH_STORAGE_KEY);
  if (!stored) return DEFAULT_PREVIEW_WIDTH;
  const parsed = Number(stored);
  if (Number.isNaN(parsed)) return DEFAULT_PREVIEW_WIDTH;
  return clampPreviewWidth(parsed, undefined, CLIP_EDITOR_MAX_PREVIEW_WIDTH);
}

const PREVIEW_HEIGHT_HEADER_ESTIMATE = 280;

function computeEffectivePreviewMaxWidth(containerWidth: number): number {
  if (typeof window === "undefined") return CLIP_EDITOR_MAX_PREVIEW_WIDTH;
  const availableHeight = window.innerHeight * 0.9 - PREVIEW_HEIGHT_HEADER_ESTIMATE;
  const heightBasedMax = Math.floor(Math.max(0, availableHeight) * (9 / 16));
  return Math.max(
    MIN_PREVIEW_WIDTH,
    Math.min(CLIP_EDITOR_MAX_PREVIEW_WIDTH, containerWidth, heightBasedMax || CLIP_EDITOR_MAX_PREVIEW_WIDTH),
  );
}

type EditorBaseline = {
  captionTemplate: string;
  fontSize: number;
  fontColor: string;
  highlightColor: string;
  textBackgroundColor: string;
  positionY: number;
  emphasisCallouts: boolean;
};

type ClipEditorModalProps = {
  taskId: string | null;
  clip: ConsoleClip | null;
  sessionSettings: ConsoleSessionSettings | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClipUpdated: (clip: ConsoleClip) => void;
  onClipCreated: (clip: ConsoleClip) => void;
  onClipDeleted?: (clipId: string) => void;
  onRegeneratingChange?: (clipId: string | null) => void;
  taskApiUrl?: string;
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

function mapApiClip(
  raw: Record<string, unknown>,
  previous?: ConsoleClip | null,
  cacheBust?: number,
): ConsoleClip {
  const baseUrl = raw.video_url ? `/api${String(raw.video_url)}` : previous?.videoUrl || "";
  const videoUrl =
    baseUrl && cacheBust ? `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}v=${cacheBust}` : baseUrl;

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
    videoUrl,
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
  onClipDeleted,
  onRegeneratingChange,
  taskApiUrl = "/api/tasks",
}: ClipEditorModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const previewContainerRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const [startDelta, setStartDelta] = useState(0);
  const [endDelta, setEndDelta] = useState(0);
  const [captionTemplate, setCaptionTemplate] = useState("riverside");
  const [fontSize, setFontSize] = useState(RIVERSIDE_CAPTION_DEFAULTS.fontSize);
  const [fontColor, setFontColor] = useState("#FFFFFF");
  const [highlightColor, setHighlightColor] = useState(DEFAULT_HIGHLIGHT_COLOR);
  const [textBackgroundColor, setTextBackgroundColor] = useState(DEFAULT_TEXT_BACKGROUND_COLOR);
  const [emphasisCallouts, setEmphasisCallouts] = useState(true);
  const [positionY, setPositionY] = useState(RIVERSIDE_CAPTION_DEFAULTS.positionY);
  const [replaceOriginal, setReplaceOriginal] = useState(false);
  const [baseline, setBaseline] = useState<EditorBaseline | null>(null);
  const [previewToken, setPreviewToken] = useState(0);
  const [templates, setTemplates] = useState<CaptionStyleTemplate[]>([]);
  const [isApplying, setIsApplying] = useState(false);
  const [applyStageIndex, setApplyStageIndex] = useState(0);
  const [applyProgress, setApplyProgress] = useState(12);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [showStylePreview, setShowStylePreview] = useState(false);
  const [previewWidth, setPreviewWidth] = useState(DEFAULT_PREVIEW_WIDTH);
  const [effectivePreviewMaxWidth, setEffectivePreviewMaxWidth] = useState(
    CLIP_EDITOR_MAX_PREVIEW_WIDTH,
  );
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const effectiveRenderFontSize = useMemo(
    () => resolveRenderFontSize(fontSize),
    [fontSize],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.sessionStorage.getItem(STYLE_PREVIEW_STORAGE_KEY);
    if (stored === "true") setShowStylePreview(true);
    setPreviewWidth(readStoredPreviewWidth());
  }, []);

  useEffect(() => {
    if (!open) return;

    const updateEffectiveMax = () => {
      const containerWidth = previewContainerRef.current?.clientWidth ?? CLIP_EDITOR_MAX_PREVIEW_WIDTH;
      const nextMax = computeEffectivePreviewMaxWidth(containerWidth);
      setEffectivePreviewMaxWidth(nextMax);
      setPreviewWidth((current) =>
        current > nextMax
          ? clampPreviewWidth(current, nextMax, CLIP_EDITOR_MAX_PREVIEW_WIDTH)
          : current,
      );
    };

    updateEffectiveMax();
    const container = previewContainerRef.current;
    const observer = container ? new ResizeObserver(updateEffectiveMax) : null;
    if (container && observer) observer.observe(container);
    window.addEventListener("resize", updateEffectiveMax);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", updateEffectiveMax);
    };
  }, [open]);

  const handlePreviewWidthChange = useCallback((width: number) => {
    const clamped = clampPreviewWidth(width, effectivePreviewMaxWidth, CLIP_EDITOR_MAX_PREVIEW_WIDTH);
    setPreviewWidth(clamped);
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(PREVIEW_WIDTH_STORAGE_KEY, String(clamped));
    }
  }, [effectivePreviewMaxWidth]);

  const handleStylePreviewChange = (checked: boolean) => {
    setShowStylePreview(checked);
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(STYLE_PREVIEW_STORAGE_KEY, String(checked));
    }
  };

  const applyTemplateSelection = useCallback((template: CaptionStyleTemplate) => {
    const defaults = applyCaptionTemplateDefaults(template);
    if (defaults.positionY != null) setPositionY(defaults.positionY);
    if (defaults.fontSize != null) setFontSize(defaults.fontSize);
    if (defaults.fontColor) setFontColor(defaults.fontColor);
    if (defaults.highlightColor) setHighlightColor(defaults.highlightColor);
    if (defaults.textBackgroundColor) {
      setTextBackgroundColor(defaults.textBackgroundColor);
    } else {
      setTextBackgroundColor("transparent");
    }
    if (defaults.emphasisCallouts != null) setEmphasisCallouts(defaults.emphasisCallouts);
    else setEmphasisCallouts(true);
  }, []);

  const cleanupEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  useEffect(() => cleanupEventSource, [cleanupEventSource]);

  useEffect(() => {
    if (!open || !clip) return;
    const templateId = sessionSettings?.captionTemplate ?? "riverside";
    const matchedTemplate = templates.find((template) => template.id === templateId);
    const templateDefaults = matchedTemplate
      ? applyCaptionTemplateDefaults(matchedTemplate)
      : {};
    const nextBaseline: EditorBaseline = {
      captionTemplate: templateId,
      fontSize: templateDefaults.fontSize ?? sessionSettings?.fontSize ?? RIVERSIDE_CAPTION_DEFAULTS.fontSize,
      fontColor: templateDefaults.fontColor ?? sessionSettings?.fontColor ?? "#FFFFFF",
      highlightColor: templateDefaults.highlightColor ?? DEFAULT_HIGHLIGHT_COLOR,
      textBackgroundColor:
        templateDefaults.textBackgroundColor ?? DEFAULT_TEXT_BACKGROUND_COLOR,
      positionY: templateDefaults.positionY ?? RIVERSIDE_CAPTION_DEFAULTS.positionY,
      emphasisCallouts: templateDefaults.emphasisCallouts ?? true,
    };
    setStartDelta(0);
    setEndDelta(0);
    setError(null);
    setCurrentTime(0);
    setReplaceOriginal(false);
    setCaptionTemplate(nextBaseline.captionTemplate);
    setFontSize(nextBaseline.fontSize);
    setFontColor(nextBaseline.fontColor);
    setHighlightColor(nextBaseline.highlightColor);
    setTextBackgroundColor(nextBaseline.textBackgroundColor);
    setEmphasisCallouts(nextBaseline.emphasisCallouts);
    setPositionY(nextBaseline.positionY);
    setBaseline(nextBaseline);
  }, [
    open,
    clip?.id,
    sessionSettings?.captionTemplate,
    sessionSettings?.fontSize,
    sessionSettings?.fontColor,
    templates,
  ]);

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

  const templateCapabilities = useMemo(
    () => getCaptionTemplateCapabilities(activeTemplate),
    [activeTemplate],
  );

  const hasTrimChanges = startDelta !== 0 || endDelta !== 0;
  const hasStyleChanges = baseline
    ? captionTemplate !== baseline.captionTemplate ||
      fontSize !== baseline.fontSize ||
      fontColor !== baseline.fontColor ||
      highlightColor !== baseline.highlightColor ||
      textBackgroundColor !== baseline.textBackgroundColor ||
      emphasisCallouts !== baseline.emphasisCallouts ||
      Math.abs(positionY - baseline.positionY) > 0.001
    : false;
  const hasChanges = hasTrimChanges || hasStyleChanges;

  const applyStatus = useMemo(() => {
    if (!isApplying) return "";
    if (applyStageIndex === 0) {
      return hasTrimChanges ? "Applying trim boundaries…" : "Preparing render…";
    }
    if (applyStageIndex === 1) return "Rendering video with subtitles…";
    return "Updating clip…";
  }, [isApplying, applyStageIndex, hasTrimChanges]);

  useEffect(() => {
    if (!isApplying) {
      setApplyStageIndex(0);
      setApplyProgress(12);
      return;
    }

    const stageTimer = window.setInterval(() => {
      setApplyStageIndex((previous) => Math.min(previous + 1, 2));
    }, 8_000);

    const progressTimer = window.setInterval(() => {
      setApplyProgress((previous) => Math.min(previous + Math.random() * 10 + 4, 92));
    }, 2_500);

    return () => {
      window.clearInterval(stageTimer);
      window.clearInterval(progressTimer);
    };
  }, [isApplying]);

  const previewStart = clip
    ? formatTimestamp(parseTimestamp(clip.startTime) + startDelta)
    : "00:00";
  const previewEnd = clip ? formatTimestamp(parseTimestamp(clip.endTime) - endDelta) : "00:00";
  const displayTitle = clip ? getClipDisplayTitle(clip) : "";

  const videoSrc = useMemo(() => {
    if (!clip?.videoUrl) return null;
    if (!previewToken) return clip.videoUrl;
    const joiner = clip.videoUrl.includes("?") ? "&" : "?";
    return `${clip.videoUrl}${joiner}v=${previewToken}`;
  }, [clip?.videoUrl, previewToken]);

  const clipDuration = clip ? clipDurationFromTimes(clip.startTime, clip.endTime) : 0;

  const handleSeek = useCallback((seconds: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(0, seconds);
    void video.play().catch(() => undefined);
  }, []);

  const handleDownload = async () => {
    if (!clip || !taskId || isDownloading) return;
    setIsDownloading(true);
    try {
      const response = await fetch(
        `/api/tasks/${taskId}/clips/${clip.id}/export?preset=tiktok`,
      );
      if (!response.ok) {
        const parsed = await parseApiError(response, "Download failed");
        throw new Error(formatSupportMessage(parsed));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = clip.filename || `${clip.id}.mp4`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast.success("Clip downloaded");
    } catch (downloadError) {
      toast.error(
        downloadError instanceof Error ? downloadError.message : "Download failed",
      );
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDelete = async () => {
    if (!clip || !taskId || isDeleting) return;
    setIsDeleting(true);
    try {
      const response = await fetch(`/api/tasks/${taskId}/clips/${clip.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const parsed = await parseApiError(response, "Failed to delete clip");
        throw new Error(formatSupportMessage(parsed));
      }
      toast.success("Clip deleted");
      setDeleteDialogOpen(false);
      onOpenChange(false);
      onClipDeleted?.(clip.id);
    } catch (deleteError) {
      toast.error(deleteError instanceof Error ? deleteError.message : "Failed to delete clip");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleApply = async () => {
    if (!clip || !taskId) return;

    setIsApplying(true);
    setError(null);
    onRegeneratingChange?.(clip.id);
    toast.loading("Regenerating clip…", { id: RERENDER_TOAST_ID });
    cleanupEventSource();

    const sourceClipId = clip.id;

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
          background_color: textBackgroundColor,
          position_y: positionY,
          replace: replaceOriginal,
          emphasis_callouts: emphasisCallouts,
        }),
      });

      if (!response.ok) {
        const parsed = await parseApiError(response, "Failed to regenerate clip");
        throw new Error(formatSupportMessage(parsed));
      }

      const queued = await response.json();
      if (queued.status !== "queued") {
        throw new Error("Unexpected response from re-render endpoint");
      }

      toast.loading("Rendering clip — this may take several minutes…", {
        id: RERENDER_TOAST_ID,
      });

      await new Promise<void>((resolve, reject) => {
        const eventSource = new EventSource(
          `${taskApiUrl}/${taskId}/progress?subscribe=clips`,
        );
        eventSourceRef.current = eventSource;

        const finish = (handler: () => void) => {
          cleanupEventSource();
          handler();
        };

        eventSource.addEventListener("clip_ready", (event) => {
          const payload = JSON.parse((event as MessageEvent<string>).data) as {
            source_clip_id?: string;
            clip?: Record<string, unknown>;
            forked?: boolean;
            replace?: boolean;
          };
          if (payload.source_clip_id && payload.source_clip_id !== sourceClipId) {
            return;
          }
          if (!payload.clip) {
            finish(() => reject(new Error("Re-render completed without clip data")));
            return;
          }

          const cacheBust = Date.now();
          const mapped = mapApiClip(payload.clip, clip, cacheBust);
          const forked = Boolean(payload.forked ?? !replaceOriginal);

          if (forked) {
            onClipCreated(mapped);
            toast.success("Clip regenerated — new version added to queue", {
              id: RERENDER_TOAST_ID,
            });
          } else {
            onClipUpdated(mapped);
            setPreviewToken(cacheBust);
            toast.success("Clip regenerated with your subtitle changes", {
              id: RERENDER_TOAST_ID,
            });
          }

          setStartDelta(0);
          setEndDelta(0);
          setBaseline({
            captionTemplate,
            fontSize,
            fontColor,
            highlightColor,
            textBackgroundColor,
            positionY,
            emphasisCallouts,
          });
          finish(resolve);
        });

        eventSource.addEventListener("rerender_error", (event) => {
          const payload = JSON.parse((event as MessageEvent<string>).data) as {
            source_clip_id?: string;
            message?: string;
          };
          if (payload.source_clip_id && payload.source_clip_id !== sourceClipId) {
            return;
          }
          finish(() =>
            reject(new Error(payload.message || "Failed to regenerate clip")),
          );
        });

        eventSource.addEventListener("error", () => {
          if (eventSource.readyState === EventSource.CLOSED) {
            finish(() =>
              reject(new Error("Lost connection while waiting for re-render")),
            );
          }
        });
      });
    } catch (applyError) {
      cleanupEventSource();
      const message =
        applyError instanceof Error ? applyError.message : "Failed to regenerate clip";
      setError(message);
      toast.error(message, { id: RERENDER_TOAST_ID });
    } finally {
      setIsApplying(false);
      onRegeneratingChange?.(null);
    }
  };

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && isApplying) return;
    onOpenChange(nextOpen);
  };

  const dialogOpen = open && Boolean(clip && taskId);

  return (
    <Dialog open={dialogOpen} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="console-theme max-h-[90vh] overflow-y-auto border-[var(--console-border)] bg-[var(--console-beige)] text-[var(--console-text)] sm:max-w-4xl">
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
                {hasChanges && (
                  <Badge
                    variant="outline"
                    className="border-[var(--console-terracotta)]/40 text-[var(--console-terracotta)]"
                  >
                    Unsaved changes
                  </Badge>
                )}
              </div>
              <DialogDescription className="text-[var(--console-text-muted)]">
                {clip.startTime}–{clip.endTime}
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col gap-6">
              <div ref={previewContainerRef} className="w-full">
                <div className="mb-2 flex justify-end">
                  <p className="text-[11px] text-[var(--console-text-muted)]">
                    Drag corner to resize
                  </p>
                </div>
                <Resizable9By16Frame
                  width={previewWidth}
                  onWidthChange={handlePreviewWidthChange}
                  maxWidth={effectivePreviewMaxWidth}
                  innerClassName="rounded-xl bg-black shadow-2xl"
                  resizeHandleAriaLabel="Resize clip preview"
                >
                  {videoSrc ? (
                    <video
                      ref={videoRef}
                      key={videoSrc}
                      src={videoSrc}
                      controls
                      className="h-full w-full object-contain"
                      playsInline
                      onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-[var(--console-text-muted)]">
                      Preview unavailable
                    </div>
                  )}
                  {showStylePreview && (
                    <CaptionStylePreview
                      fontFamily={sessionSettings?.fontFamily ?? "TikTokSans-Regular"}
                      fontSize={fontSize}
                      fontColor={fontColor}
                      highlightColor={highlightColor}
                      textBackgroundColor={textBackgroundColor}
                      template={activeTemplate}
                      positionY={positionY}
                      emphasisCallouts={emphasisCallouts}
                      frameWidth={previewWidth}
                    />
                  )}
                  {isApplying && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60">
                      <Loader2 className="h-8 w-8 animate-spin text-[var(--console-terracotta)]" />
                    </div>
                  )}
                </Resizable9By16Frame>
              </div>

              <div className="w-full space-y-5">
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
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
                      Style
                    </p>
                  </div>
                  <p className="text-xs leading-relaxed text-[var(--console-text-muted)]">
                    {showStylePreview
                      ? "Preview overlay shows unsaved style changes. Click Regenerate to re-burn subtitles on the source video."
                      : "Turn on Preview overlay, then adjust style below. Subtitles on the video are already burned in."}
                  </p>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <div className="flex shrink-0 items-center gap-2 rounded-lg border border-[var(--console-border)] bg-[var(--console-charcoal)]/50 px-2.5 py-2">
                      <Checkbox
                        id="style-preview-overlay"
                        checked={showStylePreview}
                        onCheckedChange={(checked) =>
                          handleStylePreviewChange(checked === true)
                        }
                        disabled={isApplying}
                      />
                      <Label
                        htmlFor="style-preview-overlay"
                        className="cursor-pointer text-sm text-[var(--console-text)]"
                      >
                        Preview overlay
                      </Label>
                    </div>
                    <div className="min-w-0 flex-1">
                      <Select
                        value={captionTemplate}
                        onValueChange={(value) => {
                          setCaptionTemplate(value);
                          const template = templates.find((entry) => entry.id === value);
                          if (template) applyTemplateSelection(template);
                        }}
                        disabled={isApplying}
                      >
                        <SelectTrigger className="w-full border-[var(--console-border)] bg-[var(--console-charcoal)]">
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
                    </div>
                  </div>
                  {activeTemplate?.description ? (
                    <p className="text-xs italic text-[var(--console-text-muted)]">
                      {activeTemplate.description}
                    </p>
                  ) : null}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-[var(--console-text-muted)]">
                      <span>Font size</span>
                      <span>{fontSize}px</span>
                    </div>
                    <Slider
                      min={24}
                      max={56}
                      step={1}
                      value={[fontSize]}
                      onValueChange={(value) => setFontSize(value[0] ?? fontSize)}
                      disabled={isApplying}
                    />
                    <p className="text-[11px] text-[var(--console-text-muted)]">
                      ~{effectiveRenderFontSize}px on export at 1080p
                    </p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-[var(--console-text-muted)]">
                      <span>Vertical position</span>
                      <span>{Math.round(positionY * 100)}%</span>
                    </div>
                    <Slider
                      min={55}
                      max={85}
                      step={1}
                      value={[Math.round(positionY * 100)]}
                      onValueChange={(value) => setPositionY((value[0] ?? 75) / 100)}
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
                  {templateCapabilities.supportsHighlight ? (
                    <>
                      <ColorSwatches
                        label="Highlight color"
                        value={highlightColor}
                        presets={HIGHLIGHT_COLOR_PRESETS}
                        onChange={setHighlightColor}
                        disabled={isApplying}
                      />
                      <p className="text-xs text-[var(--console-text-muted)]">
                        Accent on the word being spoken
                      </p>
                    </>
                  ) : null}
                  {templateCapabilities.supportsBackground ? (
                    <>
                      <ColorSwatches
                        label="Text background"
                        value={textBackgroundColor}
                        presets={TEXT_BACKGROUND_PRESETS}
                        onChange={setTextBackgroundColor}
                        disabled={isApplying}
                      />
                      <p className="text-xs text-[var(--console-text-muted)]">
                        Optional backdrop behind the caption line
                      </p>
                    </>
                  ) : null}
                  {templateCapabilities.supportsHighlight ? (
                    <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--console-border)] bg-[var(--console-charcoal)]/40 px-3 py-2.5">
                      <div className="space-y-0.5">
                        <Label
                          htmlFor="emphasis-callouts"
                          className="text-sm text-[var(--console-text)]"
                        >
                          Emphasis callouts
                        </Label>
                        <p className="text-xs text-[var(--console-text-muted)]">
                          AI highlights punchy words when they&apos;re spoken
                        </p>
                      </div>
                      <Switch
                        id="emphasis-callouts"
                        checked={emphasisCallouts}
                        onCheckedChange={setEmphasisCallouts}
                        disabled={isApplying}
                      />
                    </div>
                  ) : null}
                </div>

                <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--console-border)] bg-[var(--console-charcoal)]/40 px-3 py-2.5">
                  <div className="space-y-0.5">
                    <Label
                      htmlFor="replace-original"
                      className="text-sm text-[var(--console-text)]"
                    >
                      Replace original
                    </Label>
                    <p className="text-xs text-[var(--console-text-muted)]">
                      {replaceOriginal
                        ? "Overwrite this clip in place"
                        : "Keep original and add a new version"}
                    </p>
                  </div>
                  <Switch
                    id="replace-original"
                    checked={replaceOriginal}
                    onCheckedChange={setReplaceOriginal}
                    disabled={isApplying}
                  />
                </div>

                {error && <p className="text-sm text-red-400">{error}</p>}

                {isApplying && (
                  <div className="space-y-2 rounded-lg border border-[var(--console-border)] bg-[var(--console-charcoal)]/40 px-3 py-3">
                    <div className="flex items-center gap-2 text-sm text-[var(--console-text)]">
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--console-terracotta)]" />
                      <span>{applyStatus}</span>
                    </div>
                    <Progress
                      value={applyProgress}
                      className="h-1.5 bg-[var(--console-border)] [&_[data-slot=progress-indicator]]:bg-[var(--console-terracotta)]"
                    />
                    <p className="text-xs text-[var(--console-text-muted)]">
                      This usually takes several minutes. Keep this tab open.
                    </p>
                  </div>
                )}

                <Button
                  type="button"
                  className="w-full bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]"
                  disabled={isApplying || !hasChanges}
                  onClick={handleApply}
                >
                  {isApplying ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Regenerating…
                    </>
                  ) : replaceOriginal ? (
                    "Regenerate clip"
                  ) : (
                    "Regenerate as new clip"
                  )}
                </Button>

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1 border-[var(--console-border)]"
                    disabled={isApplying || isDownloading || !clip}
                    onClick={() => void handleDownload()}
                  >
                    {isDownloading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Download className="mr-2 h-4 w-4" />
                    )}
                    Download
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1 border-red-500/40 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                    disabled={isApplying || isDeleting || !clip}
                    onClick={() => setDeleteDialogOpen(true)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </div>
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

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this clip?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the clip from your session and deletes its video file. This cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              disabled={isDeleting}
              onClick={(event) => {
                event.preventDefault();
                void handleDelete();
              }}
            >
              {isDeleting ? "Deleting…" : "Delete clip"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  );
}
