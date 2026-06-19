import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";
import { resolveEffectiveCaptionColors } from "@/lib/caption-template-capabilities";

/** Riverside caption defaults calibrated from reference export (1080×1920). */
export const RIVERSIDE_CAPTION_DEFAULTS = {
  fontFamily: "TikTokSans-Regular",
  fontSize: 32,
  fontColor: "#FFFFFF",
  highlightColor: "#8B5CF6",
  backgroundColor: "#1A1A1ACC",
  captionTemplate: "riverside",
  positionY: 0.77,
  tightCuts: true,
} as const;

export type CaptionTaskOptions = {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  highlightColor: string;
  backgroundColor: string;
  captionTemplate: string;
  positionY: number;
  tightCuts: boolean;
};

export function buildCaptionTaskOptions(
  prefs: Partial<CaptionTaskOptions> | null | undefined,
  template?: CaptionStyleTemplate | null,
): CaptionTaskOptions {
  const base = {
    fontFamily: prefs?.fontFamily ?? RIVERSIDE_CAPTION_DEFAULTS.fontFamily,
    fontSize: prefs?.fontSize ?? RIVERSIDE_CAPTION_DEFAULTS.fontSize,
    fontColor: prefs?.fontColor ?? RIVERSIDE_CAPTION_DEFAULTS.fontColor,
    captionTemplate: prefs?.captionTemplate ?? RIVERSIDE_CAPTION_DEFAULTS.captionTemplate,
    positionY: prefs?.positionY ?? RIVERSIDE_CAPTION_DEFAULTS.positionY,
    tightCuts: prefs?.tightCuts ?? RIVERSIDE_CAPTION_DEFAULTS.tightCuts,
  };

  if (template) {
    const colors = resolveEffectiveCaptionColors(
      template,
      prefs?.highlightColor,
      prefs?.backgroundColor,
    );
    return {
      ...base,
      highlightColor: colors.highlightColor,
      backgroundColor: colors.textBackgroundColor,
    };
  }

  return {
    ...base,
    highlightColor: prefs?.highlightColor ?? RIVERSIDE_CAPTION_DEFAULTS.highlightColor,
    backgroundColor: prefs?.backgroundColor ?? RIVERSIDE_CAPTION_DEFAULTS.backgroundColor,
  };
}
