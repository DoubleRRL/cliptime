"use client";

import { Slider } from "@/components/ui/slider";
import { ZoomIn, ZoomOut } from "lucide-react";

type ClipGridZoomProps = {
  zoom: number;
  onZoomChange: (zoom: number) => void;
};

export function ClipGridZoom({ zoom, onZoomChange }: ClipGridZoomProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
        Size
      </span>
      <ZoomOut className="h-3.5 w-3.5 shrink-0 text-[var(--console-text-muted)]" />
      <Slider
        min={0}
        max={1}
        step={0.05}
        value={[zoom]}
        onValueChange={(value) => onZoomChange(value[0] ?? zoom)}
        className="w-24"
        aria-label="Clip card size"
      />
      <ZoomIn className="h-3.5 w-3.5 shrink-0 text-[var(--console-text-muted)]" />
    </div>
  );
}
