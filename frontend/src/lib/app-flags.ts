function isTruthyDefaultTrue(value: string | undefined): boolean {
  if (value === undefined || value === "") return true;
  const normalized = value.trim().toLowerCase();
  return !["0", "false", "no", "off"].includes(normalized);
}

export const isLandingOnlyModeEnabled =
  process.env.NEXT_PUBLIC_LANDING_ONLY_MODE === "true";

/** When true, skip sign-in and auto-use a single local user (default for self-host). */
export const isLocalSingleUserMode = isTruthyDefaultTrue(
  process.env.NEXT_PUBLIC_LOCAL_SINGLE_USER,
);
