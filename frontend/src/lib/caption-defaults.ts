/** Riverside caption defaults calibrated from reference export (1080×1920). */
export const RIVERSIDE_CAPTION_DEFAULTS = {
  fontFamily: "TikTokSans-Regular",
  fontSize: 32,
  fontColor: "#FFFFFF",
  highlightColor: "#8B5CF6",
  backgroundColor: "#1A1A1ACC",
  captionTemplate: "riverside",
  positionY: 0.77,
} as const;

export type CaptionTaskOptions = {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  highlightColor: string;
  backgroundColor: string;
  captionTemplate: string;
};

export function buildCaptionTaskOptions(
  prefs: Partial<CaptionTaskOptions> | null | undefined,
): CaptionTaskOptions {
  return {
    fontFamily: prefs?.fontFamily ?? RIVERSIDE_CAPTION_DEFAULTS.fontFamily,
    fontSize: prefs?.fontSize ?? RIVERSIDE_CAPTION_DEFAULTS.fontSize,
    fontColor: prefs?.fontColor ?? RIVERSIDE_CAPTION_DEFAULTS.fontColor,
    highlightColor: prefs?.highlightColor ?? RIVERSIDE_CAPTION_DEFAULTS.highlightColor,
    backgroundColor: prefs?.backgroundColor ?? RIVERSIDE_CAPTION_DEFAULTS.backgroundColor,
    captionTemplate: prefs?.captionTemplate ?? RIVERSIDE_CAPTION_DEFAULTS.captionTemplate,
  };
}
