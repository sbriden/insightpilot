/**
 * Analytical Applications theme system.
 *
 * A theme is more than a palette: colors + chrome (typography, spacing,
 * radii, elevation, motion, controls, selection). Product logic stays
 * theme-agnostic; presentation is driven by these tokens / CSS vars.
 */

export type AppThemeId =
  | "midnight"
  | "daylight"
  | "carbon"
  | "stadium"
  | "harbor"
  | "slate";

/** Color / surface / accent palette */
export interface AppThemeTokens {
  obsidian: string;
  midnight: string;
  deepBlue: string;
  panel: string;
  elevated: string;
  electric: string;
  cyan: string;
  brightCyan: string;
  white: string;
  silver: string;
  slate: string;
  neutral: string;
  positive: string;
  negative: string;
  warning: string;
  border: string;
  borderHover: string;
  borderActive: string;
  borderInput: string;
  focusRing: string;
  glowSoft: string;
  glowActive: string;
  gradient: string;
  beam: string;
  ctaText: string;
}

/**
 * Non-color chrome — layout density, type, controls, motion.
 * Drawn from Slaterator Chrome / editorial sports-slate guidance.
 */
export interface AppThemeChrome {
  // Typography
  fontSans: string;
  fontDisplay: string;
  fontVariantNumeric: string;
  headingTracking: string;
  labelTracking: string;
  typePageTitle: string;
  typeSection: string;
  typeCard: string;
  typeBody: string;
  typeMeta: string;
  typeMetric: string;

  // Spacing scale
  space1: string;
  space2: string;
  space3: string;
  space4: string;
  space5: string;
  space6: string;
  sectionGap: string;
  cardPadding: string;

  // Radii
  radiusCard: string;
  radiusButton: string;
  radiusInput: string;
  radiusControl: string;

  // Elevation / texture
  shadowCard: string;
  shadowRaised: string;
  beamOpacity: string;

  // Motion
  durationFast: string;
  durationNormal: string;
  easing: string;

  // Controls / shell
  buttonHeight: string;
  buttonWeight: string;
  touchTarget: string;
  headerHeight: string;
  navWidth: string;
  bottomNavHeight: string;

  // Selection / focus
  selectionBg: string;
  selectionBorder: string;
  focusRingWidth: string;
}

export interface AppThemeDefinition {
  id: AppThemeId;
  name: string;
  description: string;
  swatches: [string, string, string];
  scheme: "dark" | "light";
  tokens: AppThemeTokens;
  chrome: AppThemeChrome;
}

/* ── Color palettes ─────────────────────────────────────────── */

const midnightTokens: AppThemeTokens = {
  obsidian: "#030507",
  midnight: "#07111C",
  deepBlue: "#0A1B30",
  panel: "#0A1624",
  elevated: "#0D1C2D",
  electric: "#008CFF",
  cyan: "#00E5FF",
  brightCyan: "#38F4FF",
  white: "#F5F7FA",
  silver: "#A8B3C2",
  slate: "#667384",
  neutral: "#8B98A8",
  positive: "#25D695",
  negative: "#FF5570",
  warning: "#FFB547",
  border: "rgba(255,255,255,0.06)",
  borderHover: "rgba(0,229,255,0.20)",
  borderActive: "rgba(0,229,255,0.35)",
  borderInput: "rgba(255,255,255,0.10)",
  focusRing: "rgba(0,229,255,0.45)",
  glowSoft: "0 0 18px rgba(0,229,255,0.12)",
  glowActive: "0 0 24px rgba(0,229,255,0.18)",
  gradient: "linear-gradient(135deg, #008CFF 0%, #00E5FF 100%)",
  beam: "linear-gradient(90deg, transparent, rgba(0,229,255,0.55), transparent)",
  ctaText: "#030507",
};

