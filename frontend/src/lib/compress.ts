// FR-2.5: Client-side image compression — ≤ 1600px, JPEG 85%
import imageCompression from "browser-image-compression";

export async function compressImage(file: File): Promise<File> {
  return imageCompression(file, {
    maxSizeMB: 0.5,
    maxWidthOrHeight: 1600,
    useWebWorker: true,
    fileType: "image/jpeg",
    initialQuality: 0.85,
  });
}
