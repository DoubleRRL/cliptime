import { describe, expect, it } from "vitest";
import { formatLlmModel } from "./format-llm-model";

describe("formatLlmModel", () => {
  it("strips provider prefixes", () => {
    expect(formatLlmModel("ollama:qwen3:8b")).toBe("qwen3:8b");
    expect(formatLlmModel("google-gla:gemini-3-flash-preview")).toBe(
      "gemini-3-flash-preview",
    );
  });

  it("returns default label for empty values", () => {
    expect(formatLlmModel(null)).toBe("default model");
    expect(formatLlmModel("")).toBe("default model");
    expect(formatLlmModel("   ")).toBe("default model");
  });
});
