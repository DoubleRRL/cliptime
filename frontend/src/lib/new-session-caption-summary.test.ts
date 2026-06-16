import { describe, expect, it } from "vitest";

import { buildCaptionTaskOptions } from "@/lib/caption-defaults";
import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";
import {
  buildNewSessionCreatePayload,
  formatNewSessionCaptionSummary,
} from "@/lib/new-session-caption-summary";

const tiktokTemplate: CaptionStyleTemplate = {
  id: "tiktok",
  name: "TikTok",
  animation: "karaoke",
  background: false,
  highlight_color: "#FE2C55",
};

describe("formatNewSessionCaptionSummary", () => {
  it("shows export px and template display name", () => {
    const options = buildCaptionTaskOptions(
      {
        fontSize: 32,
        positionY: 0.75,
        captionTemplate: "tiktok",
      },
      tiktokTemplate,
    );

    expect(formatNewSessionCaptionSummary(options, "TikTok")).toBe(
      "Captions: TikTok · 48px · 75% vertical",
    );
  });
});

describe("buildNewSessionCreatePayload", () => {
  it("includes template and position from loaded prefs", () => {
    const options = buildCaptionTaskOptions(
      {
        fontSize: 32,
        positionY: 0.75,
        captionTemplate: "tiktok",
        highlightColor: "#8B5CF6",
        backgroundColor: "#1A1A1ACC",
      },
      tiktokTemplate,
    );

    const payload = buildNewSessionCreatePayload("upload://test.mp4", options, null);

    expect(payload.caption_template).toBe("tiktok");
    expect(payload.position_y).toBe(0.75);
    expect(payload.font_options.font_size).toBe(32);
    expect(payload.font_options.highlight_color).toBe("#FE2C55");
    expect(payload.font_options.background_color).toBeUndefined();
  });
});
