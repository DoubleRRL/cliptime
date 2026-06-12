import { describe, expect, it } from "vitest";

function mapTaskToSession(task: Record<string, unknown>) {
  const progressRaw = task.progress;
  const progress =
    typeof progressRaw === "number"
      ? progressRaw
      : progressRaw != null && progressRaw !== ""
        ? Number(progressRaw)
        : undefined;

  return {
    id: String(task.id),
    title: String(task.source_title || task.title || "Untitled"),
    status: String(task.status || "unknown"),
    clipsCount: Number(task.clips_count ?? 0),
    createdAt: String(task.created_at || ""),
    progress: Number.isFinite(progress) ? progress : undefined,
    progressMessage: String(task.progress_message || ""),
    llmModel:
      task.llm_model != null && task.llm_model !== ""
        ? String(task.llm_model)
        : null,
  };
}

describe("mapTaskToSession", () => {
  it("maps llm_model into llmModel", () => {
    const session = mapTaskToSession({
      id: "task-1",
      source_title: "Demo",
      status: "completed",
      clips_count: 3,
      created_at: "2026-06-12T00:00:00Z",
      llm_model: "ollama:qwen3:8b",
    });

    expect(session.llmModel).toBe("ollama:qwen3:8b");
  });

  it("uses null when llm_model is missing", () => {
    const session = mapTaskToSession({
      id: "task-1",
      source_title: "Demo",
      status: "queued",
      clips_count: 0,
      created_at: "",
    });

    expect(session.llmModel).toBeNull();
  });
});
