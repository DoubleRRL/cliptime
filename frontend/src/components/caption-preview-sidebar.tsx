"use client";

import type { ReactNode } from "react";
import { Monitor } from "lucide-react";

import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { MotionFadeIn } from "@/components/motion-primitives";

export interface CaptionPreviewSidebarProps {
  previewThumbnailUrl?: string | null;
  previewMode?: "upload" | "source";
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  templateName: string;
  fontDisplayName?: string;
  onEditStyle?: () => void;
  footer?: ReactNode;
}

export function CaptionPreviewSidebar({
  previewThumbnailUrl,
  fontFamily,
  fontSize,
  fontColor,
  templateName,
  fontDisplayName,
  onEditStyle,
  footer,
}: CaptionPreviewSidebarProps) {
  return (
    <div className="w-full lg:w-[340px] lg:sticky lg:top-8 shrink-0">
      <MotionFadeIn>
        <div className="flex items-center justify-center gap-2 mb-5 text-sm text-muted-foreground">
          <Monitor className="w-4 h-4" />
          <span>Live Preview</span>
        </div>

        <div className="mx-auto" style={{ maxWidth: "300px" }}>
          <div className="relative bg-stone-950" style={{ borderRadius: "3rem", padding: "12px" }}>
            <div
              className="relative overflow-hidden bg-black"
              style={{ borderRadius: "2.25rem", height: "420px" }}
            >
              {previewThumbnailUrl ? (
                <>
                  <div
                    className="absolute inset-0 bg-cover bg-center scale-105 blur-sm"
                    style={{ backgroundImage: `url(${previewThumbnailUrl})` }}
                  />
                  <div className="absolute inset-0 bg-black/25" />
                </>
              ) : (
                <div className="absolute inset-0 bg-gradient-to-b from-stone-600 via-stone-500 to-stone-700" />
              )}

              <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-black/70 via-black/30 to-transparent z-[1]" />

              <div className="absolute left-0 right-0 z-10" style={{ bottom: "120px" }}>
                <div className="mx-4">
                  <p
                    style={{
                      color: fontColor,
                      fontSize: `${Math.max(Math.min(fontSize * 0.55, 18), 11)}px`,
                      fontFamily: `'${fontFamily}', system-ui, -apple-system, sans-serif`,
                      textAlign: "center",
                      lineHeight: "1.5",
                      textShadow: "0 2px 8px rgba(0,0,0,0.8), 0 0px 2px rgba(0,0,0,0.9)",
                    }}
                    className="font-bold"
                  >
                    Your captions use this style
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 space-y-3 px-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Font</span>
            <span className="text-foreground font-medium">{fontDisplayName || fontFamily}</span>
          </div>
          <Separator />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Size</span>
            <span className="text-foreground font-medium">{fontSize}px</span>
          </div>
          <Separator />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Color</span>
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full border border-border"
                style={{ backgroundColor: fontColor }}
              />
              <span className="text-foreground font-medium">{fontColor}</span>
            </div>
          </div>
          <Separator />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Template</span>
            <span className="text-foreground font-medium">{templateName}</span>
          </div>
          {onEditStyle && (
            <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={onEditStyle}>
              Edit style
            </Button>
          )}
        </div>

        {footer && (
          <div className="mt-6">
            <div className="mx-auto w-full max-w-[300px] rounded-[2rem] border border-border bg-card p-4 shadow-lg shadow-black/20">
              {footer}
            </div>
          </div>
        )}
      </MotionFadeIn>
    </div>
  );
}
