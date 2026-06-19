import { baseToBurnedIn } from "@/lib/caption-fit";
import type { CaptionTaskOptions } from "@/lib/caption-defaults";

export function formatNewSessionCaptionSummary(
  options: Pick<CaptionTaskOptions, "captionTemplate" | "fontSize" | "positionY" | "tightCuts">,
  templateDisplayName?: string | null,
): string {
  const name = templateDisplayName ?? options.captionTemplate;
  const exportPx = baseToBurnedIn(options.fontSize);
  const cuts = options.tightCuts ? "Tight cuts on" : "Tight cuts off";
  return `Captions: ${name} · ${exportPx}px · ${Math.round(options.positionY * 100)}% vertical · ${cuts}`;
}

export function buildNewSessionCreatePayload(
  videoUrl: string,
  captionOptions: CaptionTaskOptions,
  llmModel: string | null,
) {
  return {
    source: { url: videoUrl, title: null },
    font_options: {
      font_family: captionOptions.fontFamily,
      font_size: captionOptions.fontSize,
      font_color: captionOptions.fontColor,
      highlight_color: captionOptions.highlightColor,
      ...(captionOptions.backgroundColor !== "transparent"
        ? { background_color: captionOptions.backgroundColor }
        : {}),
    },
    caption_template: captionOptions.captionTemplate,
    position_y: captionOptions.positionY,
    emphasis_callouts: true,
    tight_cuts: captionOptions.tightCuts,
    processing_mode: process.env.NEXT_PUBLIC_DEFAULT_PROCESSING_MODE || "quality",
    output_format: "vertical",
    add_subtitles: true,
    ...(llmModel ? { llm_model: llmModel } : {}),
  };
}
