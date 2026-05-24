export interface SpeakerPanel {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  face_cx?: number;
  face_cy?: number;
}

export interface CropRect {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width: number;
  height: number;
}

function roundToEven(value: number): number {
  const rounded = Math.round(value);
  return rounded % 2 === 0 ? rounded : rounded - 1;
}

function isPortraitSource(srcW: number, srcH: number): boolean {
  if (srcH <= 0) return false;
  return srcW / srcH <= 9 / 16 + 0.02;
}

/** Mirror backend fit_portrait_crop — apr23-style head+shoulders 9:16 crop. */
export function panelToVerticalCrop(
  panel: Pick<SpeakerPanel, "x" | "y" | "w" | "h" | "face_cx" | "face_cy">,
  srcW: number,
  srcH: number,
): CropRect {
  const { x: px, y: py, w: pw, h: ph } = panel;
  const cx = panel.face_cx ?? px + Math.floor(pw / 2);
  const cy = panel.face_cy ?? Math.floor(srcH * 0.38);

  if (isPortraitSource(srcW, srcH)) {
    let cropW = roundToEven(srcW);
    let cropH = roundToEven(Math.floor(cropW * (16 / 9)));
    if (cropH > srcH) {
      cropH = roundToEven(srcH);
      cropW = roundToEven(Math.floor(cropH * (9 / 16)));
    }
    const x1 = Math.max(0, Math.min(roundToEven(cx - Math.floor(cropW / 2)), srcW - cropW));
    const y1 = Math.max(0, Math.min(roundToEven(cy - Math.floor(cropH * 0.38)), srcH - cropH));
    return { x1, y1, x2: x1 + cropW, y2: y1 + cropH, width: cropW, height: cropH };
  }

  let cropH = roundToEven(Math.min(srcH, Math.floor(srcH * 0.92)));
  let cropW = roundToEven(Math.floor(cropH * (9 / 16)));

  const minCropW = roundToEven(Math.floor(pw * 0.55));
  if (cropW < minCropW) {
    cropW = Math.min(minCropW, pw, srcW);
    cropW = roundToEven(cropW);
    cropH = roundToEven(Math.floor(cropW * (16 / 9)));
    if (cropH > srcH) {
      cropH = roundToEven(srcH);
      cropW = roundToEven(Math.floor(cropH * (9 / 16)));
    }
  }

  if (cropW > pw) {
    cropW = roundToEven(Math.min(pw, srcW));
    cropH = roundToEven(Math.floor(cropW * (16 / 9)));
  }

  let x1 = cx - Math.floor(cropW / 2);
  x1 = Math.max(px, Math.min(x1, px + pw - cropW));
  x1 = Math.max(0, Math.min(x1, srcW - cropW));

  let y1 = cy - Math.floor(cropH * 0.38);
  y1 = Math.max(py, Math.min(y1, py + ph - cropH));
  y1 = Math.max(0, Math.min(y1, srcH - cropH));

  return { x1, y1, x2: x1 + cropW, y2: y1 + cropH, width: cropW, height: cropH };
}

/** CSS background props to show a source-frame crop inside a 9:16 container. */
export function cropToBackgroundStyle(
  frameWidth: number,
  frameHeight: number,
  crop: CropRect,
  containerWidth: number,
  containerHeight: number,
): { backgroundSize: string; backgroundPosition: string } {
  const scaleX = containerWidth / crop.width;
  const scaleY = containerHeight / crop.height;
  const scale = Math.max(scaleX, scaleY);

  const bgWidth = frameWidth * scale;
  const bgHeight = frameHeight * scale;

  const offsetX = -crop.x1 * scale;
  const offsetY = -crop.y1 * scale;

  return {
    backgroundSize: `${bgWidth}px ${bgHeight}px`,
    backgroundPosition: `${offsetX}px ${offsetY}px`,
  };
}
