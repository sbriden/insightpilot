/**
 * Analytical Applications design tokens.
 * Premium command-center aesthetic — controlled cyan, layered darkness.
 */

export const appTheme = {
  // Surfaces
  obsidian: "#030507",
  midnight: "#07111C",
  deepBlue: "#0A1B30",
  panel: "#0A1624",
  elevated: "#0D1C2D",

  // Accents
  electric: "#008CFF",
  cyan: "#00E5FF",
  brightCyan: "#38F4FF",

  // Text
  white: "#F5F7FA",
  silver: "#A8B3C2",
  slate: "#667384",
  neutral: "#8B98A8",

  // Semantic
  positive: "#25D695",
  negative: "#FF5570",
  warning: "#FFB547",

  // Borders / glow
  border: "rgba(255,255,255,0.06)",
  borderHover: "rgba(0,229,255,0.20)",
  borderActive: "rgba(0,229,255,0.35)",
  borderInput: "rgba(255,255,255,0.10)",
  focusRing: "rgba(0,229,255,0.45)",
  glowSoft: "0 0 18px rgba(0,229,255,0.12)",
  glowActive: "0 0 24px rgba(0,229,255,0.18)",

  gradient: "linear-gradient(135deg, #008CFF 0%, #00E5FF 100%)",
  beam: "linear-gradient(90deg, transparent, rgba(0,229,255,0.55), transparent)",
} as const;

export type AppTheme = typeof appTheme;
