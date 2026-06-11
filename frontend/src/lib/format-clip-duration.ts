/** Format seconds as MM:SS (e.g. 72.5 → "01:13"). */
export function formatClipDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "00:00";
  const total = Math.round(seconds);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}
