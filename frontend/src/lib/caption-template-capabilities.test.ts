import { describe, expect, it } from "vitest";

import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";
import { resolveEffectiveCaptionColors } from "@/lib/caption-template-capabilities";

const riversideTemplate: CaptionStyleTemplate = {
  id: "riverside",
  animation: "karaoke",
  pill_style: true,
  background: true,
  highlight_color: "#8B5CF6",
  background_color: "#1A1A1ACC",
};

const tiktokTemplate: CaptionStyleTemplate = {
  id: "tiktok",
  animation: "karaoke",
  background: false,
  highlight_color: "#FE2C55",
};

describe("resolveEffectiveCaptionColors", () => {
  it("uses template colors for TikTok even when saved prefs are Riverside", () => {
    const colors = resolveEffectiveCaptionColors(tiktokTemplate, "#8B5CF6", "#1A1A1ACC");
    expect(colors.highlightColor).toBe("#FE2C55");
    expect(colors.textBackgroundColor).toBe("transparent");
  });

  it("keeps Riverside pill background when template supports it", () => {
    const colors = resolveEffectiveCaptionColors(riversideTemplate, "#FF0000", "#000000AA");
    expect(colors.highlightColor).toBe("#8B5CF6");
    expect(colors.textBackgroundColor).toBe("#1A1A1ACC");
  });
});
