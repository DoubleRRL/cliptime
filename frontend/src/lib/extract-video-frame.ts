export interface ExtractedVideoFrame {
  blob: Blob;
  dataUrl: string;
  width: number;
  height: number;
}

export async function extractVideoFrame(
  file: File,
  seekSeconds = 300,
): Promise<ExtractedVideoFrame> {
  const objectUrl = URL.createObjectURL(file);

  try {
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    video.src = objectUrl;

    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error("Could not load video metadata"));
    });

    const duration = Number.isFinite(video.duration) ? video.duration : 0;
    const seekTime =
      duration > 0
        ? Math.min(Math.max(seekSeconds, 0.5), Math.max(duration - 0.1, 0.5))
        : 0.5;

    video.currentTime = seekTime;

    await new Promise<void>((resolve, reject) => {
      const onReady = () => {
        video.removeEventListener("seeked", onReady);
        video.removeEventListener("loadeddata", onReady);
        resolve();
      };
      video.onerror = () => reject(new Error("Could not seek video"));
      video.addEventListener("seeked", onReady);
      video.addEventListener("loadeddata", onReady);
    });

    if (typeof video.requestVideoFrameCallback === "function") {
      await new Promise<void>((resolve) => {
        video.requestVideoFrameCallback(() => resolve());
      });
    } else {
      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      });
    }

    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) {
      throw new Error("Video has no readable dimensions");
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      throw new Error("Could not create canvas context");
    }

    ctx.drawImage(video, 0, 0, width, height);

    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (result) => {
          if (result) {
            resolve(result);
          } else {
            reject(new Error("Could not encode frame"));
          }
        },
        "image/jpeg",
        0.85,
      );
    });

    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);

    return { blob, dataUrl, width, height };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
