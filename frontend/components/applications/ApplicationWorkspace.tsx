"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  MoreHorizontal,
  RefreshCw,
} from "lucide-react";

import AnalysisRuntime from "@/components/applications/AnalysisRuntime";
import { ApplicationContextProvider } from "@/components/applications/ApplicationContext";
import ApplicationLogo, {
  isLogoDataUrl,
  normalizeLogoType,
} from "@/components/applications/ApplicationLogo";
import {
  getAnalysisNavIcon,
  shortAnalysisLabel,
} from "@/components/applications/analysisNavIcons";
import {
  ApplicationThemeProvider,
  useAppTheme,
  useAppThemeChrome,
} from "@/components/applications/ApplicationThemeContext";
import {
  getRegistryAnalysis,
  LEGACY_PLAYER_OVERVIEW_KEY,
  PLAYER_OVERVIEW_ANALYSIS_KEYS,
  sourceProductLabels,
} from "@/lib/analysisRegistry";
import {
  normalizeApplicationSettings,
  refreshNflverseData,
  type AnalyticalApplication,
} from "@/services/api";

export type ApplicationWorkspaceMode = "studio" | "published";

interface Props {
  application: AnalyticalApplication;
  /** studio = builder chrome; published = end-user web view */
  mode?: ApplicationWorkspaceMode;
}

interface NavGroup {
  label: string;
  analyses: Array<{ analysis_key: string; display_order: number }>;
}

function buildNavGroups(
  analyses: AnalyticalApplication["analyses"]
): NavGroup[] {
  const ordered = [...(analyses || [])].sort(
    (a, b) => (a.display_order ?? 0) - (b.display_order ?? 0)
  );
  const expanded = ordered.flatMap((row) => {
    if (row.analysis_key !== LEGACY_PLAYER_OVERVIEW_KEY) {
      return [row];
    }
    return PLAYER_OVERVIEW_ANALYSIS_KEYS.map((analysis_key) => ({
      ...row,
      analysis_key,
    }));
  });
  const groups: NavGroup[] = [];
  const indexByLabel = new Map<string, number>();

  for (const row of expanded) {
    const meta = getRegistryAnalysis(row.analysis_key);
    const label = (
      row.navigation_group ||
      meta?.data_product_label ||
      "Analyses"
    ).trim();
    const existing = indexByLabel.get(label);
    if (existing === undefined) {
      indexByLabel.set(label, groups.length);
      groups.push({ label, analyses: [row] });
    } else {
      groups[existing].analyses.push(row);
    }
  }
  return groups;
}

export default function ApplicationWorkspace({
  application,
  mode = "studio",
}: Props) {
  const settings = useMemo(
    () => normalizeApplicationSettings(application.settings),
    [application.settings]
  );

  return (
    <ApplicationThemeProvider themeId={settings.theme}>
      <ApplicationWorkspaceInner
        application={application}
        mode={mode}
        settings={settings}
      />
    </ApplicationThemeProvider>
  );
}