const daylightTokens: AppThemeTokens = {
  obsidian: "#F3F5F8",
  midnight: "#FFFFFF",
  deepBlue: "#E8EEF5",
  panel: "#FFFFFF",
  elevated: "#F7F9FC",
  electric: "#0B5FFF",
  cyan: "#0B5FFF",
  brightCyan: "#3B82F6",
  white: "#0F172A",
  silver: "#475569",
  slate: "#64748B",
  neutral: "#94A3B8",
  positive: "#059669",
  negative: "#DC2626",
  warning: "#D97706",
  border: "rgba(15,23,42,0.10)",
  borderHover: "rgba(11,95,255,0.25)",
  borderActive: "rgba(11,95,255,0.40)",
  borderInput: "rgba(15,23,42,0.14)",
  focusRing: "rgba(11,95,255,0.35)",
  glowSoft: "0 0 18px rgba(11,95,255,0.10)",
  glowActive: "0 0 24px rgba(11,95,255,0.16)",
  gradient: "linear-gradient(135deg, #0B5FFF 0%, #2563EB 100%)",
  beam: "linear-gradient(90deg, transparent, rgba(11,95,255,0.45), transparent)",
  ctaText: "#FFFFFF",
};

const carbonTokens: AppThemeTokens = {
  obsidian: "#050505",
  midnight: "#0C0C0E",
  deepBlue: "#141418",
  panel: "#101014",
  elevated: "#1A1A1F",
  electric: "#3B82F6",
  cyan: "#60A5FA",
  brightCyan: "#93C5FD",
  white: "#F4F4F5",
  silver: "#A1A1AA",
  slate: "#71717A",
  neutral: "#8B8B96",
  positive: "#34D399",
  negative: "#F87171",
  warning: "#FBBF24",
  border: "rgba(255,255,255,0.08)",
  borderHover: "rgba(96,165,250,0.25)",
  borderActive: "rgba(96,165,250,0.40)",
  borderInput: "rgba(255,255,255,0.12)",
  focusRing: "rgba(96,165,250,0.45)",
  glowSoft: "0 0 18px rgba(59,130,246,0.12)",
  glowActive: "0 0 24px rgba(59,130,246,0.20)",
  gradient: "linear-gradient(135deg, #2563EB 0%, #60A5FA 100%)",
  beam: "linear-gradient(90deg, transparent, rgba(96,165,250,0.50), transparent)",
  ctaText: "#050505",
};

const stadiumTokens: AppThemeTokens = {
  obsidian: "#0A0908",
  midnight: "#14110E",
  deepBlue: "#1C1814",
  panel: "#1A1612",
  elevated: "#241F1A",
  electric: "#E8A317",
  cyan: "#F0B429",
  brightCyan: "#F6C95A",
  white: "#F7F1E8",
  silver: "#B8A99A",
  slate: "#7A6F63",
  neutral: "#9A8D80",
  positive: "#3DCF8E",
  negative: "#F07167",
  warning: "#F0B429",
  border: "rgba(247,241,232,0.08)",
  borderHover: "rgba(240,180,41,0.25)",
  borderActive: "rgba(240,180,41,0.40)",
  borderInput: "rgba(247,241,232,0.12)",
  focusRing: "rgba(240,180,41,0.45)",
  glowSoft: "0 0 18px rgba(232,163,23,0.14)",
  glowActive: "0 0 24px rgba(232,163,23,0.22)",
  gradient: "linear-gradient(135deg, #C8890F 0%, #F0B429 100%)",
  beam: "linear-gradient(90deg, transparent, rgba(240,180,41,0.55), transparent)",
  ctaText: "#0A0908",
};

