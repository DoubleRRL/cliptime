export type StorageSummary = {
  total_bytes: number;
  breakdown: {
    clips: number;
    uploads: number;
    downloads: number;
    caches: number;
    orphans: number;
  };
  counts: {
    tasks: number;
    clips: number;
    orphan_files: number;
  };
  temp_dir: string;
};

export const STORAGE_BUCKETS: Array<{
  key: keyof StorageSummary["breakdown"];
  label: string;
  color: string;
}> = [
  { key: "clips", label: "Clips", color: "bg-[var(--console-terracotta)]" },
  { key: "uploads", label: "Uploads", color: "bg-blue-500" },
  { key: "downloads", label: "Downloads", color: "bg-violet-500" },
  { key: "caches", label: "Caches", color: "bg-amber-500" },
  { key: "orphans", label: "Orphans", color: "bg-red-500" },
];
