export type CustomClipType = "micro_hook" | "deep_context";

export interface GenerateFromQueryRequest {
  query: string;
  clip_types: CustomClipType[];
  caption_template: string;
  font_family: string;
  font_size: number;
  font_color: string;
}

export interface GenerateFromQueryResponse {
  job_ids: string[];
  expected_clip_count: number;
}
