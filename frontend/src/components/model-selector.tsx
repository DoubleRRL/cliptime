"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Progress } from "@/components/ui/progress";
import {
  BrainCircuit,
  Check,
  ChevronsUpDown,
  Cloud,
  Cpu,
  Download,
  HardDrive,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type InstalledModel = {
  name: string;
  model: string;
  size_gb: number;
  parameter_size?: string | null;
  quantization?: string | null;
};

export type CloudModel = {
  model: string;
  display_name: string;
};

export type ModelRecommendation = {
  tag: string;
  model: string;
  display_name: string;
  params_b: number;
  download_gb: number;
  min_ram_gb: number;
  speed: string;
  quality: string;
  description: string;
  fit: "great" | "ok" | "tight" | "not_recommended";
  installed: boolean;
};

type SystemSpecs = {
  platform: string;
  machine: string;
  cpu_count: number;
  total_ram_gb: number;
  apple_silicon: boolean;
  has_gpu?: boolean;
  gpu_name?: string | null;
  gpu_vram_gb?: number | null;
  spec_source?: "ollama" | "psutil";
};

type PullState = {
  model: string;
  percent: number | null;
  status: string;
  error?: string;
};

type ModelSelectorProps = {
  value: string | null;
  onChange: (model: string | null) => void;
  disabled?: boolean;
  className?: string;
  variant?: "popover" | "inline";
  showDefaultCheckbox?: boolean;
  onDefaultSaved?: (model: string | null) => void;
  /** Fires once when recommendations load and parent value is still null. */
  onSuggestedModel?: (model: string) => void;
};

const FIT_LABELS: Record<ModelRecommendation["fit"], { label: string; className: string }> = {
  great: { label: "Great fit", className: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" },
  ok: { label: "Good fit", className: "bg-sky-500/15 text-sky-600 dark:text-sky-400" },
  tight: { label: "Tight on RAM", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
  not_recommended: { label: "Too heavy", className: "bg-red-500/15 text-red-600 dark:text-red-400" },
};

function shortModelLabel(model: string): string {
  const withoutProvider = model.includes(":") ? model.slice(model.indexOf(":") + 1) : model;
  return withoutProvider;
}

function platformLabel(specs: SystemSpecs): string | null {
  if (specs.apple_silicon) return "Apple Silicon";
  if (specs.platform === "windows") return "Windows";
  if (specs.platform === "linux") return "Linux";
  if (specs.platform === "darwin") return "macOS";
  return null;
}

type ModelListProps = {
  loading: boolean;
  value: string | null;
  system: SystemSpecs | null;
  recsError: string | null;
  recommendations: ModelRecommendation[];
  bestPick: string | null;
  pull: PullState | null;
  ollamaAvailable: boolean;
  defaultModel: string;
  otherInstalled: InstalledModel[];
  cloudModels: CloudModel[];
  disabled?: boolean;
  onReload: () => void;
  onSelect: (model: string | null) => void;
  onInstall: (model: string) => void;
};

function modelRowClasses(isSelected: boolean, disabled?: boolean) {
  return cn(
    "rounded-md border px-2.5 py-2 transition-colors",
    disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
    isSelected
      ? "border-primary/35 bg-primary/10 text-foreground"
      : "border-transparent hover:bg-muted/50",
  );
}

function ModelList({
  loading,
  value,
  system,
  recsError,
  recommendations,
  bestPick,
  pull,
  ollamaAvailable,
  defaultModel,
  otherInstalled,
  cloudModels,
  disabled,
  onReload,
  onSelect,
  onInstall,
}: ModelListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking your models…
      </div>
    );
  }

  return (
    <>
      {system && (
        <div className="mb-1 rounded-md bg-muted/60 px-2.5 py-2 text-[11px] text-muted-foreground">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="flex items-center gap-1">
              <Cpu className="h-3 w-3" /> {system.cpu_count} cores
            </span>
            <span className="flex items-center gap-1">
              <HardDrive className="h-3 w-3" /> {system.total_ram_gb} GB RAM
            </span>
            {platformLabel(system) && <span>{platformLabel(system)}</span>}
            {system.has_gpu && system.gpu_name && (
              <span className="break-words" title={system.gpu_name}>
                GPU · {system.gpu_name}
                {system.gpu_vram_gb != null ? ` (${system.gpu_vram_gb} GB)` : ""}
              </span>
            )}
          </div>
          {system.spec_source === "ollama" && (
            <p className="mt-1 text-[10px]">Specs from Ollama host</p>
          )}
        </div>
      )}

      {recsError ? (
        <div className="mb-1 rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-2 text-xs text-destructive">
          <p>{recsError}</p>
          <button
            type="button"
            onClick={onReload}
            className="mt-1.5 flex items-center gap-1 underline underline-offset-2 hover:no-underline"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        </div>
      ) : recommendations.length > 0 ? (
        <>
          <p className="px-2.5 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Recommended for your system
          </p>
          {recommendations.map((rec) => {
            const fit = FIT_LABELS[rec.fit];
            const isSelected = value === rec.model;
            const isTopPick = bestPick === rec.model;
            const isPulling = pull?.model === rec.model;
            const pullFailed = isPulling && pull?.status === "error";
            const installDisabled =
              disabled ||
              !ollamaAvailable ||
              rec.fit === "not_recommended" ||
              Boolean(pull && !pullFailed);

            return (
              <div
                key={rec.model}
                role="button"
                tabIndex={disabled ? -1 : 0}
                onClick={() => !disabled && onSelect(rec.model)}
                onKeyDown={(event) => {
                  if (disabled) return;
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(rec.model);
                  }
                }}
                className={modelRowClasses(isSelected, disabled)}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-left text-sm">
                    <span className="font-medium break-words">{rec.display_name}</span>
                    {isTopPick && (
                      <span className="flex shrink-0 items-center gap-0.5 text-[10px] text-amber-600 dark:text-amber-400">
                        <Sparkles className="h-3 w-3" />
                        Top pick
                      </span>
                    )}
                    {isSelected && <Check className="h-4 w-4 shrink-0 text-primary" />}
                  </div>
                  {rec.installed ? (
                    <Badge variant="secondary" className="h-5 shrink-0 px-1.5 text-[10px]">
                      Installed
                    </Badge>
                  ) : isPulling && !pullFailed ? (
                    <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {pull?.percent != null ? `${Math.round(pull.percent)}%` : pull?.status}
                    </span>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      className="h-6 shrink-0 gap-1 px-2 text-[11px]"
                      disabled={installDisabled}
                      title={
                        !ollamaAvailable
                          ? "Start Ollama to install"
                          : rec.fit === "not_recommended"
                            ? "Not enough RAM for this model"
                            : undefined
                      }
                      onClick={(event) => {
                        event.stopPropagation();
                        void onInstall(rec.model);
                      }}
                    >
                      <Download className="h-3 w-3" />
                      Install
                    </Button>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <Badge variant="secondary" className={cn("h-4 px-1.5 text-[10px]", fit.className)}>
                    {fit.label}
                  </Badge>
                  <span className="text-[11px] text-muted-foreground">
                    {rec.download_gb} GB · ~{rec.min_ram_gb} GB RAM · {rec.speed}
                  </span>
                </div>
                {isPulling && !pullFailed && pull?.percent != null && (
                  <Progress value={pull.percent} className="mt-1.5 h-1" />
                )}
                {pullFailed && (
                  <p className="mt-1 text-[11px] text-red-500">{pull?.error}</p>
                )}
                <p className="mt-1 text-[11px] leading-snug break-words text-muted-foreground">
                  {rec.description}
                </p>
              </div>
            );
          })}
        </>
      ) : (
        <div className="mb-1 px-2.5 py-2 text-xs text-muted-foreground">
          No recommendations available.{" "}
          <a
            href="https://ollama.com/download"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            Install Ollama
          </a>{" "}
          (0.20+ for Gemma 4).
        </div>
      )}

      <button
        type="button"
        disabled={disabled}
        onClick={() => onSelect(null)}
        className={cn(
          "mt-1 flex w-full items-center justify-between text-left text-sm",
          modelRowClasses(!value, disabled),
        )}
      >
        <span>
          <span className="font-medium">Default</span>
          {defaultModel && (
            <span className="ml-1.5 text-xs text-muted-foreground">
              {shortModelLabel(defaultModel)}
            </span>
          )}
        </span>
        {!value && <Check className="h-4 w-4 text-primary" />}
      </button>

      {(otherInstalled.length > 0 || !ollamaAvailable) && (
        <>
          <p className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Other installed
          </p>
          {!ollamaAvailable && (
            <p className="px-2.5 pb-2 text-xs text-muted-foreground">
              Ollama isn&apos;t reachable.{" "}
              <a
                href="https://ollama.com/download"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2 hover:text-foreground"
              >
                Install Ollama
              </a>
              , then run <code className="text-[10px]">ollama serve</code>.
            </p>
          )}
          {otherInstalled.map((entry) => {
            const isSelected = value === entry.model;
            return (
            <button
              key={entry.model}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(entry.model)}
              className={cn(
                "flex w-full items-center justify-between text-left text-sm",
                modelRowClasses(isSelected, disabled),
              )}
            >
              <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="break-words">{entry.name}</span>
                <span className="shrink-0 text-[11px] text-muted-foreground">
                  {entry.size_gb} GB
                </span>
              </span>
              {isSelected && <Check className="h-4 w-4 shrink-0 text-primary" />}
            </button>
            );
          })}
        </>
      )}

      {cloudModels.length > 0 && (
        <>
          <p className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Cloud
          </p>
          {cloudModels.map((cloud) => {
            const isSelected = value === cloud.model;
            return (
            <button
              key={cloud.model}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(cloud.model)}
              className={cn(
                "flex w-full items-center justify-between text-left text-sm",
                modelRowClasses(isSelected, disabled),
              )}
            >
              <span className="flex items-center gap-2">
                <Cloud className="h-3.5 w-3.5 opacity-50" />
                {cloud.display_name}
              </span>
              {isSelected && <Check className="h-4 w-4 text-primary" />}
            </button>
            );
          })}
        </>
      )}
    </>
  );
}

