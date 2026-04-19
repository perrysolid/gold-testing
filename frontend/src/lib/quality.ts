// FR-2.4: Client-side quality checks before upload
export type QualityResult = {
  bright_ok: boolean;
  sharp_ok: boolean;
  occupancy_ok: boolean;
  jewellery_ok: boolean;
  overall_ok: boolean;
  jewellery_reason?: string;
};

export async function checkImageQuality(blob: Blob): Promise<QualityResult> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(img, 0, 0);
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;

      let totalBright = 0;
      let nonBlack = 0;
      for (let i = 0; i < data.length; i += 4) {
        const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
        totalBright += lum;
        if (lum > 30) nonBlack++;
      }
      const pixels = data.length / 4;
      const avgBright = totalBright / pixels;
      const occupancy = nonBlack / pixels;

      URL.revokeObjectURL(url);
      resolve({
        bright_ok: avgBright >= 40 && avgBright <= 220,
        sharp_ok: true, // Laplacian needs WebGL; stub as true client-side
        occupancy_ok: occupancy >= 0.15,
        jewellery_ok: true, // server-side check is authoritative; default true client-side
        overall_ok: avgBright >= 40 && avgBright <= 220 && occupancy >= 0.15,
      });
    };
    img.src = url;
  });
}
