import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTaskProgress } from "./use-task-progress";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, (event: MessageEvent<string>) => void>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, handler);
  }

  close() {
    const index = MockEventSource.instances.indexOf(this);
    if (index >= 0) MockEventSource.instances.splice(index, 1);
  }

  emit(type: string, data: Record<string, unknown>) {
    const handler = this.listeners.get(type);
    handler?.({ data: JSON.stringify(data) } as MessageEvent<string>);
  }
}

describe("useTaskProgress", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("hydrates progress from initial server values on mount", () => {
    const { result } = renderHook(() =>
      useTaskProgress({
        taskId: "task-1",
        taskStatus: "processing",
        initialProgress: 42,
        initialMessage: "Transcribing audio",
      }),
    );

    expect(result.current.progress).toBe(42);
    expect(result.current.message).toBe("Transcribing audio");
    expect(result.current.activityLog).toEqual(["Transcribing audio"]);
  });

  it("does not zero progress when remounting the same task with hydrate values", () => {
    const props = {
      taskId: "task-1",
      taskStatus: "processing",
      initialProgress: 55,
      initialMessage: "Analyzing transcript",
    };

    const first = renderHook(() => useTaskProgress(props));
    expect(first.result.current.progress).toBe(55);
    first.unmount();

    const second = renderHook(() => useTaskProgress(props));
    expect(second.result.current.progress).toBe(55);
    expect(second.result.current.message).toBe("Analyzing transcript");
  });

  it("resets progress when switching to a different task", () => {
    const { result, rerender } = renderHook(
      (input: {
        taskId: string;
        taskStatus: string;
        initialProgress: number;
        initialMessage: string;
      }) => useTaskProgress(input),
      {
        initialProps: {
          taskId: "task-1",
          taskStatus: "processing",
          initialProgress: 40,
          initialMessage: "Step one",
        },
      },
    );

    expect(result.current.progress).toBe(40);

    rerender({
      taskId: "task-2",
      taskStatus: "queued",
      initialProgress: 5,
      initialMessage: "Queued",
    });

    expect(result.current.progress).toBe(5);
    expect(result.current.message).toBe("Queued");
  });

  it("applies SSE progress updates", async () => {
    const { result } = renderHook(() =>
      useTaskProgress({
        taskId: "task-1",
        taskStatus: "processing",
        initialProgress: 10,
        initialMessage: "Starting",
      }),
    );

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });

    const source = MockEventSource.instances[0];
    act(() => {
      source.emit("progress", { progress: 72, message: "Rendering clips", status: "processing" });
    });

    expect(result.current.progress).toBe(72);
    expect(result.current.message).toBe("Rendering clips");
  });
});
