export type ScoreTier = "high" | "mid" | "low";

export function getScoreTier(score: number): ScoreTier {
  if (score >= 80) return "high";
  if (score >= 60) return "mid";
  return "low";
}

export function getScoreBadgeClass(score: number): string {
  const tier = getScoreTier(score);
  if (tier === "high") {
    return "bg-[var(--console-score-high-bg)] text-[var(--console-score-high-fg)]";
  }
  if (tier === "mid") {
    return "bg-[var(--console-score-mid-bg)] text-[var(--console-score-mid-fg)]";
  }
  return "bg-[var(--console-score-low-bg)] text-[var(--console-score-low-fg)]";
}

export function getViralityColor(score: number): string {
  if (score >= 80) return "text-emerald-300";
  if (score >= 60) return "text-amber-300";
  if (score >= 40) return "text-orange-300";
  return "text-red-300";
}

export function getViralityBgColor(score: number): string {
  if (score >= 80) return "bg-emerald-500/15 text-emerald-300";
  if (score >= 60) return "bg-amber-500/15 text-amber-300";
  if (score >= 40) return "bg-orange-500/15 text-orange-300";
  return "bg-red-500/15 text-red-300";
}
