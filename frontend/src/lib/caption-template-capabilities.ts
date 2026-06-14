import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";

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