const harborTokens: AppThemeTokens = {
  obsidian: "#031014",
  midnight: "#071A1F",
  deepBlue: "#0B242C",
  panel: "#0A1E24",
  elevated: "#0F2A32",
  electric: "#14B8A6",
  cyan: "#2DD4BF",
  brightCyan: "#5EEAD4",
  white: "#F0FDFA",
  silver: "#99B4B0",
  slate: "#5F7A76",
  neutral: "#7A9692",
  positive: "#34D399",
  negative: "#FB7185",
  warning: "#FBBF24",
  border: "rgba(240,253,250,0.07)",
  borderHover: "rgba(45,212,191,0.22)",
  borderActive: "rgba(45,212,191,0.38)",
  borderInput: "rgba(240,253,250,0.12)",
  focusRing: "rgba(45,212,191,0.45)",
  glowSoft: "0 0 18px rgba(45,212,191,0.12)",
  glowActive: "0 0 24px rgba(45,212,191,0.20)",
  gradient: "linear-gradient(135deg, #0D9488 0%, #2DD4BF 100%)",
  beam: "linear-gradient(90deg, transparent, rgba(45,212,191,0.55), transparent)",
  ctaText: "#031014",
};

const slateTokens: AppThemeTokens = {
  obsidian: "#080D0F",
  midnight: "#12191B",
  deepBlue: "#0D1416",
  panel: "#12191B",
  elevated: "#1A2325",
  electric: "#37BD87",
  cyan: "#63E6AD",
  brightCyan: "#80F0BE",
  white: "#F5F3EB",
  silver: "#B3BCB9",
  slate: "#7D8B87",
  neutral: "#9AA7A3",
  positive: "#63E6AD",
  negative: "#FF777D",
  warning: "#F2C879",
  border: "#293436",
  borderHover: "rgba(99,230,173,0.25)",
  borderActive: "rgba(99,230,173,0.38)",
  borderInput: "#3A484A",
  focusRing: "rgba(99,230,173,0.45)",
  glowSoft: "0 1px 2px rgba(0,0,0,0.35)",
  glowActive: "0 2px 8px rgba(0,0,0,0.40)",
  gradient: "linear-gradient(180deg, #63E6AD 0%, #37BD87 100%)",
  beam: "linear-gradient(90deg, transparent, rgba(99,230,173,0.35), transparent)",
  ctaText: "#07110D",
};

/* ── Chrome profiles ────────────────────────────────────────── */

/** Command-center chrome — tighter, glow-forward (BetBot / Midnight). */
const commandCenterChrome: AppThemeChrome = {
  fontSans: "var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontDisplay:
    "var(--font-app-display), var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontVariantNumeric: "normal",
  headingTracking: "-0.01em",
  labelTracking: "0.16em",
  typePageTitle: "1.75rem",
  typeSection: "1.125rem",
  typeCard: "0.9375rem",
  typeBody: "0.875rem",
  typeMeta: "0.6875rem",
  typeMetric: "1.75rem",
  space1: "0.25rem",
  space2: "0.5rem",
  space3: "0.75rem",
  space4: "1rem",
  space5: "1.25rem",
  space6: "2rem",
  sectionGap: "1.5rem",
  cardPadding: "1rem",
  radiusCard: "0.75rem",
  radiusButton: "0.5rem",
  radiusInput: "0.5rem",
  radiusControl: "0.5rem",
  shadowCard: "var(--ip-glow-soft)",
  shadowRaised: "var(--ip-glow-active)",
  beamOpacity: "1",
  durationFast: "150ms",
  durationNormal: "180ms",
  easing: "ease",
  buttonHeight: "2.25rem",
  buttonWeight: "600",
  touchTarget: "2.5rem",
  headerHeight: "3.5rem",
  navWidth: "14.5rem",
  bottomNavHeight: "4.25rem",
  selectionBg: "rgba(0,229,255,0.12)",
  selectionBorder: "rgba(0,229,255,0.35)",
  focusRingWidth: "0",
};

