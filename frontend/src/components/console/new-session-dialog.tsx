"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Loader2, Upload } from "lucide-react";
import { Label } from "@/components/ui/label";
import { ModelSelector } from "@/components/model-selector";
import { formatSupportMessage, parseApiError } from "@/lib/api-error";
import {
  buildCaptionTaskOptions,
  type CaptionTaskOptions,
} from "@/lib/caption-defaults";
import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";
import {
  buildNewSessionCreatePayload,
  formatNewSessionCaptionSummary,
} from "@/lib/new-session-caption-summary";

type NewSessionDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (taskId: string) => void;
};

type DefaultsStatus = "loading" | "ready" | "error";

export function NewSessionDialog({ open, onOpenChange, onCreated }: NewSessionDialogProps) {
  const [uploadedPath, setUploadedPath] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [llmModel, setLlmModel] = useState<string | null>(null);
  const [captionOptions, setCaptionOptions] = useState<CaptionTaskOptions>(
    buildCaptionTaskOptions(null),
  );
  const [defaultsStatus, setDefaultsStatus] = useState<DefaultsStatus>("loading");
  const [templateDisplayName, setTemplateDisplayName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSuggestedModel = useCallback((model: string) => {
    setLlmModel((current) => current ?? model);
  }, []);

  const isBusy = isSubmitting || isUploading;
  const canStart =
    Boolean(uploadedPath) && defaultsStatus === "ready" && !isSubmitting && !isUploading;

  useEffect(() => {
    if (!open) return;

    setDefaultsStatus("loading");
    setTemplateDisplayName(null);

    const loadDefaults = async () => {
      try {
        const [prefsResponse, templatesResponse] = await Promise.all([
          fetch("/api/preferences", { cache: "no-store" }),
          fetch("/api/caption-templates", { cache: "no-store" }),
        ]);

        if (!prefsResponse.ok) {
          console.error("Failed to load preferences:", prefsResponse.status);
          setDefaultsStatus("error");
          return;
        }

        const data = await prefsResponse.json();
        const templatesPayload = templatesResponse.ok ? await templatesResponse.json() : null;
        const templates = (templatesPayload?.templates || []) as CaptionStyleTemplate[];

        if (data?.llmModel) setLlmModel(String(data.llmModel));

        const template =
          templates.find((entry) => entry.id === data?.captionTemplate) ?? null;
        setTemplateDisplayName(template?.name ?? data?.captionTemplate ?? null);
        setCaptionOptions(
          buildCaptionTaskOptions(
            {
              fontFamily: data.fontFamily,
              fontSize: data.fontSize,
              fontColor: data.fontColor,
              highlightColor: data.highlightColor,
              backgroundColor: data.pillColor,
              captionTemplate: data.captionTemplate,
              positionY: data.positionY,
            },
            template,
          ),
        );
        setDefaultsStatus("ready");
      } catch (loadError) {
        console.error("Failed to load session defaults:", loadError);
        setDefaultsStatus("error");
      }
    };

    void loadDefaults();
  }, [open]);

  const reset = () => {
    setUploadedPath(null);
    setUploadedFileName(null);
    setError(null);
    setIsSubmitting(false);
    setIsUploading(false);
    setDefaultsStatus("loading");
    setTemplateDisplayName(null);
    setCaptionOptions(buildCaptionTaskOptions(null));
  };

  const createTask = async (videoUrl: string) => {
    const response = await fetch("/api/tasks/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildNewSessionCreatePayload(videoUrl, captionOptions, llmModel)),
    });

    if (!response.ok) {
      const parsed = await parseApiError(response, "Failed to start processing");
      throw new Error(formatSupportMessage(parsed));
    }

    const data = await response.json();
    return String(data.task_id);
  };

  const handleStartClipping = async () => {
    if (!uploadedPath || defaultsStatus !== "ready") return;

    setIsSubmitting(true);
    setError(null);
    try {
      const taskId = await createTask(uploadedPath);
      onCreated(taskId);
      onOpenChange(false);
      reset();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to create session");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("video", file);
      const uploadResponse = await fetch("/api/upload", { method: "POST", body: formData });
      if (!uploadResponse.ok) {
        const parsed = await parseApiError(uploadResponse, "Upload failed");
        throw new Error(formatSupportMessage(parsed));
      }
      const uploadResult = await uploadResponse.json();
      setUploadedPath(String(uploadResult.video_path));
      setUploadedFileName(file.name);
    } catch (uploadError) {
      setUploadedPath(null);
      setUploadedFileName(null);
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const captionSummary =
    defaultsStatus === "loading"
      ? "Loading defaults…"
      : defaultsStatus === "error"
        ? "Couldn't load saved defaults — check Settings or retry."
        : formatNewSessionCaptionSummary(captionOptions, templateDisplayName);

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) reset();
      }}
    >
      <SheetContent
        side="left"
        className="console-theme top-12 h-[calc(100dvh-3rem)] w-full min-h-0 overflow-hidden border-[var(--console-border)] bg-[var(--console-beige)] text-[var(--console-text)] sm:max-w-md"
      >
        <SheetHeader className="pl-1">
          <SheetTitle className="text-[var(--console-text)]">New session</SheetTitle>
          <SheetDescription className="text-[var(--console-text-muted)]">
            Upload a video file, choose an AI model, then start clipping.
          </SheetDescription>
        </SheetHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-1">
          <Button
            type="button"
            variant="outline"
            className="w-full border-[var(--console-border)]"
            disabled={isBusy}
            onClick={() => fileInputRef.current?.click()}
          >
            {isUploading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            {uploadedFileName ? "Change video file" : "Upload video file"}
          </Button>
          {uploadedFileName && (
            <p className="text-xs text-[var(--console-text-muted)]">
              Ready to clip: {uploadedFileName}
            </p>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            className="hidden"
            onChange={handleFileChange}
          />

          <div className="space-y-1.5">
            <Label className="text-xs text-[var(--console-text-muted)]">AI model</Label>
            <ModelSelector
              variant="inline"
              value={llmModel}
              onChange={setLlmModel}
              onSuggestedModel={handleSuggestedModel}
              disabled={isBusy}
            />
          </div>

          <p
            className="text-[11px] text-[var(--console-text-muted)]"
            data-testid="new-session-caption-summary"
          >
            {captionSummary}
          </p>

          <Button
            type="button"
            className="w-full bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]"
            disabled={!canStart}
            onClick={handleStartClipping}
          >
            {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Start clipping
          </Button>

          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>
      </SheetContent>
    </Sheet>
  );
}
