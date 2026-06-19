export type ConsoleSessionSettings = {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  captionTemplate: string;
  tightCuts: boolean;
};

export type ConsoleSession = {
  id: string;
  title: string;
  status: string;
  clipsCount: number;
  createdAt: string;
  progress?: number;
  progressMessage?: string;
  llmModel?: string | null;
};

export type ConsoleClip = {
  id: string;
  title: string;
  postTitle: string;
  startTime: string;
  endTime: string;
  durationSeconds: number;
  viralityScore: number;
  hookScore: number;
  engagementScore: number;
  valueScore: number;
  shareabilityScore: number;
  clipOrder: number;
  filename: string;
  videoUrl: string;
  text: string;
  reasoning: string;
  hookType: string | null;
  selected: boolean;
  parentClipId?: string;
};

export type WindowProgress = {
  current: number;
  total: number;
};