function modelsMatch(a: string | null | undefined, b: string | null | undefined) {
  return (a ?? null) === (b ?? null);
}

type DefaultModelCheckboxProps = {
  value: string | null;
  savedDefault: string | null;
  disabled?: boolean;
  saving: boolean;
  error: string | null;
  onToggle: (checked: boolean) => void;
};

function DefaultModelCheckbox({
  value,
  savedDefault,
  disabled,
  saving,
  error,
  onToggle,
}: DefaultModelCheckboxProps) {
  const checked = Boolean(value) && modelsMatch(value, savedDefault);
  const checkboxId = "model-selector-default";
  const checkboxDisabled = disabled || saving || !value;

  return (
    <div className="space-y-1">
      <div className="flex items-start gap-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-2">
        <Checkbox
          id={checkboxId}
          checked={checked}
          disabled={checkboxDisabled}
          onCheckedChange={(next) => onToggle(next === true)}
          className="mt-0.5"
        />
        <label
          htmlFor={checkboxId}
          className={cn(
            "text-xs leading-snug text-muted-foreground",
            checkboxDisabled ? "cursor-not-allowed" : "cursor-pointer",
          )}
        >
          {saving
            ? "Saving default model…"
            : !value
              ? "Select a model above first"
              : checked
                ? "Default for new sessions"
                : "Set as default for new sessions"}
          {value ? (
            <span className="mt-0.5 block text-[11px] text-foreground/80">
              {shortModelLabel(value)}
            </span>
          ) : null}
        </label>
      </div>
      {error && <p className="text-[11px] text-red-500">{error}</p>}
    </div>
  );
}

