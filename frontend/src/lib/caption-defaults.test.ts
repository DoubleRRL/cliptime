import { describe, expect, it } from "vitest";

import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";
import { buildCaptionTaskOptions } from "@/lib/caption-defaults";

const tiktokTemplate: CaptionStyleTemplate = {
  id: "tiktok",
  animation: "karaoke",
  background: false,
  highlight_color: "#FE2C55",
};

describe("buildCaptionTaskOptions", () => {
  it("merges template-owned colors when a template is provided", () => {
    const options = buildCaptionTaskOptions(
      {
        captionTemplate: "tiktok",
        highlightColor: "#8B5CF6",
        backgroundColor: "#1A1A1ACC",
        positionY: 0.75,
      },
      tiktokTemplate,
    );

    expect(options.highlightColor).toBe("#FE2C55");
    expect(options.backgroundColor).toBe("transparent");
    expect(options.positionY).toBe(0.75);
  });
});
