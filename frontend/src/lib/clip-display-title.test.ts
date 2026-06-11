import { describe, expect, it } from "vitest";

import {
  CARD_TITLE_MAX_LEN,
  getClipDisplayTitle,
  sanitizeForCard,
  stripSpeakerPrefix,
} from "@/lib/clip-display-title";

describe("clip-display-title", () => {
  it("strips speaker prefix", () => {
    expect(stripSpeakerPrefix("Speaker C: I swear this is wild")).toBe("I swear this is wild");
    expect(stripSpeakerPrefix("Speaker A: Yeah")).toBe("Yeah");
  });

  it("truncates long fallback titles", () => {
    const long = "A".repeat(60);
    expect(sanitizeForCard(long).length).toBeLessThanOrEqual(CARD_TITLE_MAX_LEN);
    expect(sanitizeForCard(long).endsWith("…")).toBe(true);
  });

  it("prefers postTitle and sanitizes it", () => {
    const title = getClipDisplayTitle({
      postTitle: "Just Good with Money",
      title: "fallback",
      text: "transcript",
    });
    expect(title).toBe("Just Good with Money");
  });

  it("falls back to transcript without speaker label", () => {
    const title = getClipDisplayTitle({
      postTitle: "",
      title: "Speaker C: I swear, just think it doubled down on the gay card game joke",
      text: "Speaker C: I swear, just think it doubled down on the gay card game joke",
    });
    expect(title).not.toMatch(/^Speaker/i);
    expect(title.length).toBeLessThanOrEqual(CARD_TITLE_MAX_LEN);
  });
});