export function ModelSelector({
  value,
  onChange,
  disabled,
  className,
  variant = "popover",
  showDefaultCheckbox = true,
  onDefaultSaved,
  onSuggestedModel,
}: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [installed, setInstalled] = useState<InstalledModel[]>([]);
  const [cloudModels, setCloudModels] = useState<CloudModel[]>([]);
  const [defaultModel, setDefaultModel] = useState<string>("");
  const [ollamaAvailable, setOllamaAvailable] = useState(true);
  const [recommendations, setRecommendations] = useState<ModelRecommendation[]>([]);
  const [system, setSystem] = useState<SystemSpecs | null>(null);
  const [bestPick, setBestPick] = useState<string | null>(null);
  const [recsError, setRecsError] = useState<string | null>(null);
  const [pull, setPull] = useState<PullState | null>(null);
  const [savedDefault, setSavedDefault] = useState<string | null>(null);
  const [defaultSaving, setDefaultSaving] = useState(false);
  const [defaultError, setDefaultError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadSavedDefault = useCallback(async () => {
    try {
      const response = await fetch("/api/preferences", { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      setSavedDefault(data.llmModel ? String(data.llmModel) : null);
    } catch {
      // Preferences are optional; selector still works without them.
    }
  }, []);

  const loadModels = useCallback(async () => {
    setLoading(true);
    setRecsError(null);
    try {
      const [installedRes, recsRes] = await Promise.all([
        fetch("/api/models/installed", { cache: "no-store" }),
        fetch("/api/models/recommendations", { cache: "no-store" }),
      ]);
      if (installedRes.ok) {
        const data = await installedRes.json();
        setInstalled(data.installed || []);
        setCloudModels(data.cloud_models || []);
        setDefaultModel(data.default_model || "");
        setOllamaAvailable(Boolean(data.ollama_available));
      }
      if (recsRes.ok) {
        const data = await recsRes.json();
        setRecommendations(data.recommendations || []);
        setSystem(data.system || null);
        setBestPick(data.best_pick || null);
      } else {
        setRecommendations([]);
        setSystem(null);
        setBestPick(null);
        setRecsError(`Recommendations unavailable (${recsRes.status})`);
      }
    } catch {
      setRecommendations([]);
      setRecsError("Couldn't load recommendations. Check that the backend is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadModels();
    if (showDefaultCheckbox) {
      void loadSavedDefault();
    }
    return () => abortRef.current?.abort();
  }, [loadModels, loadSavedDefault, showDefaultCheckbox]);

  useEffect(() => {
    if (loading || value) return;
    const suggested = bestPick || defaultModel || null;
    if (suggested) {
      onSuggestedModel?.(suggested);
    }
  }, [loading, value, bestPick, defaultModel, onSuggestedModel]);

  const handleDefaultToggle = useCallback(
    async (checked: boolean) => {
      if (checked && !value) return;

      setDefaultSaving(true);
      setDefaultError(null);
      try {
        const response = await fetch("/api/preferences", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ llmModel: checked ? value : null }),
        });
        if (!response.ok) {
          let message = "Couldn't save default model. Try again.";
          try {
            const errorData = await response.json();
            if (errorData?.error) {
              message = String(errorData.error);
            }
          } catch {
            // Ignore malformed error bodies.
          }
          console.error(`Failed to save default model (${response.status})`);
          setDefaultError(message);
          return;
        }
        const data = await response.json();
        const nextDefault = data.llmModel ? String(data.llmModel) : null;
        setSavedDefault(nextDefault);
        onDefaultSaved?.(nextDefault);
      } catch (error) {
        console.error("Failed to save default model", error);
        setDefaultError("Couldn't save default model. Try again.");
      } finally {
        setDefaultSaving(false);
      }
    },
    [onDefaultSaved, value],
  );

  const installModel = useCallback(
    async (model: string) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setPull({ model, percent: 0, status: "starting" });

      try {
        const response = await fetch("/api/models/pull", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model }),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error("Install request failed");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let eventName = "";

        for (;;) {
          const { done, value: chunk } = await reader.read();
          if (done) break;
          buffer += decoder.decode(chunk, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              const payload = JSON.parse(line.slice(5).trim());
              if (eventName === "error") {
                setPull({ model, percent: null, status: "error", error: payload.error });
                return;
              }
              if (eventName === "done") {
                setPull(null);
                await loadModels();
                onChange(payload.model || model);
                return;
              }
              setPull({
                model,
                percent: payload.percent ?? null,
                status: payload.status || "downloading",
              });
            }
          }
        }
        setPull(null);
        await loadModels();
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setPull({ model, percent: null, status: "error", error: "Install failed. Is Ollama running?" });
        }
      }
    },
    [loadModels, onChange],
  );

  const recommendedModels = useMemo(
    () => new Set(recommendations.map((rec) => rec.model)),
    [recommendations],
  );

  const otherInstalled = useMemo(
    () => installed.filter((entry) => !recommendedModels.has(entry.model)),
    [installed, recommendedModels],
  );

  const selectedLabel = useMemo(() => {
    if (value) {
      const rec = recommendations.find((entry) => entry.model === value);
      return rec?.display_name ?? shortModelLabel(value);
    }
    if (bestPick) {
      const rec = recommendations.find((entry) => entry.model === bestPick);
      return `Recommended · ${rec?.display_name ?? shortModelLabel(bestPick)}`;
    }
    if (defaultModel) return `Default · ${shortModelLabel(defaultModel)}`;
    return "Default model";
  }, [value, defaultModel, bestPick, recommendations]);

  const handleSelect = useCallback(
    (model: string | null) => {
      onChange(model);
      setOpen(false);
    },
    [onChange],
  );

  const listProps: ModelListProps = {
    loading,
    value,
    system,
    recsError,
    recommendations,
    bestPick,
    pull,
    ollamaAvailable,
    defaultModel,
    otherInstalled,
    cloudModels,
    disabled,
    onReload: () => void loadModels(),
    onSelect: handleSelect,
    onInstall: installModel,
  };

  const defaultCheckbox = showDefaultCheckbox ? (
    <DefaultModelCheckbox
      value={value}
      savedDefault={savedDefault}
      disabled={disabled}
      saving={defaultSaving}
      error={defaultError}
      onToggle={(checked) => void handleDefaultToggle(checked)}
    />
  ) : null;

  if (variant === "inline") {
    return (
      <div className={cn("space-y-1.5", className)}>
        <div className="max-h-[min(70vh,520px)] overflow-y-auto overscroll-contain rounded-md border border-border bg-background p-1.5">
          <ModelList {...listProps} />
        </div>
        {defaultCheckbox}
      </div>
    );
  }

  return (
    <div className={cn("space-y-1.5", className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            className="h-10 w-full justify-between font-normal"
          >
            <span className="flex min-w-0 items-center gap-2">
              <BrainCircuit className="h-4 w-4 shrink-0 opacity-60" />
              <span className="truncate">{selectedLabel}</span>
            </span>
            <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-40" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          side="bottom"
          collisionPadding={16}
          className="z-[100] w-[min(340px,calc(100vw-2rem))] max-h-[min(85vh,680px)] overflow-y-auto overscroll-contain p-1.5"
          sideOffset={6}
        >
          <ModelList {...listProps} />
        </PopoverContent>
      </Popover>
      {defaultCheckbox}
    </div>
  );
}
