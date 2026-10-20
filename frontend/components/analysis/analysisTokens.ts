import { appTheme } from "@/components/applications/appTheme";
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

/**
 * Application command-center mapping.
 * Semantic roles stay the same (navy = primary heading text, white = card surface).
 */
export const APPLICATION_ANALYSIS_TOKENS: AnalysisTokens = {
  navy: appTheme.white,
  blue: appTheme.cyan,
  blueLight: "rgba(0, 229, 255, 0.12)",
  white: appTheme.elevated,
  background: appTheme.midnight,
  success: appTheme.positive,
  successLight: "rgba(37, 214, 149, 0.14)",
  warning: appTheme.warning,
  warningLight: "rgba(255, 181, 71, 0.14)",
  negative: appTheme.negative,
  negativeLight: "rgba(255, 85, 112, 0.14)",
  purple: "#A78BFA",
  purpleLight: "rgba(167, 139, 250, 0.14)",
  textPrimary: appTheme.white,
  textSecondary: appTheme.silver,
  textMuted: appTheme.slate,
  border: "rgba(255, 255, 255, 0.10)",
  divider: "rgba(255, 255, 255, 0.06)",
};

export function tokensForFormat(
  format: AnalysisFormat
): AnalysisTokens {
  return format === "application"
    ? APPLICATION_ANALYSIS_TOKENS
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