/** Clean light product chrome — airy, paper-like elevation. */
const daylightChrome: AppThemeChrome = {
  fontSans: "var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontDisplay:
    "var(--font-app-display), var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontVariantNumeric: "normal",
  headingTracking: "-0.02em",
  labelTracking: "0.12em",
  typePageTitle: "1.875rem",
  typeSection: "1.1875rem",
  typeCard: "1rem",
  typeBody: "0.9375rem",
  typeMeta: "0.75rem",
  typeMetric: "1.875rem",
  space1: "0.25rem",
  space2: "0.5rem",
  space3: "0.875rem",
  space4: "1.125rem",
  space5: "1.5rem",
  space6: "2.25rem",
  sectionGap: "1.75rem",
  cardPadding: "1.25rem",
  radiusCard: "1rem",
  radiusButton: "0.75rem",
  radiusInput: "0.75rem",
  radiusControl: "0.625rem",
  shadowCard: "0 1px 3px rgba(15,23,42,0.08)",
  shadowRaised: "0 8px 24px rgba(15,23,42,0.10)",
  beamOpacity: "0.7",
  durationFast: "140ms",
  durationNormal: "220ms",
  easing: "cubic-bezier(0.22, 1, 0.36, 1)",
  buttonHeight: "2.5rem",
  buttonWeight: "600",
  touchTarget: "2.75rem",
  headerHeight: "3.75rem",
  navWidth: "15.5rem",
  bottomNavHeight: "4.5rem",
  selectionBg: "rgba(11,95,255,0.10)",
  selectionBorder: "rgba(11,95,255,0.35)",
  focusRingWidth: "2px",
};

/** Stark industrial chrome — denser, sharper, cool. */
const carbonChrome: AppThemeChrome = {
  fontSans: "var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontDisplay:
    "var(--font-app-display), var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontVariantNumeric: "tabular-nums",
  headingTracking: "-0.025em",
  labelTracking: "0.18em",
  typePageTitle: "1.625rem",
  typeSection: "1.0625rem",
  typeCard: "0.875rem",
  typeBody: "0.8125rem",
  typeMeta: "0.625rem",
  typeMetric: "1.625rem",
  space1: "0.25rem",
  space2: "0.375rem",
  space3: "0.625rem",
  space4: "0.875rem",
  space5: "1.125rem",
  space6: "1.75rem",
  sectionGap: "1.25rem",
  cardPadding: "0.875rem",
  radiusCard: "0.5rem",
  radiusButton: "0.375rem",
  radiusInput: "0.375rem",
  radiusControl: "0.375rem",
  shadowCard: "0 0 0 1px rgba(255,255,255,0.04)",
  shadowRaised: "0 8px 20px rgba(0,0,0,0.45)",
  beamOpacity: "0.85",
  durationFast: "120ms",
  durationNormal: "160ms",
  easing: "ease-out",
  buttonHeight: "2.125rem",
  buttonWeight: "700",
  touchTarget: "2.375rem",
  headerHeight: "3.25rem",
  navWidth: "13.5rem",
  bottomNavHeight: "4rem",
  selectionBg: "rgba(96,165,250,0.12)",
  selectionBorder: "rgba(96,165,250,0.40)",
  focusRingWidth: "1px",
};

/** Game-day chrome — bold metrics, athletic touch targets. */
const stadiumChrome: AppThemeChrome = {
  fontSans: "var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontDisplay:
    "var(--font-app-display), var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontVariantNumeric: "tabular-nums",
  headingTracking: "-0.015em",
  labelTracking: "0.2em",
  typePageTitle: "2rem",
  typeSection: "1.25rem",
  typeCard: "1rem",
  typeBody: "0.9375rem",
  typeMeta: "0.75rem",
  typeMetric: "2.125rem",
  space1: "0.25rem",
  space2: "0.5rem",
  space3: "0.875rem",
  space4: "1.125rem",
  space5: "1.5rem",
  space6: "2.25rem",
  sectionGap: "1.75rem",
  cardPadding: "1.125rem",
  radiusCard: "0.875rem",
  radiusButton: "9999px",
  radiusInput: "0.75rem",
  radiusControl: "0.75rem",
  shadowCard: "0 2px 8px rgba(0,0,0,0.35)",
  shadowRaised: "0 10px 28px rgba(232,163,23,0.18)",
  beamOpacity: "1",
  durationFast: "160ms",
  durationNormal: "240ms",
  easing: "cubic-bezier(0.34, 1.2, 0.64, 1)",
  buttonHeight: "2.75rem",
  buttonWeight: "700",
  touchTarget: "3rem",
  headerHeight: "3.75rem",
  navWidth: "15.25rem",
  bottomNavHeight: "4.75rem",
  selectionBg: "rgba(240,180,41,0.12)",
  selectionBorder: "rgba(240,180,41,0.40)",
  focusRingWidth: "2px",
};

