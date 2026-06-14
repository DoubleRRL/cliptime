"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { cn } from "@/lib/utils";
import type { ConsoleClip, ConsoleSession, ConsoleSessionSettings } from "@/components/console/types";
import { ClipCard } from "@/components/console/clip-card";
import { ClipGridZoom } from "@/components/console/clip-grid-zoom";
import { CustomClipPanel } from "@/components/custom-clip-panel";
import {
  CLIP_GAP,
  DEFAULT_CLIP_ZOOM,
  useClipGridLayout,
} from "@/components/console/use-clip-grid-layout";
import type { TaskProgressState } from "@/hooks/use-task-progress";
import { Progress } from "@/components/ui/progress";
import { CornerOrbitLoader } from "@/components/corner-orbit-loader";
import { fadeUp, staggerChildren } from "@/lib/motion";
import { formatLlmModel } from "@/lib/format-llm-model";
import { RIVERSIDE_CAPTION_DEFAULTS } from "@/lib/caption-defaults";

type CenterClipsProps = {
  className?: string;
  taskId: string | null;
  session: ConsoleSession | null;
  sessionSettings: ConsoleSessionSettings | null;
  clips: ConsoleClip[];
  activeClipId: string | null;
  progress: TaskProgressState;
  regeneratingClipId?: string | null;
  onSelectClip: (id: string) => void;
  onClipReady?: (clip: Record<string, unknown>) => void;
};

const ACTIVE_STATUSES = new Set(["queued", "processing"]);

function statusColor(status: string): string {
  switch (status) {
    case "completed":
      return "var(--console-status-completed)";
    case "processing":
      return "var(--console-status-processing)";
    case "error":
      return "var(--console-status-error)";
    case "queued":
      return "var(--console-status-queued)";
    default:
      return "var(--console-text-muted)";
  }
}

export function CenterClips({
  className,
  taskId,
  session,
  sessionSettings,
  clips,
  activeClipId,
  progress,
  regeneratingClipId = null,
  onSelectClip,
  onClipReady,
}: CenterClipsProps) {
  const gridRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(DEFAULT_CLIP_ZOOM);
  const { rows, setContainerWidth } = useClipGridLayout(clips.length, zoom);

  const isProcessing = session?.status ? ACTIVE_STATUSES.has(session.status) : false;

  useEffect(() => {
    const node = gridRef.current;
    if (!node) return;

    const updateWidth = () => setContainerWidth(node.clientWidth);
    updateWidth();

    const observer = new ResizeObserver(updateWidth);
    observer.observe(node);
    return () => observer.disconnect();
  }, [clips.length, setContainerWidth]);

  if (!taskId) {
    return (
      <main
        className={cn(
          "flex flex-col items-center justify-center bg-[var(--console-charcoal)] p-8 text-center",
          className,
        )}
      >
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-sm text-[var(--console-text-muted)]"
        >
          Start a session from the left rail — upload a video file to begin.
        </motion.p>
      </main>
    );
  }

  const captionTemplate = sessionSettings?.captionTemplate ?? "riverside";
  const fontFamily = sessionSettings?.fontFamily ?? "TikTokSans-Regular";
  const fontSize = sessionSettings?.fontSize ?? RIVERSIDE_CAPTION_DEFAULTS.fontSize;
  const fontColor = sessionSettings?.fontColor ?? "#FFFFFF";
  const modelLabel = formatLlmModel(session?.llmModel);

  return (
    <main className={cn("flex min-h-0 flex-col bg-[var(--console-charcoal)]", className)}>
      <div className="border-b border-[var(--console-border)] px-4 py-3">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-medium text-[var(--console-text)]">
              {session?.title ?? "Session"}
            </h1>
            <p className="text-xs text-[var(--console-text-muted)]">
              <span style={{ color: statusColor(session?.status ?? "") }}>
                {session?.status ?? "unknown"}
              </span>
              {" · "}
              {clips.length} clip{clips.length === 1 ? "" : "s"}
              {" · "}
              {modelLabel}
            </p>
          </div>
          {clips.length > 0 && <ClipGridZoom zoom={zoom} onZoomChange={setZoom} />}
        </div>

        <AnimatePresence>
          {isProcessing && (
            <motion.div
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="mt-3 space-y-2"
            >
              <div className="flex items-center gap-2 text-sm text-[var(--console-text-muted)]">
                <CornerOrbitLoader />
                <span>{progress.message || "Processing…"}</span>
                <span className="ml-auto tabular-nums">{progress.progress}%</span>
              </div>
              <Progress
                value={progress.progress}
                className="h-1.5 bg-[var(--console-border)] [&>div]:bg-[var(--console-terracotta)] [&>div]:transition-all"
              />
              {progress.activityLog.length > 0 && (
                <div className="max-h-20 overflow-y-auto rounded-lg border border-[var(--console-border)] bg-[var(--console-rail-bg)] px-3 py-2 text-xs text-[var(--console-text-muted)]">
                  {progress.activityLog.slice(-4).map((line) => (
                    <p key={line} className="truncate">
                      {line}
                    </p>
                  ))}
                </div>
              )}
              <p className="text-[11px] text-[var(--console-text-muted)]">
                Processing continues in the background if you refresh.
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div ref={gridRef} className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-4 py-4">
        <AnimatePresence mode="wait">
          {clips.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex h-full min-h-[240px] items-center justify-center rounded-xl border border-dashed border-[var(--console-border)] text-sm text-[var(--console-text-muted)]"
            >
              {isProcessing ? (
                <div className="flex flex-col items-center gap-3">
                  <CornerOrbitLoader />
                  <span>Generating clips…</span>
                </div>
              ) : (
                "Clips will appear here once processing finishes."
              )}
            </motion.div>
          ) : (
            <motion.div
              key="grid"
              variants={staggerChildren}
              initial="hidden"
              animate="visible"
              className="space-y-4"
            >
              {rows.map((row) => (
                <div
                  key={`row-${row.startIndex}`}
                  className="flex flex-wrap justify-center"
                  style={{ gap: CLIP_GAP }}
                >
                  {clips.slice(row.startIndex, row.startIndex + row.count).map((clip) => (
                    <ClipCard
                      key={clip.id}
                      clip={clip}
                      videoSrc={clip.videoUrl || null}
                      width={row.cardWidth}
                      isActive={clip.id === activeClipId}
                      isRegenerating={clip.id === regeneratingClipId}
                      onClick={() => onSelectClip(clip.id)}
                    />
                  ))}
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="console-action-panel shrink-0 border-t border-[var(--console-border)] px-4 py-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
          Create more clips
        </p>
        <CustomClipPanel
          taskId={taskId}
          taskApiUrl="/api/tasks"
          captionTemplate={captionTemplate}
          fontFamily={fontFamily}
          fontSize={fontSize}
          fontColor={fontColor}
          emptyState={clips.length === 0}
          variant="console"
          onClipReady={onClipReady}
        />
      </div>
    </main>
  );
}
