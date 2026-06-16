import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";
import { RIVERSIDE_CAPTION_DEFAULTS } from "@/lib/caption-defaults";

export type CaptionTemplateCapabilities = {
  supportsPillBackground: boolean;
  supportsBoxBackground: boolean;
  supportsBackground: boolean;
  supportsHighlight: boolean;
  supportsStroke: boolean;
};

export function getCaptionTemplateCapabilities(
  template: CaptionStyleTemplate | null | undefined,
): CaptionTemplateCapabilities {
  const pillStyle = Boolean(template?.pill_style);
  const hasBackground = Boolean(template?.background);
  const animation = template?.animation ?? "none";
  const strokeWidth = template?.stroke_width ?? 0;

  return {
    supportsPillBackground: pillStyle,
    supportsBoxBackground: hasBackground && !pillStyle,
    supportsBackground: pillStyle || (hasBackground && !pillStyle),
    supportsHighlight: animation === "karaoke" || animation === "pop",
    supportsStroke: strokeWidth > 0,
  };
}

export function applyCaptionTemplateDefaults(
  template: CaptionStyleTemplate,
): {
  fontSize?: number;
  fontColor?: string;
  highlightColor?: string;
  textBackgroundColor?: string;
  /** @deprecated Use textBackgroundColor */
  pillColor?: string;
  positionY?: number;
  emphasisCallouts?: boolean;
} {
  return {
    fontSize: template.font_size,
    fontColor: template.font_color,
    highlightColor: template.highlight_color,
    textBackgroundColor: template.background_color,
    pillColor: template.background_color,
    positionY: template.position_y,
    emphasisCallouts: template.emphasis_callouts ?? true,
  };
}

export function resolveEffectiveCaptionColors(
  template: CaptionStyleTemplate | null | undefined,
  savedHighlight?: string | null,
  savedPill?: string | null,
  fallbacks: { highlightColor: string; backgroundColor: string } = RIVERSIDE_CAPTION_DEFAULTS,
): { highlightColor: string; textBackgroundColor: string } {
  const caps = getCaptionTemplateCapabilities(template);
  const highlightColor =
    template?.highlight_color ?? savedHighlight ?? fallbacks.highlightColor;
  const textBackgroundColor = caps.supportsBackground
    ? (template?.background_color ?? savedPill ?? fallbacks.backgroundColor)
    : "transparent";
  return { highlightColor, textBackgroundColor };
}