/** Calm harbor chrome — softer radii, roomier rhythm. */
const harborChrome: AppThemeChrome = {
  fontSans: "var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontDisplay:
    "var(--font-app-display), var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontVariantNumeric: "normal",
  headingTracking: "-0.012em",
  labelTracking: "0.14em",
  typePageTitle: "1.8125rem",
  typeSection: "1.1875rem",
  typeCard: "0.975rem",
  typeBody: "0.9rem",
  typeMeta: "0.72rem",
  typeMetric: "1.8125rem",
  space1: "0.25rem",
  space2: "0.55rem",
  space3: "0.85rem",
  space4: "1.1rem",
  space5: "1.4rem",
  space6: "2.15rem",
  sectionGap: "1.65rem",
  cardPadding: "1.15rem",
  radiusCard: "1.125rem",
  radiusButton: "0.85rem",
  radiusInput: "0.85rem",
  radiusControl: "0.85rem",
  shadowCard: "0 0 20px rgba(45,212,191,0.08)",
  shadowRaised: "0 12px 32px rgba(0,0,0,0.35)",
  beamOpacity: "0.75",
  durationFast: "170ms",
  durationNormal: "260ms",
  easing: "cubic-bezier(0.33, 1, 0.68, 1)",
  buttonHeight: "2.5rem",
  buttonWeight: "600",
  touchTarget: "2.75rem",
  headerHeight: "3.6rem",
  navWidth: "15rem",
  bottomNavHeight: "4.4rem",
  selectionBg: "rgba(45,212,191,0.12)",
  selectionBorder: "rgba(45,212,191,0.38)",
  focusRingWidth: "2px",
};

/**
 * Editorial sports slate chrome (Slaterator).
 * Larger touch targets, softer radii, no neon elevation, tabular nums.
 */
const slateChrome: AppThemeChrome = {
  fontSans: "var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontDisplay:
    "var(--font-app-display), var(--font-app-sans), ui-sans-serif, system-ui, sans-serif",
  fontVariantNumeric: "tabular-nums",
  headingTracking: "-0.02em",
  labelTracking: "0.14em",
  typePageTitle: "1.875rem",
  typeSection: "1.25rem",
  typeCard: "1rem",
  typeBody: "0.9375rem",
  typeMeta: "0.75rem",
  typeMetric: "2rem",
  space1: "0.25rem",
  space2: "0.5rem",
  space3: "0.75rem",
  space4: "1rem",
  space5: "1.25rem",
  space6: "2rem",
  sectionGap: "1.5rem",
  cardPadding: "1rem",
  radiusCard: "1rem",
  radiusButton: "0.875rem",
  radiusInput: "0.75rem",
  radiusControl: "0.75rem",
  shadowCard: "none",
  shadowRaised: "0 1px 2px rgba(0,0,0,0.35)",
  beamOpacity: "0.55",
  durationFast: "150ms",
  durationNormal: "200ms",
  easing: "ease",
  buttonHeight: "3rem",
  buttonWeight: "600",
  touchTarget: "2.75rem",
  headerHeight: "3.5rem",
  navWidth: "15rem",
  bottomNavHeight: "4.5rem",
  selectionBg: "rgba(99,230,173,0.12)",
  selectionBorder: "rgba(99,230,173,0.38)",
  focusRingWidth: "2px",
};

