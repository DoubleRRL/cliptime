"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type ClipVideoThumbProps = {
  src: string | null;
  className?: string;
};

const THUMB_SEEK_SECONDS = 0.25;

export function ClipVideoThumb({ src, className }: ClipVideoThumbProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setReady(false);
    setFailed(false);
  }, [src]);

  if (!src) {
    return (
      <div
        className={cn(
          "flex h-full items-center justify-center text-xs text-[var(--console-text-muted)]",
          className,
        )}
      >
        No preview
      </div>
    );
  }

  return (
    <div className={cn("relative h-full w-full bg-black", className)}>
      {!ready && !failed && (
        <div className="absolute inset-0 animate-pulse bg-[var(--console-beige)]/20" />
      )}
      <video
        ref={videoRef}
        src={src}
        muted
        playsInline
        preload="metadata"
        className={cn(
          "h-full w-full object-cover transition-opacity duration-200",
          ready ? "opacity-100" : "opacity-0",
        )}
        onLoadedMetadata={() => {
          const video = videoRef.current;
          if (!video) return;
          video.currentTime = Math.min(THUMB_SEEK_SECONDS, video.duration || THUMB_SEEK_SECONDS);
        }}
        onSeeked={() => {
          videoRef.current?.pause();
          setReady(true);
        }}
        onError={() => setFailed(true)}
      />
      {failed && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-[var(--console-text-muted)]">
          Preview unavailable
        </div>
      )}
    </div>
  );
}
