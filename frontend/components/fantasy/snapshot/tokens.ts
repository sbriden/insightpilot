/** InsightPilot Player Snapshot design tokens (style guide). */

export const productSnapshotTokens = {
  navy: "#0B1F3A",
  blue: "#1677FF",
  blueLight: "#EAF3FF",
  white: "#FFFFFF",
  background: "#F5F7FA",
  success: "#16A34A",
  successLight: "#EAF8EF",
  warning: "#F59E0B",
  warningLight: "#FFF7E6",
  negative: "#DC2626",
  negativeLight: "#FDECEC",
  purple: "#7C3AED",
  purpleLight: "#F3EEFF",
  textPrimary: "#172B4D",
  textSecondary: "#5B6B7F",
  textMuted: "#8996A8",
  border: "#DCE3EC",
  divider: "#E8EDF3",
} as const;

export type SnapshotTokens = {
  -readonly [K in keyof typeof productSnapshotTokens]: string;
};

type TokenGetter = () => SnapshotTokens;

let analysisTokenGetter: TokenGetter | null = null;

/** Registered by analysis format module so product pages stay static. */
export function registerAnalysisTokenGetter(
  getter: TokenGetter
): void {
  analysisTokenGetter = getter;
}

/**
 * Active analysis tokens. Inside an application format provider these
 * resolve to the dark command-center map; otherwise product defaults.
 */
export const snapshotTokens: SnapshotTokens = new Proxy(
  productSnapshotTokens as SnapshotTokens,
  {
    get(target, prop, receiver) {
      const source = analysisTokenGetter
        ? analysisTokenGetter()
        : target;
      return Reflect.get(source, prop, receiver);
    },
  }
);

export function assessmentStyles(
  label: string | null | undefined
): { bg: string; text: string; border: string } {
  switch ((label || "").toLowerCase()) {
    case "elite":
    case "strong":
      return {
        bg: snapshotTokens.successLight,
        text: snapshotTokens.success,
        border: snapshotTokens.success,
      };
    case "solid":
      return {
        bg: snapshotTokens.blueLight,
        text: snapshotTokens.blue,
        border: snapshotTokens.blue,
      };
    case "cautious":
      return {
        bg: snapshotTokens.warningLight,
        text: snapshotTokens.warning,
        border: snapshotTokens.warning,
      };
    case "weak":
      return {
        bg: snapshotTokens.negativeLight,
        text: snapshotTokens.negative,
        border: snapshotTokens.negative,
      };
    default:
      return {
        bg: snapshotTokens.background,
        text: snapshotTokens.textSecondary,
        border: snapshotTokens.border,
      };
  }
}

export function formatMetricValue(
  value: number | null | undefined,
  digits = 1
): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  if (Number.isInteger(value) && Math.abs(value) >= 10) {
    return value.toLocaleString();
  }
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits > 0 ? 1 : 0,
  });
}

export function formatScore(
  value: number | null | undefined
): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return String(Math.round(value));
}
