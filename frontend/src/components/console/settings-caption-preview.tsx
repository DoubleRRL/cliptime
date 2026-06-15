"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CaptionStylePreview,
  type CaptionStyleTemplate,
} from "@/components/console/caption-style-preview";
import { buildPreviewCaptionStyles, hexToRgba, isTransparentBackground } from "@/lib/caption-preview-styles";
import { burnedInToBase } from "@/lib/caption-fit";

const SAMPLE_WORDS = ["Your", "subtitle", "here"];
const WORD_CYCLE_MS = 650;
const PLACEMENT_FRAME_WIDTH = 240;

type SettingsCaptionPreviewProps = {
  fontFamily: string;
  burnedInPx: number;
  fontColor: string;
  highlightColor: string;
  textBackgroundColor: string;
  template: CaptionStyleTemplate | null;
};

function buildWords(template: CaptionStyleTemplate | null): string[] {
  if (template?.text_transform === "uppercase") {
    return SAMPLE_WORDS.map((word) => word.toUpperCase());
  }
  return SAMPLE_WORDS.map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
}

export function SettingsCaptionPreview({
  fontFamily,
  burnedInPx,
  fontColor,
  highlightColor,
  textBackgroundColor,
  template,
}: SettingsCaptionPreviewProps) {
  const [activeWordIndex, setActiveWordIndex] = useState(0);
  const words = useMemo(() => buildWords(template), [template]);
  const baseFontSize = burnedInToBase(burnedInPx);
  const showKaraoke = template?.animation === "karaoke";
  const pillStyle = Boolean(template?.pill_style);
  const boxStyle = Boolean(template?.background) && !pillStyle;
  const transparentBackground = isTransparentBackground(textBackgroundColor);

  const captionStyle = buildPreviewCaptionStyles({
    fontFamily,
    displayFontSize: burnedInPx,
    strokeWidth: template?.stroke_width ?? 0,
    strokeColor: template?.stroke_color ?? "#000000",
    shadow: template?.shadow ?? false,
    pillStyle: pillStyle || boxStyle,
  });

  const lineBackgroundStyles =
    !transparentBackground && pillStyle
      ? {
          backgroundColor: hexToRgba(textBackgroundColor, "rgba(26, 26, 26, 0.8)"),
          borderRadius: `${Math.max(8, burnedInPx * 0.45)}px`,
          padding: `${burnedInPx * 0.28}px ${burnedInPx * 0.5}px`,
        }
      : !transparentBackground && boxStyle
        ? {
            backgroundColor: hexToRgba(textBackgroundColor, "rgba(0, 0, 0, 0.5)"),
            borderRadius: "0.25rem",
            padding: "0.3rem 0.5rem",
          }
        : {};

  useEffect(() => {
    if (!showKaraoke) return;
    const timer = window.setInterval(() => {
      setActiveWordIndex((prev) => (prev + 1) % words.length);
    }, WORD_CYCLE_MS);
    return () => window.clearInterval(timer);
  }, [showKaraoke, words.length]);

  return (
    <div className="space-y-4" data-testid="settings-caption-preview">
      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground">
          {burnedInPx}px in your exported clip
        </p>
        <div className="overflow-x-auto rounded-lg border border-border bg-[#0a0a0a] px-4 py-6">
          <div
            className="inline-flex max-w-full flex-wrap justify-center text-center leading-tight"
            data-testid="export-size-sample"
            style={{
              ...captionStyle,
              color: fontColor,
              gap: pillStyle ? "0.15em" : "0.25em",
              ...lineBackgroundStyles,
            }}
          >
            {words.map((word, index) => {
              const isActive = showKaraoke && index === activeWordIndex;
              return (
                <span
                  key={`${word}-${index}`}
                  style={{
                    color: fontColor,
                    whiteSpace: "nowrap",
                    borderRadius: isActive && pillStyle ? `${Math.max(4, burnedInPx * 0.18)}px` : undefined,
                    padding: isActive && pillStyle ? "0.05em 0.2em" : undefined,
                    backgroundColor: isActive && showKaraoke ? highlightColor : "transparent",
                    marginRight: index < words.length - 1 ? "0.15em" : 0,
                  }}
                >
                  {word}
                </span>
              );
            })}
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground">
          Exact export size on screen — what you see here is what gets burned in.
        </p>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground">Placement on 9:16 clip</p>
        <div
          className="relative mx-auto overflow-hidden rounded-lg bg-black"
          style={{ width: PLACEMENT_FRAME_WIDTH, aspectRatio: "9 / 16" }}
        >
          <CaptionStylePreview
            fontFamily={fontFamily}
            fontSize={baseFontSize}
            fontColor={fontColor}
            highlightColor={highlightColor}
            textBackgroundColor={textBackgroundColor}
            template={template}
            sampleWords={SAMPLE_WORDS.map((word) => word.toUpperCase())}
            emphasisCallouts
          />
        </div>
      </div>
    </div>
  );
}
