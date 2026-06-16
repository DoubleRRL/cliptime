"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export const DEFAULT_PREVIEW_WIDTH = 300;
export const MIN_PREVIEW_WIDTH = 220;
export const MAX_PREVIEW_WIDTH = 420;
export const CLIP_EDITOR_MAX_PREVIEW_WIDTH = 680;

export function clampPreviewWidth(
  width: number,
  containerMax?: number,
  maxWidth: number = MAX_PREVIEW_WIDTH,
): number {
  const cap = Math.min(maxWidth, containerMax ?? maxWidth);
  return Math.max(MIN_PREVIEW_WIDTH, Math.min(cap, Math.round(width)));
}

export function computeResizeWidth(
  startWidth: number,
  startPointerX: number,
  pointerX: number,
): number {
  return startWidth + 2 * (pointerX - startPointerX);
}

export function previewHeightForWidth(width: number): number {
  return Math.round(width * (16 / 9));
}

type Resizable9By16FrameProps = {
  width: number;
  onWidthChange: (width: number) => void;
  children: ReactNode;
  maxWidth?: number;
  className?: string;
  frameClassName?: string;
  innerClassName?: string;
  centerFrame?: boolean;
  showResizeHandle?: boolean;
  frameTestId?: string;
  resizeHandleTestId?: string;
  resizeHandleAriaLabel?: string;
};

export function Resizable9By16Frame({
  width,
  onWidthChange,
  children,
  maxWidth = MAX_PREVIEW_WIDTH,
  className,
  frameClassName,
  innerClassName,
  centerFrame = true,
  showResizeHandle = true,
  frameTestId = "caption-preview-frame",
  resizeHandleTestId = "preview-resize-handle",
  resizeHandleAriaLabel = "Resize preview",
}: Resizable9By16FrameProps) {
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef({ width, pointerX: 0 });

  const clampWidth = useCallback(
    (nextWidth: number) => {
      const containerMax = containerRef.current?.clientWidth ?? maxWidth;
      return clampPreviewWidth(nextWidth, containerMax, maxWidth);
    },
    [maxWidth],
  );

  useEffect(() => {
    if (!isResizing) return;

    const handlePointerMove = (event: PointerEvent) => {
      const { width: startWidth, pointerX: startPointerX } = dragStartRef.current;
      const nextWidth = computeResizeWidth(startWidth, startPointerX, event.clientX);
      onWidthChange(clampWidth(nextWidth));
    };

    const handlePointerUp = () => setIsResizing(false);

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [clampWidth, isResizing, onWidthChange]);

  const frame = (
    <div
      className={cn("relative", frameClassName)}
      data-testid={frameTestId}
      style={{
        width,
        height: previewHeightForWidth(width),
        aspectRatio: "9 / 16",
        maxWidth: "100%",
      }}
    >
      <div className={cn("relative h-full w-full overflow-hidden", innerClassName)}>
        {children}
      </div>
      {showResizeHandle ? (
        <button
          type="button"
          aria-label={resizeHandleAriaLabel}
          data-testid={resizeHandleTestId}
          className={cn(
            "absolute -bottom-1 -right-1 z-30 h-4 w-4 cursor-se-resize rounded-sm",
            "border border-border bg-[var(--console-beige,var(--background))]",
            isResizing && "bg-[var(--console-terracotta,var(--primary))]",
          )}
          onPointerDown={(event) => {
            event.preventDefault();
            dragStartRef.current = { width, pointerX: event.clientX };
            setIsResizing(true);
          }}
        />
      ) : null}
    </div>
  );

  return (
    <div ref={containerRef} className={cn("w-full", className)}>
      {centerFrame ? <div className="flex justify-center">{frame}</div> : frame}
    </div>
  );
}
