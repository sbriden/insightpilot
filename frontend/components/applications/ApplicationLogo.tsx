"use client";

import { appTheme } from "@/components/applications/appTheme";

const MAX_BYTES = 900_000;
const TARGET_SIZE = 128;

export function isLogoDataUrl(value: string | null | undefined): boolean {
  return Boolean(value && value.startsWith("data:image/"));
}

/** Read and optionally downscale an image file to a data URL. */
export async function fileToLogoDataUrl(file: File): Promise<string> {
  if (!file.type.startsWith("image/")) {
    throw new Error("Please choose an image file (PNG, JPG, SVG, or WebP).");
  }
  if (file.size > 4_000_000) {
    throw new Error("Logo must be under 4 MB.");
  }

  const dataUrl = await readFileAsDataUrl(file);
  if (file.type === "image/svg+xml") {
    if (dataUrl.length > MAX_BYTES) {
      throw new Error("SVG logo is too large. Try a smaller file.");
    }
    return dataUrl;
  }

  return downscaleDataUrl(dataUrl, TARGET_SIZE);
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Unable to read logo file."));
    reader.readAsDataURL(file);
  });
}

function downscaleDataUrl(
  dataUrl: string,
  maxEdge: number
): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxEdge / Math.max(img.width, img.height));
      const width = Math.max(1, Math.round(img.width * scale));
      const height = Math.max(1, Math.round(img.height * scale));
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(dataUrl);
        return;
      }
      ctx.clearRect(0, 0, width, height);
      ctx.drawImage(img, 0, 0, width, height);
      const out = canvas.toDataURL("image/png");
      if (out.length > MAX_BYTES) {
        reject(new Error("Logo is still too large after resize."));
        return;
      }
      resolve(out);
    };
    img.onerror = () => reject(new Error("Unable to process logo image."));
    img.src = dataUrl;
  });
}

interface ApplicationLogoProps {
  src?: string | null;
  name?: string;
  size?: number;
  className?: string;
}

export default function ApplicationLogo({
  src,
  name = "Application",
  size = 28,
  className = "",
}: ApplicationLogoProps) {
  if (isLogoDataUrl(src) || (src && src.startsWith("http"))) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        title={name}
        width={size}
        height={size}
        className={`shrink-0 rounded-md object-contain ${className}`}
        style={{
          width: size,
          height: size,
          background: appTheme.deepBlue,
          border: `1px solid ${appTheme.borderActive}`,
          boxShadow: appTheme.glowSoft,
        }}
      />
    );
  }

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${className}`}
      style={{
        width: size,
        height: size,
        background: appTheme.deepBlue,
        color: appTheme.cyan,
        boxShadow: appTheme.glowSoft,
        border: `1px solid ${appTheme.borderActive}`,
      }}
      aria-hidden
    >
      {src && src.length <= 3 ? src : "◉"}
    </span>
  );
}
