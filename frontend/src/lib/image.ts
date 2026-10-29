const MAX_DIMENSION = 1600;
const JPEG_QUALITY = 0.86;
const SKIP_BELOW_BYTES = 1.5 * 1024 * 1024;

export const MAX_IMAGE_INPUT_BYTES = 15 * 1024 * 1024;
export const MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024;

/** Keep the aspect ratio while fitting inside a square bounding box. */
export function targetDimensions(
  width: number,
  height: number,
  maxDimension = MAX_DIMENSION,
): { width: number; height: number } {
  if (width <= 0 || height <= 0) return { width: 0, height: 0 };
  const longest = Math.max(width, height);
  if (longest <= maxDimension) return { width, height };
  const scale = maxDimension / longest;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

function loadImage(file: File): Promise<{ image: HTMLImageElement; revoke: () => void }> {
  const url = URL.createObjectURL(file);
  const image = new Image();
  image.decoding = "async";
  return new Promise((resolve, reject) => {
    image.onload = () => resolve({ image, revoke: () => URL.revokeObjectURL(url) });
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("image_decode_failed"));
    };
    image.src = url;
  });
}

/**
 * Best-effort browser-side compression before upload. The backend always
 * processes the image again, so failures fall back to the original file.
 */
export async function compressImageForUpload(file: File): Promise<File> {
  if (!file.type.startsWith("image/") || file.type === "image/svg+xml") return file;
  // Animated GIFs lose their animation on a canvas; leave them to the backend.
  if (file.type === "image/gif") return file;

  let loaded: { image: HTMLImageElement; revoke: () => void } | null = null;
  try {
    loaded = await loadImage(file);
    const { image } = loaded;
    // Avoid allocating a huge canvas; the backend applies the same limit.
    if (image.naturalWidth * image.naturalHeight > 40_000_000) return file;
    const target = targetDimensions(image.naturalWidth, image.naturalHeight);
    const resized = target.width !== image.naturalWidth || target.height !== image.naturalHeight;
    if (!resized && file.size <= SKIP_BELOW_BYTES) return file;

    const canvas = document.createElement("canvas");
    canvas.width = target.width;
    canvas.height = target.height;
    const context = canvas.getContext("2d");
    if (!context) return file;

    // JPEG has no alpha channel; flatten transparent pixels onto white.
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, target.width, target.height);
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(image, 0, 0, target.width, target.height);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
    );
    if (!blob) return file;
    if (!resized && blob.size >= file.size) return file;

    const baseName = file.name.replace(/\.[^.]+$/, "") || "image";
    return new File([blob], `${baseName}.jpg`, {
      type: "image/jpeg",
      lastModified: Date.now(),
    });
  } catch {
    return file;
  } finally {
    loaded?.revoke();
  }
}
