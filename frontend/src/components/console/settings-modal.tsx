"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { track } from "@/lib/datafast";
import { useEffectiveSession } from "@/hooks/use-effective-session";
import { Type, Palette, CheckCircle, AlertCircle, Shield } from "lucide-react";
import { ModelSelector } from "@/components/model-selector";
import { StorageDetailsSection } from "@/components/console/storage-details-section";
import { AppearanceSetting } from "@/components/console/appearance-setting";
import { SettingsCaptionPreview } from "@/components/console/settings-caption-preview";
import type { CaptionStyleTemplate } from "@/components/console/caption-style-preview";
import { cn } from "@/lib/utils";
import { RIVERSIDE_CAPTION_DEFAULTS } from "@/lib/caption-defaults";
import {
  baseToBurnedIn,
  burnedInToBase,
  BURNED_IN_MAX,
  BURNED_IN_MIN,
} from "@/lib/caption-fit";

type SettingsSection = "defaults" | "storage" | "admin";

interface UserPreferences {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  highlightColor: string;
  pillColor: string;
  captionTemplate: string;
  llmModel: string | null;
}

type SettingsModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialSection?: SettingsSection;
  storageRefreshKey?: number;
  onStorageChanged?: () => void;
};

const SECTIONS: Array<{ id: SettingsSection; label: string }> = [
  { id: "defaults", label: "Defaults" },
  { id: "storage", label: "Storage" },
  { id: "admin", label: "Admin" },
];