function ApplicationWorkspaceInner({
  application,
  mode = "studio",
  settings,
}: Props & {
  settings: ReturnType<typeof normalizeApplicationSettings>;
}) {
  const theme = useAppTheme();
  const chrome = useAppThemeChrome();
  const isPublished = mode === "published";
  const groups = useMemo(
    () => buildNavGroups(application.analyses),
    [application.analyses]
  );
  const flatKeys = useMemo(
    () => groups.flatMap((g) => g.analyses.map((a) => a.analysis_key)),
    [groups]
  );

  const [activeKey, setActiveKey] = useState(() => flatKeys[0] || "");
  const [navOpen, setNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [refreshKey, setRefreshKey] = useState(0);
  const [refreshLoading, setRefreshLoading] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const products = sourceProductLabels(flatKeys);
  const showLeftNav = settings.show_left_nav;
  const showTopTabs = settings.show_top_tabs;
  const showBottomTabs = settings.show_bottom_tabs;
  const showAnalysisTitle = settings.show_analysis_title;
  const logoType = normalizeLogoType(settings.logo_type);
  const hasWordmark =
    logoType === "wordmark" &&
    Boolean(
      isLogoDataUrl(application.icon) ||
        (application.icon && application.icon.startsWith("http"))
    );
  const publishedHref = `/applications/${application.id}/published`;

  const activeGroup = useMemo(
    () =>
      groups.find((group) =>
        group.analyses.some(
          (row) => row.analysis_key === activeKey
        )
      ) ?? null,
    [groups, activeKey]
  );

  async function handleDataRefresh() {
    if (refreshLoading) {
      return;
    }
    try {
      setRefreshLoading(true);
      setRefreshError(null);
      const result = await refreshNflverseData("incremental");
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("insightpilot:fantasy-data-refreshed", {
            detail: {
              mode: "incremental",
              status: result.status,
              validation_blocked_derived:
                result.validation_blocked_derived,
            },
          })
        );
      }
      setRefreshKey((key) => key + 1);
    } catch (error) {
      setRefreshError(
        error instanceof Error
          ? error.message
          : "Unable to refresh data."
      );
    } finally {
      setRefreshLoading(false);
    }
  }

  return (
    <ApplicationContextProvider>
      <div
        className="flex min-h-screen flex-col"
        style={{ background: theme.obsidian }}
      >
        <header
          className="flex shrink-0 items-center justify-between px-4 lg:px-5"
          style={{
            background: theme.midnight,
            height: chrome.headerHeight,
            minHeight: chrome.touchTarget,
          }}
        >
          <div className="flex min-w-0 items-center gap-3">
            {!isPublished ? (
              <>
                <Link
                  href="/applications"
                  className="shrink-0 text-sm transition-colors"
                  style={{ color: theme.slate }}
                >
                  ← Portal
                </Link>
                <span
                  className="hidden h-4 w-px sm:block"
                  style={{ background: theme.border }}
                />
              </>
            ) : null}
            {hasWordmark ? (
              <ApplicationLogo
                src={application.icon}
                name={application.name}
                variant="wordmark"
                size={32}
              />
            ) : (
              <>
                <ApplicationLogo
                  src={application.icon}
                  name={application.name}
                  variant="square"
                  size={28}
                />
                <div className="min-w-0">
                  <h1
                    className="ip-heading truncate text-[20px] font-semibold tracking-tight lg:text-[22px]"
                    style={{ color: theme.white }}
                  >
                    {application.name}
                  </h1>
                </div>
              </>
            )}
          </div>
          <div className="flex min-w-0 items-center gap-2">
            {!isPublished && refreshError ? (
              <p
                className="hidden max-w-[220px] truncate text-xs sm:block"
                style={{ color: theme.negative }}
                title={refreshError}
              >
                {refreshError}
              </p>
            ) : null}
            {showLeftNav ? (
              <button
                type="button"
                className="rounded-lg px-3 py-1.5 text-sm lg:hidden"
                style={{
                  color: theme.silver,
                  border: `1px solid ${theme.border}`,
                }}
                onClick={() => setNavOpen((v) => !v)}
              >
                Analyses
              </button>
            ) : null}
            {!isPublished ? (
              <>
                <Link
                  href={publishedHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open published view"
                  className="inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors"
                  style={{
                    color: theme.cyan,
                    border: `1px solid ${theme.borderActive}`,
                    background: "rgba(0,229,255,0.08)",
                  }}
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">View published</span>
                  <span className="sm:hidden">Published</span>
                </Link>
                <button
                  type="button"
                  title={
                    refreshLoading
                      ? "Refreshing data…"
                      : "Refresh data"
                  }
                  disabled={refreshLoading}
                  onClick={() => void handleDataRefresh()}
                  className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors disabled:opacity-60"
                  style={{ color: theme.silver }}
                >
                  <RefreshCw
                    className={[
                      "h-4 w-4",
                      refreshLoading ? "animate-spin" : "",
                    ].join(" ")}
                  />
                  <span className="hidden sm:inline">
                    {refreshLoading ? "Refreshing…" : "Refresh"}
                  </span>
                </button>
                <Link
                  href={`/applications/${application.id}/edit`}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium transition-colors"
                  style={{
                    color: theme.white,
                    background: theme.deepBlue,
                    border: `1px solid ${theme.border}`,
                  }}
                >
                  Settings
                </Link>
                <button
                  type="button"
                  className="rounded-lg p-2"
                  style={{ color: theme.slate }}
                  aria-label="More"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </button>
              </>
            ) : null}
          </div>
        </header>
        <div className="ip-app-beam shrink-0" />

        <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1">
          {showLeftNav ? (
          <aside
            className={[
              "shrink-0",
              navOpen ? "block" : "hidden lg:block",
            ].join(" ")}
            style={{
              width: chrome.navWidth,
              background: theme.midnight,
              borderRight: `1px solid ${theme.border}`,
            }}
          >
            <div
              className="px-4 py-4"
              style={{ borderBottom: `1px solid ${theme.border}` }}
            >
              <p
                className="ip-label"
                style={{ color: theme.slate }}
              >
                Application
              </p>
              <p
                className="mt-1 text-sm font-medium"
                style={{ color: theme.white }}
              >
                {flatKeys.length} analyses
              </p>
              {products ? (
                <p className="mt-0.5 text-xs" style={{ color: theme.slate }}>
                  {products}
                </p>
              ) : null}
            </div>

            <nav className="space-y-4 p-3" aria-label="Application analyses">
              {groups.map((group) => {
                const isCollapsed = Boolean(collapsed[group.label]);
                return (
                  <div key={group.label}>
                    <button
                      type="button"
                      onClick={() =>
                        setCollapsed((c) => ({
                          ...c,
                          [group.label]: !c[group.label],
                        }))
                      }
                      className="ip-label flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left transition-colors"
                      style={{
                        color: theme.slate,
                        transitionDuration: chrome.durationFast,
                      }}
                      aria-expanded={!isCollapsed}
                    >
                      {isCollapsed ? (
                        <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                      )}
                      <span className="truncate">{group.label}</span>
                    </button>
                    {!isCollapsed ? (
                      <div className="mt-1 space-y-0.5">
                        {group.analyses.map((row) => {
                          const meta = getRegistryAnalysis(row.analysis_key);
                          const selected = row.analysis_key === activeKey;
                          return (
                            <button
                              key={row.analysis_key}
                              type="button"
                              onClick={() => {
                                setActiveKey(row.analysis_key);
                                setNavOpen(false);
                              }}
                              className="relative block w-full px-3 py-2.5 text-left text-sm transition-all"
                              style={
                                selected
                                  ? {
                                      background: chrome.selectionBg,
                                      color: theme.white,
                                      borderRadius: chrome.radiusControl,
                                      boxShadow: chrome.shadowCard,
                                      transitionDuration: chrome.durationNormal,
                                    }
                                  : {
                                      color: theme.silver,
                                      borderRadius: chrome.radiusControl,
                                      transitionDuration: chrome.durationNormal,
                                    }
                              }
                            >
                              {selected ? (
                                <span
                                  className="absolute inset-y-1.5 left-0 w-[3px] rounded-r"
                                  style={{
                                    background: theme.cyan,
                                    boxShadow: theme.glowActive,
                                  }}
                                />
                              ) : null}
                              <span className="flex items-center gap-2 pl-1">
                                <span
                                  style={{
                                    color: selected
                                      ? theme.cyan
                                      : theme.slate,
                                  }}
                                >
                                  {selected ? "◉" : "○"}
                                </span>
                                <span className="font-medium">
                                  {meta?.name || row.analysis_key}
                                </span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </nav>
          </aside>
          ) : null}

          <main
            className="min-w-0 flex-1 overflow-auto p-4 lg:p-5 xl:p-6"
            style={{ background: theme.obsidian }}
          >
            {activeKey && activeGroup ? (
              <div className="min-h-0 flex-1 space-y-4">
                {showTopTabs ? (
                <header className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
                  <p
                    className="ip-label shrink-0"
                    style={{ color: theme.cyan }}
                  >
                    {activeGroup.label}
                  </p>
                  <nav
                    className="flex min-w-0 flex-wrap items-center gap-1"
                    role="tablist"
                    aria-label={`${activeGroup.label} analyses`}
                  >
                    {activeGroup.analyses.map((row) => {
                      const meta = getRegistryAnalysis(
                        row.analysis_key
                      );
                      const selected =
                        row.analysis_key === activeKey;
                      return (
                        <button
                          key={row.analysis_key}
                          type="button"
                          role="tab"
                          aria-selected={selected}
                          onClick={() => {
                            setActiveKey(row.analysis_key);
                            setNavOpen(false);
                          }}
                          className="px-3 py-1.5 text-sm font-medium transition-colors"
                          style={
                            selected
                              ? {
                                  background: chrome.selectionBg,
                                  color: theme.cyan,
                                  borderRadius: chrome.radiusControl,
                                  boxShadow: chrome.shadowCard,
                                  border: `1px solid ${chrome.selectionBorder}`,
                                  transitionDuration: chrome.durationFast,
                                }
                              : {
                                  color: theme.silver,
                                  borderRadius: chrome.radiusControl,
                                  transitionDuration: chrome.durationFast,
                                }
                          }
                        >
                          {meta?.name || row.analysis_key}
                        </button>
                      );
                    })}
                  </nav>
                </header>
                ) : null}
                <AnalysisRuntime
                  key={`${activeKey}:${refreshKey}`}
                  analysisKey={activeKey}
                  showTitle={showAnalysisTitle}
                />
              </div>
            ) : activeKey ? (
              <AnalysisRuntime
                key={`${activeKey}:${refreshKey}`}
                analysisKey={activeKey}
                showTitle={showAnalysisTitle}
              />
            ) : (
              <div
                className="ip-app-panel rounded-xl px-8 py-16 text-center"
              >
                <p className="ip-label" style={{ color: theme.cyan }}>
                  InsightPilot
                </p>
                <h2
                  className="ip-heading mt-3 font-semibold"
                  style={{
                    color: theme.white,
                    fontSize: chrome.typePageTitle,
                  }}
                >
                  {isPublished
                    ? "This application is empty"
                    : "Your analytical workspace is empty"}
                </h2>
                <p
                  className="mx-auto mt-2 max-w-md text-sm"
                  style={{ color: theme.silver }}
                >
                  {isPublished
                    ? "No analyses are available in this published application yet."
                    : "Add analyses from your data products to begin building your application."}
                </p>
                {!isPublished ? (
                  <Link
                    href={`/applications/${application.id}/edit`}
                    className="ip-app-cta mt-6 inline-flex rounded-lg px-4 py-2.5 text-sm"
                  >
                    + Add Analysis
                  </Link>
                ) : null}
              </div>
            )}
          </main>
        </div>

        {showBottomTabs && flatKeys.length > 0 ? (
          <nav
            className="z-20 shrink-0"
            style={{
              background: theme.midnight,
              borderTop: `1px solid ${theme.border}`,
              paddingBottom: "env(safe-area-inset-bottom, 0px)",
            }}
            aria-label="Bottom navigation"
          >
            <div className="mx-auto flex max-w-3xl items-stretch justify-around gap-1 overflow-x-auto px-2 py-2">
              {flatKeys.map((analysisKey) => {
                const meta = getRegistryAnalysis(analysisKey);
                const Icon = getAnalysisNavIcon(analysisKey);
                const selected = analysisKey === activeKey;
                const label = shortAnalysisLabel(
                  meta?.name || analysisKey
                );
                return (
                  <button
                    key={analysisKey}
                    type="button"
                    onClick={() => {
                      setActiveKey(analysisKey);
                      setNavOpen(false);
                    }}
                    className="flex min-w-[4.5rem] flex-1 flex-col items-center gap-1 px-2 py-2 transition-colors"
                    style={
                      selected
                        ? {
                            color: theme.cyan,
                            background: chrome.selectionBg,
                            borderRadius: chrome.radiusControl,
                            minHeight: chrome.touchTarget,
                            boxShadow: chrome.shadowCard,
                            transitionDuration: chrome.durationFast,
                          }
                        : {
                            color: theme.slate,
                            borderRadius: chrome.radiusControl,
                            minHeight: chrome.touchTarget,
                            transitionDuration: chrome.durationFast,
                          }
                    }
                    aria-current={selected ? "page" : undefined}
                    title={meta?.name || analysisKey}
                  >
                    <Icon
                      className="h-5 w-5 shrink-0"
                      strokeWidth={selected ? 2.25 : 1.75}
                    />
                    <span className="max-w-full truncate text-[10px] font-semibold leading-tight tracking-wide">
                      {label}
                    </span>
                  </button>
                );
              })}
            </div>
          </nav>
        ) : null}
        </div>
      </div>
    </ApplicationContextProvider>
  );
}
