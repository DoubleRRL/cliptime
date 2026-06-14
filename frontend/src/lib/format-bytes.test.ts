import { describe, expect, it } from "vitest";

import { formatBytes } from "./format-bytes";

describe("formatBytes", () => {
  it("formats zero", () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  it("formats gigabytes", () => {
    expect(formatBytes(2.4 * 1024 * 1024 * 1024)).toBe("2.4 GB");
  });

  it("formats kilobytes with precision", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
  });
});