export function SettingsModal({
  open,
  onOpenChange,
  initialSection = "defaults",
  storageRefreshKey = 0,
  onStorageChanged,
}: SettingsModalProps) {
  const [section, setSection] = useState<SettingsSection>(initialSection);
  const [fontFamily, setFontFamily] = useState(RIVERSIDE_CAPTION_DEFAULTS.fontFamily);
  const [burnedInPx, setBurnedInPx] = useState(baseToBurnedIn(RIVERSIDE_CAPTION_DEFAULTS.fontSize));
  const [fontColor, setFontColor] = useState(RIVERSIDE_CAPTION_DEFAULTS.fontColor);
  const [highlightColor, setHighlightColor] = useState(RIVERSIDE_CAPTION_DEFAULTS.highlightColor);
  const [pillColor, setPillColor] = useState(RIVERSIDE_CAPTION_DEFAULTS.backgroundColor);
  const [captionTemplate, setCaptionTemplate] = useState(RIVERSIDE_CAPTION_DEFAULTS.captionTemplate);
  const [llmModel, setLlmModel] = useState<string | null>(null);
  const [availableTemplates, setAvailableTemplates] = useState<CaptionStyleTemplate[]>([]);
  const [availableFonts, setAvailableFonts] = useState<
    Array<{ name: string; display_name: string }>
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const { user, isPending } = useEffectiveSession();
  const isAdmin = Boolean(user?.is_admin);
  const activeTemplate =
    availableTemplates.find((template) => template.id === captionTemplate) ?? null;

  useEffect(() => {
    if (open) {
      setSection(initialSection);
    }
  }, [open, initialSection]);

  useEffect(() => {
    if (!open) return;

    const loadFonts = async () => {
      try {
        const response = await fetch("/api/fonts", { cache: "no-store" });
        if (!response.ok) return;
        const data = await response.json();
        setAvailableFonts(data.fonts || []);

        const fontFaceStyles = (data.fonts || [])
          .map(
            (font: { name: string }) => `
              @font-face {
                font-family: '${font.name}';
                src: url('/api/fonts/${font.name}') format('truetype');
                font-weight: normal;
                font-style: normal;
              }
            `,
          )
          .join("\n");

        const styleElement = document.createElement("style");
        styleElement.id = "custom-fonts";
        styleElement.innerHTML = fontFaceStyles;
        document.getElementById("custom-fonts")?.remove();
        document.head.appendChild(styleElement);
      } catch (loadError) {
        console.error("Failed to load fonts:", loadError);
      }
    };

    void loadFonts();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const loadTemplates = async () => {
      try {
        const response = await fetch("/api/caption-templates");
        if (response.ok) {
          const data = await response.json();
          setAvailableTemplates(data.templates || []);
        }
      } catch (loadError) {
        console.error("Failed to load caption templates:", loadError);
      }
    };

    void loadTemplates();
  }, [open]);

  useEffect(() => {
    if (!open || !user?.id) return;

    const loadPreferences = async () => {
      setIsFetching(true);
      try {
        const response = await fetch("/api/preferences");
        if (response.ok) {
          const data: UserPreferences = await response.json();
          setFontFamily(data.fontFamily);
          setBurnedInPx(baseToBurnedIn(data.fontSize));
          setFontColor(data.fontColor);
          setHighlightColor(data.highlightColor || RIVERSIDE_CAPTION_DEFAULTS.highlightColor);
          setPillColor(data.pillColor || RIVERSIDE_CAPTION_DEFAULTS.backgroundColor);
          setCaptionTemplate(data.captionTemplate || RIVERSIDE_CAPTION_DEFAULTS.captionTemplate);
          setLlmModel(data.llmModel ?? null);
        }
      } catch (loadError) {
        console.error("Failed to load preferences:", loadError);
      } finally {
        setIsFetching(false);
      }
    };

    void loadPreferences();
  }, [open, user?.id]);

  const handleSavePreferences = async () => {
    setIsLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetch("/api/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fontFamily,
          fontSize: burnedInToBase(burnedInPx),
          fontColor,
          captionTemplate,
          llmModel,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to save preferences");
      }

      track("preferences_saved");
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save preferences");
    } finally {
      setIsLoading(false);
    }
  };

  const visibleSections = SECTIONS.filter((entry) => entry.id !== "admin" || isAdmin);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="console-theme flex max-h-[90vh] w-[min(100vw-2rem,42rem)] flex-col overflow-hidden border-[var(--console-border)] bg-[var(--console-beige)] p-0 text-[var(--console-text)]">
        <DialogHeader className="border-b border-border px-6 py-4">
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Defaults for new sessions, storage usage, and admin tools.
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex gap-2 border-b border-border px-6 py-3">
            {visibleSections.map((entry) => (
              <Button
                key={entry.id}
                type="button"
                size="sm"
                variant={section === entry.id ? "default" : "ghost"}
                className={cn(
                  section === entry.id &&
                    "bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]",
                )}
                onClick={() => setSection(entry.id)}
              >
                {entry.label}
              </Button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
            {isPending || (section === "defaults" && isFetching) ? (
              <div className="space-y-4 py-8">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : section === "defaults" ? (
              <div className="space-y-6">
                <AppearanceSetting />

                <Separator />

                <div>
                  <h3 className="text-sm font-semibold text-foreground">Default font settings</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Applied to all new video processing sessions.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2 text-sm font-medium">
                    <Type className="h-4 w-4" />
                    Font family
                  </Label>
                  <Select value={fontFamily} onValueChange={setFontFamily} disabled={isLoading}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select font" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableFonts.map((font) => (
                        <SelectItem key={font.name} value={font.name}>
                          {font.display_name}
                        </SelectItem>
                      ))}
                      {availableFonts.length === 0 && (
                        <SelectItem value="TikTokSans-Regular">TikTok Sans Regular</SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label className="text-sm font-medium">Subtitle size: {burnedInPx}px</Label>
                  <Slider
                    value={[burnedInPx]}
                    onValueChange={(value) => setBurnedInPx(value[0])}
                    max={BURNED_IN_MAX}
                    min={BURNED_IN_MIN}
                    step={2}
                    disabled={isLoading}
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-sm font-medium">Default caption style</Label>
                  <Select
                    value={captionTemplate}
                    onValueChange={setCaptionTemplate}
                    disabled={isLoading}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select caption style" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableTemplates.map((template) => (
                        <SelectItem key={template.id} value={template.id}>
                          {template.name ?? template.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2 text-sm font-medium">
                    <Palette className="h-4 w-4" />
                    Font color
                  </Label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={fontColor}
                      onChange={(event) => setFontColor(event.target.value)}
                      disabled={isLoading}
                      className="h-10 w-12 cursor-pointer rounded border border-border disabled:cursor-not-allowed"
                    />
                    <Input
                      type="text"
                      value={fontColor}
                      onChange={(event) => setFontColor(event.target.value)}
                      disabled={isLoading}
                      className="h-10 flex-1"
                    />
                  </div>
                </div>

                <SettingsCaptionPreview
                  fontFamily={fontFamily}
                  burnedInPx={burnedInPx}
                  fontColor={fontColor}
                  highlightColor={highlightColor}
                  textBackgroundColor={pillColor}
                  template={activeTemplate}
                />

                <div className="space-y-2">
                  <Label className="text-sm font-medium">Default AI model</Label>
                  <ModelSelector
                    variant="inline"
                    value={llmModel}
                    onChange={setLlmModel}
                    disabled={isLoading}
                  />
                </div>

                {success && (
                  <Alert className="border-green-500/20 bg-green-500/10">
                    <CheckCircle className="h-4 w-4 text-green-400" />
                    <AlertDescription className="text-sm text-green-400">
                      Preferences saved successfully.
                    </AlertDescription>
                  </Alert>
                )}

                {error && (
                  <Alert className="border-red-500/20 bg-red-500/10">
                    <AlertCircle className="h-4 w-4 text-red-400" />
                    <AlertDescription className="text-sm text-red-400">{error}</AlertDescription>
                  </Alert>
                )}

                <Button
                  type="button"
                  className="w-full"
                  disabled={isLoading}
                  onClick={() => void handleSavePreferences()}
                >
                  {isLoading ? "Saving…" : "Save preferences"}
                </Button>
              </div>
            ) : section === "storage" ? (
              <StorageDetailsSection
                refreshKey={storageRefreshKey}
                onStorageChanged={onStorageChanged}
              />
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  <h3 className="text-sm font-semibold text-foreground">Admin dashboard</h3>
                </div>
                <p className="text-sm text-muted-foreground">
                  Review users, active jobs, and recent generations.
                </p>
                <Button asChild variant="outline">
                  <Link href="/admin">Open admin dashboard</Link>
                </Button>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
