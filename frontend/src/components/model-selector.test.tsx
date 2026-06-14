import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModelSelector } from "./model-selector";

const mockRecommendations = {
  system: {
    platform: "darwin",
    machine: "arm64",
    cpu_count: 8,
    total_ram_gb: 16,
    apple_silicon: true,
    spec_source: "ollama",
  },
  best_pick: "ollama:gemma4:e4b",
  recommendations: [
    {
      tag: "gemma4:e4b",
      model: "ollama:gemma4:e4b",
      display_name: "Gemma 4 E4B",
      params_b: 4,
      download_gb: 9.6,
      min_ram_gb: 16,
      speed: "medium",
      quality: "good",
      description: "Top pick for 16 GB laptops.",
      fit: "ok",
      installed: false,
    },
    {
      tag: "gemma4:e2b",
      model: "ollama:gemma4:e2b",
      display_name: "Gemma 4 E2B",
      params_b: 2,
      download_gb: 7.2,
      min_ram_gb: 8,
      speed: "fast",
      quality: "good",
      description: "Edge model.",
      fit: "great",
      installed: true,
    },
  ],
};

const mockInstalled = {
  ollama_available: true,
  installed: [
    {
      name: "gemma4:e2b",
      model: "ollama:gemma4:e2b",
      size_gb: 7.2,
    },
    {
      name: "qwen2.5:7b",
      model: "ollama:qwen2.5:7b",
      size_gb: 4.7,
    },
  ],
  cloud_models: [],
  default_model: "ollama:qwen2.5:7b",
};

describe("ModelSelector", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url.includes("/recommendations")) {
          return Promise.resolve({
            ok: true,
            json: async () => mockRecommendations,
          });
        }
        if (url.includes("/installed")) {
          return Promise.resolve({
            ok: true,
            json: async () => mockInstalled,
          });
        }
        if (url.includes("/api/preferences")) {
          if (init?.method === "PATCH") {
            const body = JSON.parse(String(init.body));
            return Promise.resolve({
              ok: true,
              json: async () => ({ llmModel: body.llmModel ?? null }),
            });
          }
          return Promise.resolve({
            ok: true,
            json: async () => ({ llmModel: null }),
          });
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );
  });

  it("shows recommended models in the dropdown above other installed", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<ModelSelector value={null} onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Recommended · Gemma 4 E4B/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Recommended · Gemma 4 E4B/i }));

    expect(await screen.findByText("Recommended for your system")).toBeInTheDocument();
    expect(screen.getByText("Gemma 4 E4B")).toBeInTheDocument();
    expect(screen.getByText("Gemma 4 E2B")).toBeInTheDocument();
    expect(screen.getByText("Top pick")).toBeInTheDocument();
    expect(screen.getByText("Other installed")).toBeInTheDocument();
    expect(screen.getAllByText("qwen2.5:7b").length).toBeGreaterThan(0);

    const popover = screen.getByRole("dialog");
    const text = popover.textContent ?? "";
    expect(text.indexOf("Recommended for your system")).toBeLessThan(text.indexOf("Other installed"));
  });

  it("selects a recommended model when its row is clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<ModelSelector value={null} onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Recommended · Gemma 4 E4B/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Recommended · Gemma 4 E4B/i }));
    await user.click(screen.getByText("Gemma 4 E2B"));

    expect(onChange).toHaveBeenCalledWith("ollama:gemma4:e2b");
  });

  it("inline variant shows scrollable list and selects on description click", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<ModelSelector variant="inline" value={null} onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByText("Recommended for your system")).toBeInTheDocument();
    });

    expect(screen.getByText("Top pick for 16 GB laptops.")).toBeInTheDocument();
    await user.click(screen.getByText("Top pick for 16 GB laptops."));
    expect(onChange).toHaveBeenCalledWith("ollama:gemma4:e4b");
  });

  it("saves the selected model as the default preference", async () => {
    const onDefaultSaved = vi.fn();
    const user = userEvent.setup();

    render(
      <ModelSelector
        variant="inline"
        value="ollama:gemma4:e2b"
        onChange={vi.fn()}
        onDefaultSaved={onDefaultSaved}
      />,
    );

    const checkbox = await screen.findByRole("checkbox", {
      name: /set as default for new sessions/i,
    });
    await user.click(checkbox);

    await waitFor(() => {
      expect(onDefaultSaved).toHaveBeenCalledWith("ollama:gemma4:e2b");
    });
    expect(screen.getByText("Default for new sessions")).toBeInTheDocument();
  });

  it("disables the default checkbox until a model is selected", async () => {
    render(<ModelSelector variant="inline" value={null} onChange={vi.fn()} />);

    const checkbox = await screen.findByRole("checkbox");
    expect(checkbox).toBeDisabled();
    expect(screen.getByText("Select a model above first")).toBeInTheDocument();
  });

  it("shows the API error when saving the default model fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url.includes("/recommendations")) {
          return Promise.resolve({
            ok: true,
            json: async () => mockRecommendations,
          });
        }
        if (url.includes("/installed")) {
          return Promise.resolve({
            ok: true,
            json: async () => mockInstalled,
          });
        }
        if (url.includes("/api/preferences")) {
          if (init?.method === "PATCH") {
            return Promise.resolve({
              ok: false,
              status: 500,
              json: async () => ({ error: "Internal server error" }),
            });
          }
          return Promise.resolve({
            ok: true,
            json: async () => ({ llmModel: null }),
          });
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );

    const user = userEvent.setup();
    render(
      <ModelSelector variant="inline" value="ollama:gemma4:e2b" onChange={vi.fn()} />,
    );

    const checkbox = await screen.findByRole("checkbox", {
      name: /set as default for new sessions/i,
    });
    await user.click(checkbox);

    expect(await screen.findByText("Internal server error")).toBeInTheDocument();
  });
});
