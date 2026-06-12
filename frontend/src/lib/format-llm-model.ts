const PROVIDER_PREFIX = /^(google-gla|openai|anthropic|ollama|gemini):/i;

/** Display-friendly model label from stored `llm_model` value. */
export function formatLlmModel(model: string | null | undefined): string {
  if (!model || !model.trim()) {
    return "default model";
  }
  const trimmed = model.trim();
  return trimmed.replace(PROVIDER_PREFIX, "");
}