export const APP_THEMES: AppThemeDefinition[] = [
  {
    id: "midnight",
    name: "Midnight",
    description: "Command-center dark with electric cyan accents.",
    swatches: ["#07111C", "#008CFF", "#00E5FF"],
    scheme: "dark",
    tokens: midnightTokens,
    chrome: commandCenterChrome,
  },
  {
    id: "daylight",
    name: "Daylight",
    description: "Clean light surfaces with navy-blue accents.",
    swatches: ["#FFFFFF", "#0B5FFF", "#E8EEF5"],
    scheme: "light",
    tokens: daylightTokens,
    chrome: daylightChrome,
  },
  {
    id: "carbon",
    name: "Carbon",
    description: "Stark charcoal with cool blue highlights.",
    swatches: ["#0C0C0E", "#3B82F6", "#60A5FA"],
    scheme: "dark",
    tokens: carbonTokens,
    chrome: carbonChrome,
  },
  {
    id: "stadium",
    name: "Stadium",
    description: "Warm charcoal with amber game-day accents.",
    swatches: ["#14110E", "#E8A317", "#F0B429"],
    scheme: "dark",
    tokens: stadiumTokens,
    chrome: stadiumChrome,
  },
  {
    id: "harbor",
    name: "Harbor",
    description: "Deep teal waters with seafoam accents.",
    swatches: ["#071A1F", "#14B8A6", "#2DD4BF"],
    scheme: "dark",
    tokens: harborTokens,
    chrome: harborChrome,
  },
  {
    id: "slate",
    name: "Slate",
    description:
      "Editorial sports slate — graphite surfaces, mint accents, tactile chrome.",
    swatches: ["#12191B", "#63E6AD", "#F5F3EB"],
    scheme: "dark",
    tokens: slateTokens,
    chrome: slateChrome,
  },
];

export const DEFAULT_APP_THEME_ID: AppThemeId = "midnight";

export function isAppThemeId(value: unknown): value is AppThemeId {
  return (
    typeof value === "string" &&
    APP_THEMES.some((theme) => theme.id === value)
  );
}

export function normalizeAppThemeId(
  value?: string | null
): AppThemeId {
  return isAppThemeId(value) ? value : DEFAULT_APP_THEME_ID;
}

export function getAppThemeDefinition(
  themeId?: string | null
): AppThemeDefinition {
  const id = normalizeAppThemeId(themeId);
  return (
    APP_THEMES.find((theme) => theme.id === id) || APP_THEMES[0]
  );
}

export function getAppThemeTokens(
  themeId?: string | null
): AppThemeTokens {
  return getAppThemeDefinition(themeId).tokens;
}

export function getAppThemeChrome(
  themeId?: string | null
): AppThemeChrome {
  return getAppThemeDefinition(themeId).chrome;
}

/** Default theme tokens — used by portal chrome (library, wizard). */
export const appTheme: AppThemeTokens = midnightTokens;

export type AppTheme = AppThemeTokens;

