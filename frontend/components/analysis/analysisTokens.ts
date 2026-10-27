import {
  appTheme,
  type AppThemeTokens,
} from "@/components/applications/appTheme";
import {
  productSnapshotTokens,
  registerAnalysisTokenGetter,
  type SnapshotTokens,
} from "@/components/fantasy/snapshot/tokens";

export type AnalysisFormat = "product" | "application";

export type AnalysisTokens = SnapshotTokens;

/** Product / data-product default. */
export const PRODUCT_ANALYSIS_TOKENS: AnalysisTokens = {
  ...productSnapshotTokens,
};

function withAlpha(hex: string, alpha: number): string {
  const raw = hex.replace("#", "").trim();
  if (raw.length !== 6) {
    return hex;
  }
  const r = Number.parseInt(raw.slice(0, 2), 16);
  const g = Number.parseInt(raw.slice(2, 4), 16);
  const b = Number.parseInt(raw.slice(4, 6), 16);
  if (![r, g, b].every((n) => Number.isFinite(n))) {
    return hex;
  }
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Application theme mapping.
 * Semantic roles stay the same (navy = primary heading text, white = card surface).
 */
export function applicationTokensFromTheme(
  theme: AppThemeTokens
): AnalysisTokens {
  return {
    navy: theme.white,
    blue: theme.cyan,
    blueLight: withAlpha(theme.cyan, 0.12),
    white: theme.elevated,
    background: theme.midnight,
    success: theme.positive,
    successLight: withAlpha(theme.positive, 0.14),
    warning: theme.warning,
    warningLight: withAlpha(theme.warning, 0.14),
    negative: theme.negative,
    negativeLight: withAlpha(theme.negative, 0.14),
    purple: "#A78BFA",
    purpleLight: "rgba(167, 139, 250, 0.14)",
    textPrimary: theme.white,
    textSecondary: theme.silver,
    textMuted: theme.slate,
    border: theme.borderInput,
    divider: theme.border,
  };
}

/** Default application tokens (Midnight). */
export const APPLICATION_ANALYSIS_TOKENS: AnalysisTokens =
  applicationTokensFromTheme(appTheme);

export function tokensForFormat(
  format: AnalysisFormat,
  theme: AppThemeTokens = appTheme
): AnalysisTokens {
  return format === "application"
    ? applicationTokensFromTheme(theme)
    : PRODUCT_ANALYSIS_TOKENS;
}

export function analysisTokenCssVars(
  tokens: AnalysisTokens
): Record<string, string> {
  return {
    "--analysis-navy": tokens.navy,
    "--analysis-blue": tokens.blue,
    "--analysis-blue-light": tokens.blueLight,
    "--analysis-white": tokens.white,
    "--analysis-background": tokens.background,
    "--analysis-success": tokens.success,
    "--analysis-success-light": tokens.successLight,
    "--analysis-warning": tokens.warning,
    "--analysis-warning-light": tokens.warningLight,
    "--analysis-negative": tokens.negative,
    "--analysis-negative-light": tokens.negativeLight,
    "--analysis-purple": tokens.purple,
    "--analysis-purple-light": tokens.purpleLight,
    "--analysis-text-primary": tokens.textPrimary,
    "--analysis-text-secondary": tokens.textSecondary,
    "--analysis-text-muted": tokens.textMuted,
    "--analysis-border": tokens.border,
    "--analysis-divider": tokens.divider,
  };
}

let activeTokens: AnalysisTokens = PRODUCT_ANALYSIS_TOKENS;

registerAnalysisTokenGetter(() => activeTokens);

/** Set during AnalysisFormatProvider render so snapshotTokens Proxy resolves correctly. */
export function setActiveAnalysisTokens(
  tokens: AnalysisTokens
): void {
  activeTokens = tokens;
}

export function getActiveAnalysisTokens(): AnalysisTokens {
  return activeTokens;
}
