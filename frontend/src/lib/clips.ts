import type { ConsoleClip } from "@/components/console/types";

/**
 * Map a raw backend clip payload to the shared ConsoleClip shape.
 * Used by the console app, SSE clip_ready events, and the editor modal.
 */
export function mapApiClip(
  raw: Record<string, unknown>,
  index = 0,
  previous?: ConsoleClip | null,
): ConsoleClip {
  return {
    id: String(raw.id),
    title: String(raw.title || raw.text || previous?.title || `Clip ${index + 1}`),
    postTitle: String(raw.post_title || previous?.postTitle || ""),
    startTime: String(raw.start_time || previous?.startTime || ""),
    endTime: String(raw.end_time || previous?.endTime || ""),
    durationSeconds: Number(raw.duration ?? previous?.durationSeconds ?? 0),
    viralityScore: Number(raw.virality_score ?? previous?.viralityScore ?? 0),
    hookScore: Number(raw.hook_score ?? previous?.hookScore ?? 0),
    engagementScore: Number(raw.engagement_score ?? previous?.engagementScore ?? 0),
    valueScore: Number(raw.value_score ?? previous?.valueScore ?? 0),
    shareabilityScore: Number(raw.shareability_score ?? previous?.shareabilityScore ?? 0),
    clipOrder: Number(raw.clip_order ?? previous?.clipOrder ?? index + 1),
    filename: String(raw.filename || previous?.filename || ""),
    videoUrl: raw.video_url ? `/api${String(raw.video_url)}` : previous?.videoUrl || "",
    text: String(raw.text ?? previous?.text ?? ""),
    reasoning: String(raw.reasoning ?? previous?.reasoning ?? ""),
    hookType: raw.hook_type ? String(raw.hook_type) : previous?.hookType ?? null,
    selected: previous?.selected ?? false,
    parentClipId: raw.parent_clip_id
      ? String(raw.parent_clip_id)
      : previous?.parentClipId,
  };
}
