"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, MoreHorizontal, RefreshCw } from "lucide-react";

import AnalysisRuntime from "@/components/applications/AnalysisRuntime";
import { ApplicationContextProvider } from "@/components/applications/ApplicationContext";
import ApplicationLogo from "@/components/applications/ApplicationLogo";
import { appTheme } from "@/components/applications/appTheme";
import {
  getRegistryAnalysis,
  sourceProductLabels,
} from "@/lib/analysisRegistry";
import type { AnalyticalApplication } from "@/services/api";

interface Props {
  application: AnalyticalApplication;
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
  const groups: NavGroup[] = [];
  const indexByLabel = new Map<string, number>();

  for (const row of ordered) {
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

export default function ApplicationWorkspace({ application }: Props) {
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

  const products = sourceProductLabels(flatKeys);

  return (
    <ApplicationContextProvider>
      <div
        className="flex min-h-screen flex-col"
        style={{ background: appTheme.obsidian }}
      >
        <header
          className="flex h-14 shrink-0 items-center justify-between px-4 lg:h-16 lg:px-5"
          style={{ background: appTheme.midnight }}
        >
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href="/applications"
              className="shrink-0 text-sm transition-colors"
              style={{ color: appTheme.slate }}
            >
              ← Portal
            </Link>
            <span
              className="hidden h-4 w-px sm:block"
              style={{ background: appTheme.border }}
            />
            <ApplicationLogo
              src={application.icon}
              name={application.name}
              size={28}
            />
            <div className="min-w-0">
              <h1
                className="ip-heading truncate text-[20px] font-semibold tracking-tight lg:text-[22px]"
                style={{ color: appTheme.white }}
              >
                {application.name}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-lg px-3 py-1.5 text-sm lg:hidden"
              style={{
                color: appTheme.silver,
                border: `1px solid ${appTheme.border}`,
              }}
              onClick={() => setNavOpen((v) => !v)}
            >
              Analyses
            </button>
            <button
              type="button"
              title="Refresh analysis"
              onClick={() => setRefreshKey((k) => k + 1)}
              className="rounded-lg p-2 transition-colors"
              style={{ color: appTheme.silver }}
            >
              <RefreshCw className="h-4 w-4" />
            </button>
            <Link
              href={`/applications/${application.id}/edit`}
              className="rounded-lg px-3 py-1.5 text-sm font-medium transition-colors"
              style={{
                color: appTheme.white,
                background: appTheme.deepBlue,
                border: `1px solid ${appTheme.border}`,
              }}
            >
              Settings
            </Link>
            <button
              type="button"
              className="rounded-lg p-2"
              style={{ color: appTheme.slate }}
              aria-label="More"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </div>
        </header>
        <div className="ip-app-beam shrink-0" />

        <div className="flex min-h-0 flex-1">
          <aside
            className={[
              "w-[230px] shrink-0 xl:w-[250px]",
              navOpen ? "block" : "hidden lg:block",
            ].join(" ")}
            style={{
              background: appTheme.midnight,
              borderRight: `1px solid ${appTheme.border}`,
            }}
          >
            <div
              className="px-4 py-4"
              style={{ borderBottom: `1px solid ${appTheme.border}` }}
            >
              <p
                className="text-[11px] font-semibold uppercase tracking-[0.16em]"
                style={{ color: appTheme.slate }}
              >
                Application
              </p>
              <p
                className="mt-1 text-sm font-medium"
                style={{ color: appTheme.white }}
              >
                {flatKeys.length} analyses
              </p>
              {products ? (
                <p className="mt-0.5 text-xs" style={{ color: appTheme.slate }}>
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
                      className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                      style={{ color: appTheme.slate }}
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
                              className="relative block w-full rounded-lg px-3 py-2.5 text-left text-sm transition-all duration-200"
                              style={
                                selected
                                  ? {
                                      background: "rgba(0,140,255,0.12)",
                                      color: appTheme.white,
                                      boxShadow: appTheme.glowSoft,
                                    }
                                  : { color: appTheme.silver }
                              }
                            >
                              {selected ? (
                                <span
                                  className="absolute inset-y-1.5 left-0 w-[3px] rounded-r"
                                  style={{
                                    background: appTheme.cyan,
                                    boxShadow: appTheme.glowActive,
                                  }}
                                />
                              ) : null}
                              <span className="flex items-center gap-2 pl-1">
                                <span
                                  style={{
                                    color: selected
                                      ? appTheme.cyan
                                      : appTheme.slate,
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

          <main
            className="min-w-0 flex-1 overflow-auto p-4 lg:p-5 xl:p-6"
            style={{ background: appTheme.obsidian }}
          >
            {activeKey ? (
              <AnalysisRuntime
                key={`${activeKey}:${refreshKey}`}
                analysisKey={activeKey}
              />
            ) : (
              <div
                className="ip-app-panel rounded-xl px-8 py-16 text-center"
              >
                <p
                  className="text-[11px] font-semibold uppercase tracking-[0.2em]"
                  style={{ color: appTheme.cyan }}
                >
                  InsightPilot
                </p>
                <h2
                  className="ip-heading mt-3 text-2xl font-semibold"
                  style={{ color: appTheme.white }}
                >
                  Your analytical workspace is empty
                </h2>
                <p
                  className="mx-auto mt-2 max-w-md text-sm"
                  style={{ color: appTheme.silver }}
                >
                  Add analyses from your data products to begin building your
                  application.
                </p>
                <Link
                  href={`/applications/${application.id}/edit`}
                  className="ip-app-cta mt-6 inline-flex rounded-lg px-4 py-2.5 text-sm"
                >
                  + Add Analysis
                </Link>
              </div>
            )}
          </main>
        </div>
      </div>
    </ApplicationContextProvider>
  );
}
