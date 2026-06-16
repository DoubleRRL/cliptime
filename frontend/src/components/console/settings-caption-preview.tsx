"use client";

import { useState } from "react";

import {
  CaptionStylePreview,
  type CaptionStyleTemplate,
} from "@/components/console/caption-style-preview";
import {
  DEFAULT_PREVIEW_WIDTH,
  Resizable9By16Frame,
} from "@/components/console/resizable-9-16-frame";
import { burnedInToBase } from "@/lib/caption-fit";
import { cn } from "@/lib/utils";

const SAMPLE_WORDS = ["Your", "subtitle", "here"];
const CAPTION_SETTINGS_PREVIEW_IMAGE = "/images/caption-settings-preview.jpg";

type SettingsCaptionPreviewProps = {
  fontFamily: string;
  burnedInPx: number;
  fontColor: string;
  highlightColor: string;
  textBackgroundColor: string;
  template: CaptionStyleTemplate | null;
  positionY: number;
};

export function SettingsCaptionPreview({
  fontFamily,
  burnedInPx,
  fontColor,
  highlightColor,
  textBackgroundColor,
  template,
  positionY,
}: SettingsCaptionPreviewProps) {
  const [frameWidth, setFrameWidth] = useState(DEFAULT_PREVIEW_WIDTH);
  const baseFontSize = burnedInToBase(burnedInPx);

  return (
    <div className="space-y-2" data-testid="settings-caption-preview">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-foreground">Caption preview</p>
        <p className="text-[11px] text-muted-foreground">Drag corner to resize</p>
      </div>
      <Resizable9By16Frame
        width={frameWidth}
        onWidthChange={setFrameWidth}
        innerClassName={cn(
          "rounded-xl bg-black",
          "ring-2 ring-border ring-offset-2 ring-offset-[var(--console-beige,var(--background))]",
        )}
        resizeHandleAriaLabel="Resize caption preview"
      >
        <CaptionStylePreview
          fontFamily={fontFamily}
          fontSize={baseFontSize}
          fontColor={fontColor}
          highlightColor={highlightColor}
          textBackgroundColor={textBackgroundColor}
          template={template}
          positionY={positionY}
          sampleWords={SAMPLE_WORDS.map((word) => word.toUpperCase())}
          emphasisCallouts
          frameWidth={frameWidth}
          backgroundImageUrl={CAPTION_SETTINGS_PREVIEW_IMAGE}
          showPositionGuide
        />
        <span
          className="absolute right-2 top-2 z-20 rounded-md bg-black/70 px-2 py-0.5 text-[10px] font-medium text-white"
          data-testid="export-px-badge"
        >
          {burnedInPx}px
        </span>
      </Resizable9By16Frame>
    </div>
  );
}
