"use client";

import { appTheme } from "@/components/applications/appTheme";

const MAX_BYTES = 900_000;
const SQUARE_MAX_EDGE = 128;
const WORDMARK_MAX_HEIGHT = 96;
const WORDMARK_MAX_WIDTH = 480;

export type ApplicationLogoType = "square" | "wordmark";

export function isLogoDataUrl(value: string | null | undefined): boolean {
  return Boolean(value && value.startsWith("data:image/"));
}

export function normalizeLogoType(
  value?: string | null
): ApplicationLogoType {
  return value === "wordmark" ? "wordmark" : "square";
}

/** Read and optionally downscale an image file to a data URL. */
export async function fileToLogoDataUrl(
  file: File,
  logoType: ApplicationLogoType = "square"
): Promise<string> {
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

  if (logoType === "wordmark") {
    return downscaleDataUrl(dataUrl, {
      maxWidth: WORDMARK_MAX_WIDTH,
      maxHeight: WORDMARK_MAX_HEIGHT,
    });
  }

  return downscaleDataUrl(dataUrl, {
    maxWidth: SQUARE_MAX_EDGE,
    maxHeight: SQUARE_MAX_EDGE,
  });
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
  limits: { maxWidth: number; maxHeight: number }
): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(
        1,
        limits.maxWidth / Math.max(img.width, 1),
        limits.maxHeight / Math.max(img.height, 1)
      );
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
  /** Square mark size, or wordmark height */
  size?: number;
  variant?: ApplicationLogoType;
  className?: string;
}

export default function ApplicationLogo({
  src,
  name = "Application",
  size = 28,
  variant = "square",
  className = "",
}: ApplicationLogoProps) {
  const isWordmark = variant === "wordmark";

  if (isLogoDataUrl(src) || (src && src.startsWith("http"))) {
    if (isWordmark) {
      const height = size;
      const maxWidth = Math.round(height * 5);
      return (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={name}
          title={name}
          className={`shrink-0 object-contain object-left ${className}`}
          style={{
            height,
            width: "auto",
            maxWidth,
            maxHeight: height,
          }}
        />
      );
    }

    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        title={name}
        width={size}
        height={size}
        className={`shrink-0 object-contain ${className}`}
        style={{
          width: size,
          height: size,
        }}
      />
    );
  }

  // Fallback mark — square only; wordmark without an image uses title text instead.
  if (isWordmark) {
    return null;
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