function chromeCssVars(chrome: AppThemeChrome): Record<string, string> {
  return {
    "--ip-font-sans": chrome.fontSans,
    "--ip-font-display": chrome.fontDisplay,
    "--ip-font-numeric": chrome.fontVariantNumeric,
    "--ip-heading-tracking": chrome.headingTracking,
    "--ip-label-tracking": chrome.labelTracking,
    "--ip-type-page-title": chrome.typePageTitle,
    "--ip-type-section": chrome.typeSection,
    "--ip-type-card": chrome.typeCard,
    "--ip-type-body": chrome.typeBody,
    "--ip-type-meta": chrome.typeMeta,
    "--ip-type-metric": chrome.typeMetric,
    "--ip-space-1": chrome.space1,
    "--ip-space-2": chrome.space2,
    "--ip-space-3": chrome.space3,
    "--ip-space-4": chrome.space4,
    "--ip-space-5": chrome.space5,
    "--ip-space-6": chrome.space6,
    "--ip-section-gap": chrome.sectionGap,
    "--ip-card-padding": chrome.cardPadding,
    "--ip-radius-card": chrome.radiusCard,
    "--ip-radius-button": chrome.radiusButton,
    "--ip-radius-input": chrome.radiusInput,
    "--ip-radius-control": chrome.radiusControl,
    "--ip-shadow-card": chrome.shadowCard,
    "--ip-shadow-raised": chrome.shadowRaised,
    "--ip-beam-opacity": chrome.beamOpacity,
    "--ip-duration-fast": chrome.durationFast,
    "--ip-duration-normal": chrome.durationNormal,
    "--ip-easing": chrome.easing,
    "--ip-button-height": chrome.buttonHeight,
    "--ip-button-weight": chrome.buttonWeight,
    "--ip-touch-target": chrome.touchTarget,
    "--ip-header-height": chrome.headerHeight,
    "--ip-nav-width": chrome.navWidth,
    "--ip-bottom-nav-height": chrome.bottomNavHeight,
    "--ip-selection-bg": chrome.selectionBg,
    "--ip-selection-border": chrome.selectionBorder,
    "--ip-focus-ring-width": chrome.focusRingWidth,
  };
}

export function appThemeCssVars(
  tokens: AppThemeTokens,
  themeId?: AppThemeId | string | null
): Record<string, string> {
  const id = normalizeAppThemeId(themeId);
  const chrome = getAppThemeChrome(id);

  const vars: Record<string, string> = {
    "--ip-obsidian": tokens.obsidian,
    "--ip-midnight": tokens.midnight,
    "--ip-deep": tokens.deepBlue,
    "--ip-panel": tokens.panel,
    "--ip-elevated": tokens.elevated,
    "--ip-electric": tokens.electric,
    "--ip-cyan": tokens.cyan,
    "--ip-bright": tokens.brightCyan,
    "--ip-white": tokens.white,
    "--ip-silver": tokens.silver,
    "--ip-slate": tokens.slate,
    "--ip-positive": tokens.positive,
    "--ip-negative": tokens.negative,
    "--ip-warning": tokens.warning,
    "--ip-border": tokens.border,
    "--ip-border-hover": tokens.borderHover,
    "--ip-border-active": tokens.borderActive,
    "--ip-border-input": tokens.borderInput,
    "--ip-focus": tokens.focusRing,
    "--ip-glow-soft": tokens.glowSoft,
    "--ip-glow-active": tokens.glowActive,
    "--ip-gradient": tokens.gradient,
    "--ip-beam": tokens.beam,
    "--ip-cta-text": tokens.ctaText,
    ...chromeCssVars(chrome),
  };

  if (id === "slate") {
    Object.assign(vars, {
      "--slate-bg": tokens.obsidian,
      "--slate-surface": tokens.midnight,
      "--slate-surface-raised": tokens.elevated,
      "--slate-surface-muted": tokens.deepBlue,
      "--slate-border": tokens.border,
      "--slate-border-strong": tokens.borderInput,
      "--slate-text": tokens.white,
      "--slate-text-secondary": tokens.silver,
      "--slate-text-muted": tokens.slate,
      "--slate-text-inverse": tokens.ctaText,
      "--slate-accent": tokens.cyan,
      "--slate-accent-hover": tokens.brightCyan,
      "--slate-accent-pressed": tokens.electric,
      "--slate-accent-subtle": chrome.selectionBg,
      "--slate-accent-border": chrome.selectionBorder,
      "--slate-positive": tokens.positive,
      "--slate-negative": tokens.negative,
      "--slate-warning": tokens.warning,
      "--slate-neutral": tokens.neutral,
      "--slate-radius-card": chrome.radiusCard,
      "--slate-radius-button": chrome.radiusButton,
      "--slate-space-card": chrome.cardPadding,
      "--slate-duration": chrome.durationNormal,
    });
  }

  return vars;
}
