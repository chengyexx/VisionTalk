/**
 * Pixel-level frame difference detection.
 * Compares two Base64 JPEG frames by decoding to ImageData and
 * computing the percentage of pixels that differ beyond a tolerance.
 */

const THUMBNAIL_SIZE = 64; // Downscale for fast comparison

/**
 * Convert a Base64 JPEG string to a small ImageData for comparison.
 */
async function base64ToImageData(base64: string): Promise<ImageData> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = THUMBNAIL_SIZE;
      canvas.height = THUMBNAIL_SIZE;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("Canvas context unavailable"));
        return;
      }
      ctx.drawImage(img, 0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
      resolve(ctx.getImageData(0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE));
    };
    img.onerror = () => reject(new Error("Failed to load image"));
    img.src = base64;
  });
}

/**
 * Check if the current frame is significantly different from the previous one.
 * @param prev - Previous frame as Base64 JPEG (or null for first frame)
 * @param curr - Current frame as Base64 JPEG
 * @param threshold - Percentage of changed pixels to trigger (0.0-1.0, default 0.05 = 5%)
 * @returns true if this is a key frame (significant change detected)
 */
export async function isKeyFrame(
  prev: string | null,
  curr: string,
  threshold: number = 0.05
): Promise<boolean> {
  if (!prev) return true; // First frame is always a key frame

  const prevData = await base64ToImageData(prev);
  const currData = await base64ToImageData(curr);

  const { data: prevPixels } = prevData;
  const { data: currPixels } = currData;

  let diffCount = 0;
  const totalPixels = THUMBNAIL_SIZE * THUMBNAIL_SIZE;

  for (let i = 0; i < prevPixels.length; i += 4) {
    const rDiff = Math.abs(prevPixels[i] - currPixels[i]);
    const gDiff = Math.abs(prevPixels[i + 1] - currPixels[i + 1]);
    const bDiff = Math.abs(prevPixels[i + 2] - currPixels[i + 2]);

    // A pixel is "different" if any channel differs by more than 30
    if (rDiff > 30 || gDiff > 30 || bDiff > 30) {
      diffCount++;
    }
  }

  const diffRatio = diffCount / totalPixels;
  return diffRatio >= threshold;
}
