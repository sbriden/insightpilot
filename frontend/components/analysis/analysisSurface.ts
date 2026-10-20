import type { AnalysisTokens } from "@/components/analysis/analysisTokens";
import type { CSSProperties } from "react";

/** Shared surface recipes so analyses stay consistent across formats. */
export function panelStyle(
  tokens: AnalysisTokens
): CSSProperties {
  return {
    background: tokens.white,
    border: `1px solid ${tokens.border}`,
    color: tokens.textPrimary,
  };
}

export function mutedPanelStyle(
  tokens: AnalysisTokens
): CSSProperties {
  return {
    background: tokens.background,
    border: `1px solid ${tokens.border}`,
    color: tokens.textPrimary,
  };
}

export function inputStyle(
  tokens: AnalysisTokens
): CSSProperties {
  return {
    background: tokens.background,
    border: `1px solid ${tokens.border}`,
    color: tokens.textPrimary,
  };
}

export function primaryButtonStyle(
  tokens: AnalysisTokens
): CSSProperties {
  const darkSurface =
    tokens.background.toLowerCase() !== "#f5f7fa";
  return {
    background: tokens.blue,
    color: darkSurface ? "#030507" : "#FFFFFF",
    border: `1px solid ${tokens.blue}`,
  };
}
