"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "motion/react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CornerOrbitLoader } from "@/components/corner-orbit-loader";
import { MotionShake } from "@/components/motion-primitives";
import type { CustomClipType, GenerateFromQueryRequest } from "@/lib/types";

interface CustomClipPanelProps {
  taskId: string;
  taskApiUrl: string;
  captionTemplate: string;
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  emptyState?: boolean;
  onClipReady?: (clip: Record<string, unknown>) => void;
  onGenerationComplete?: () => void;
}

type PanelState = "idle" | "generating" | "error";

const CLIP_FORMATS: { value: CustomClipType; label: string; helper: string }[] = [
  { value: "micro_hook", label: "Micro hook (10–30s)", helper: "Punchy standalone moment" },
  { value: "deep_context", label: "Deep cut (30–90s)", helper: "Setup and payoff with context" },
];

export function CustomClipPanel({
  taskId,
  taskApiUrl,
  captionTemplate,
  fontFamily,
  fontSize,
  fontColor,
  emptyState = false,
  onClipReady,
  onGenerationComplete,
}: CustomClipPanelProps) {
  const [query, setQuery] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<CustomClipType[]>([]);
  const [state, setState] = useState<PanelState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [expectedCount, setExpectedCount] = useState(0);
  const receivedRef = useRef(0);
  const eventSourceRef = useRef<EventSource | null>(null);

  const canGenerate = query.trim().length > 0 && selectedTypes.length > 0 && state !== "generating";

  const toggleType = (clipType: CustomClipType) => {
    setSelectedTypes((prev) =>
      prev.includes(clipType) ? prev.filter((value) => value !== clipType) : [...prev, clipType],
    );
  };

  const cleanupEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  useEffect(() => cleanupEventSource, [cleanupEventSource]);

  const handleGenerate = async () => {
    if (!canGenerate) return;

    setState("generating");
    setError(null);
    receivedRef.current = 0;

    const body: GenerateFromQueryRequest = {
      query: query.trim(),
      clip_types: selectedTypes,
      caption_template: captionTemplate,
      font_family: fontFamily,
      font_size: fontSize,
      font_color: fontColor,
    };

    try {
      const response = await fetch(`${taskApiUrl}/${taskId}/clips/generate-from-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || payload.error || "Failed to start generation");
      }

      const data = await response.json();
      const expected = data.expected_clip_count ?? selectedTypes.length;
      setExpectedCount(expected);

      cleanupEventSource();
      const eventSource = new EventSource(
        `${taskApiUrl}/${taskId}/progress?subscribe=clips`,
      );
      eventSourceRef.current = eventSource;

      eventSource.addEventListener("clip_ready", (event) => {
        const payload = JSON.parse((event as MessageEvent<string>).data);
        if (payload.clip) {
          onClipReady?.(payload.clip);
        }
        receivedRef.current += 1;
        if (receivedRef.current >= expected) {
          cleanupEventSource();
          setState("idle");
          setQuery("");
          setSelectedTypes([]);
          onGenerationComplete?.();
        }
      });

      eventSource.addEventListener("error", () => {
        if (receivedRef.current >= expected) {
          cleanupEventSource();
          setState("idle");
          onGenerationComplete?.();
        }
      });
    } catch (generateError) {
      cleanupEventSource();
      setState("error");
      setError(generateError instanceof Error ? generateError.message : "Generation failed");
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-medium text-foreground mb-1">
          {emptyState ? "Describe the clip you're looking for" : "Describe the moment"}
        </p>
        <MotionShake shake={state === "error"}>
          <Textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder='e.g. "do we really need ass cheeks to walk?"'
            rows={3}
            disabled={state === "generating"}
            className="resize-none text-sm"
          />
        </MotionShake>
      </div>

      <div className="space-y-2">
        {CLIP_FORMATS.map((format) => (
          <motion.label
            key={format.value}
            whileTap={{ scale: 0.98 }}
            className="flex items-start gap-3 rounded-lg border border-border/60 px-3 py-2 cursor-pointer"
          >
            <Checkbox
              checked={selectedTypes.includes(format.value)}
              onCheckedChange={() => toggleType(format.value)}
              disabled={state === "generating"}
            />
            <span className="text-sm leading-tight">
              <span className="font-medium text-foreground">{format.label}</span>
              <span className="block text-xs text-muted-foreground">{format.helper}</span>
            </span>
          </motion.label>
        ))}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button className="w-full" disabled={!canGenerate} onClick={handleGenerate}>
        {state === "generating" ? (
          <>
            <CornerOrbitLoader className="mr-2" />
            <motion.span
              key="generating"
              initial={{ opacity: 0, filter: "blur(4px)" }}
              animate={{ opacity: 1, filter: "blur(0px)" }}
            >
              Generating
            </motion.span>
          </>
        ) : (
          <motion.span
            key="generate"
            initial={{ opacity: 0, filter: "blur(4px)" }}
            animate={{ opacity: 1, filter: "blur(0px)" }}
            whileHover={canGenerate ? { scale: 1.02 } : undefined}
            className="inline-flex items-center"
          >
            Generate
          </motion.span>
        )}
      </Button>

      {state === "generating" && expectedCount > 0 && (
        <p className="text-xs text-center text-muted-foreground">
          Rendering {expectedCount} clip{expectedCount === 1 ? "" : "s"}…
        </p>
      )}
    </div>
  );
}
