import { describe, expect, it } from "vitest";

import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";
import { getCaptionTemplateCapabilities } from "@/lib/caption-template-capabilities";

describe("getCaptionTemplateCapabilities", () => {
  it("riverside supports pill background and highlight", () => {
    const caps = getCaptionTemplateCapabilities({
      id: "riverside",
      pill_style: true,
      background: true,
      animation: "karaoke",
    } as CaptionStyleTemplate);
    expect(caps.supportsPillBackground).toBe(true);
    expect(caps.supportsBoxBackground).toBe(false);
    expect(caps.supportsHighlight).toBe(true);
  });

  it("podcast supports box background not pill", () => {
    const caps = getCaptionTemplateCapabilities({
      id: "podcast",
      background: true,
      animation: "fade",
      stroke_width: 1,
    } as CaptionStyleTemplate);
    expect(caps.supportsPillBackground).toBe(false);
    expect(caps.supportsBoxBackground).toBe(true);
    expect(caps.supportsHighlight).toBe(false);
    expect(caps.supportsStroke).toBe(true);
  });

  it("tiktok has no background controls", () => {
    const caps = getCaptionTemplateCapabilities({
      id: "tiktok",
      background: false,
      animation: "karaoke",
      stroke_width: 2,
    } as CaptionStyleTemplate);
    expect(caps.supportsBackground).toBe(false);
    expect(caps.supportsHighlight).toBe(true);
  });
});
