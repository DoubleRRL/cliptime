export interface SpeakerPanel {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
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

/** Port of backend panel_to_vertical_crop — crop a panel to 9:16. */
export function panelToVerticalCrop(
  panel: Pick<SpeakerPanel, "x" | "y" | "w" | "h">,
  srcW: number,
  srcH: number,
): CropRect {
  const { x: px, y: py, w: pw, h: ph } = panel;

  let cropH = ph;
  let cropW = roundToEven(Math.floor(cropH * (9 / 16)));

  if (cropW > pw) {
    cropW = roundToEven(pw);
    cropH = roundToEven(Math.floor(cropW * (16 / 9)));
  }

  const cx = px + Math.floor(pw / 2);
  const cy = py + Math.floor(ph / 2);

  let x1 = Math.max(px, Math.min(cx - Math.floor(cropW / 2), px + pw - cropW));
  let y1 = Math.max(py, Math.min(cy - Math.floor(cropH / 2), py + ph - cropH));

  x1 = Math.max(0, Math.min(x1, srcW - cropW));
  y1 = Math.max(0, Math.min(y1, srcH - cropH));

  return {
    x1,
    y1,
    x2: x1 + cropW,
    y2: y1 + cropH,
    width: cropW,
    height: cropH,
  };
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
