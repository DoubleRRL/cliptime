"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Loader2, Upload } from "lucide-react";
import { Label } from "@/components/ui/label";
import { ModelSelector } from "@/components/model-selector";
import { formatSupportMessage, parseApiError } from "@/lib/api-error";

type NewSessionDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (taskId: string) => void;
};

export function NewSessionDialog({ open, onOpenChange, onCreated }: NewSessionDialogProps) {
  const [url, setUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [llmModel, setLlmModel] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Seed the selector with the user's saved default model.
  useEffect(() => {
    if (!open) return;
    fetch("/api/preferences", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (data?.llmModel) setLlmModel(String(data.llmModel));
      })
      .catch(() => undefined);
  }, [open]);

  const reset = () => {
    setUrl("");
    setError(null);
    setIsSubmitting(false);
  };

  const createTask = async (videoUrl: string) => {
    const response = await fetch("/api/tasks/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: { url: videoUrl, title: null },
        font_options: {
          font_family: "TikTokSans-Regular",
          font_size: 48,
          font_color: "#FFFFFF",
          highlight_color: "#8B5CF6",
          background_color: "#1A1A1ACC",
        },
        caption_template: "riverside",
        processing_mode: process.env.NEXT_PUBLIC_DEFAULT_PROCESSING_MODE || "quality",
        output_format: "vertical",
        add_subtitles: true,
        ...(llmModel ? { llm_model: llmModel } : {}),
      }),
    });

    if (!response.ok) {
      const parsed = await parseApiError(response, "Failed to start processing");
      throw new Error(formatSupportMessage(parsed));
    }

    const data = await response.json();
    return String(data.task_id);
  };

  const handleYoutubeSubmit = async () => {
    if (!url.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const taskId = await createTask(url.trim());
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

    setIsSubmitting(true);
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
      const taskId = await createTask(String(uploadResult.video_path));
      onCreated(taskId);
      onOpenChange(false);
      reset();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed");
    } finally {
      setIsSubmitting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

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
            Paste a YouTube link or upload a video file to start clipping.
          </SheetDescription>
        </SheetHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-1">
          <Input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            disabled={isSubmitting}
            className="border-[var(--console-border)] bg-[var(--console-charcoal)] text-[var(--console-text)]"
          />

          <Button
            type="button"
            variant="outline"
            className="w-full border-[var(--console-border)]"
            disabled={isSubmitting}
            onClick={() => fileInputRef.current?.click()}
          >
            {isSubmitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            Upload video file
          </Button>
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
              disabled={isSubmitting}
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>

        <SheetFooter>
          <Button
            type="button"
            className="bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]"
            disabled={!url.trim() || isSubmitting}
            onClick={handleYoutubeSubmit}
          >
            {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Start clipping
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
