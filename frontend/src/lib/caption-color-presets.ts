export const HIGHLIGHT_COLOR_PRESETS = [
  { label: "Purple", value: "#8B5CF6" },
  { label: "Terracotta", value: "#C15F3C" },
  { label: "Gold", value: "#EAB308" },
  { label: "Emerald", value: "#10B981" },
  { label: "Sky", value: "#38BDF8" },
  { label: "White", value: "#FFFFFF" },
] as const;

export const TEXT_BACKGROUND_PRESETS = [
  { label: "None", value: "#00000000" },
  { label: "Dark", value: "#1A1A1ACC" },
  { label: "Charcoal", value: "#1C1917CC" },
  { label: "Terracotta", value: "#C15F3CE6" },
  { label: "Purple", value: "#6D28D9CC" },
] as const;

/** @deprecated Use TEXT_BACKGROUND_PRESETS */
export const PILL_COLOR_PRESETS = TEXT_BACKGROUND_PRESETS;

export const FONT_COLOR_PRESETS = [
  { label: "White", value: "#FFFFFF" },
  { label: "Cream", value: "#FAF7F4" },
  { label: "Yellow", value: "#FDE047" },
  { label: "Black", value: "#1C1917" },
] as const;
