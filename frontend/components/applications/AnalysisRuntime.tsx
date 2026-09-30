"use client";

import { Component, type ReactNode } from "react";

import DailyFantasyAnalyzer from "@/components/fantasy/dfs/DailyFantasyAnalyzer";
import PlayerAnalysisRuntime from "@/components/applications/PlayerAnalysisRuntime";
import SportsBettingAnalyzer from "@/components/betting/SportsBettingAnalyzer";
import { appTheme } from "@/components/applications/appTheme";
import {
  getRegistryAnalysis,
  type RegistryAnalysis,
} from "@/lib/analysisRegistry";
import type { DfsWorkspaceTab } from "@/components/fantasy/dfs/DfsSlateHeader";
import type { SnapshotTabId } from "@/components/fantasy/snapshot/PlayerTabs";

interface Props {
  analysisKey: string;
}

class AnalysisErrorBoundary extends Component<
  { children: ReactNode; name: string },
  { error: string | null }
> {
  state = { error: null as string | null };

  static getDerivedStateFromError(error: Error) {
    return { error: error.message || "Unable to load this analysis" };
  }

  render() {
    if (this.state.error) {
      return (
        <div
          className="rounded-xl p-8"
          style={{
            background: "rgba(255,85,112,0.08)",
            border: `1px solid rgba(255,85,112,0.35)`,
          }}
        >
          <h3
            className="text-lg font-semibold"
            style={{ color: appTheme.negative }}
          >
            Unable to load this analysis
          </h3>
          <p className="mt-2 max-w-xl text-sm" style={{ color: appTheme.silver }}>
            {this.props.name} is temporarily unavailable. Other analyses in this
            application are still available.
          </p>
          <button
            type="button"
            className="mt-4 rounded-lg px-3 py-1.5 text-sm font-medium"
            style={{
              background: appTheme.elevated,
              color: appTheme.white,
              border: `1px solid ${appTheme.border}`,
            }}
            onClick={() => this.setState({ error: null })}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function RuntimeBody({ analysis }: { analysis: RegistryAnalysis }) {
  if (analysis.runtime === "player_snapshot") {
    const view = (analysis.view || "snapshot") as SnapshotTabId;
    return <PlayerAnalysisRuntime view={view} />;
  }
  if (analysis.runtime === "dfs_analyzer") {
    return (
      <DailyFantasyAnalyzer
        initialTab={(analysis.view as DfsWorkspaceTab) || "analyzer"}
        hideTabBar
      />
    );
  }
  if (analysis.runtime === "sports_betting") {
    const view = analysis.view || "games";
    const tab =
      view === "games" ||
      view === "markets" ||
      view === "portfolio" ||
      view === "results" ||
      view === "overview"
        ? view
        : "games";
    return <SportsBettingAnalyzer initialTab={tab} hideTabBar />;
  }
  return (
    <div
      className="rounded-xl p-8 text-sm"
      style={{
        background: appTheme.midnight,
        border: `1px solid ${appTheme.border}`,
        color: appTheme.silver,
      }}
    >
      This analysis is not available in the runtime yet.
    </div>
  );
}

export default function AnalysisRuntime({ analysisKey }: Props) {
  const analysis = getRegistryAnalysis(analysisKey);

  if (!analysis) {
    return (
      <div
        className="rounded-xl p-8 text-sm"
        style={{ color: appTheme.silver }}
      >
        Unknown analysis: {analysisKey}
      </div>
    );
  }

  if (analysis.status !== "available") {
    return (
      <div
        className="rounded-xl p-8 text-sm"
        style={{ color: appTheme.silver }}
      >
        {analysis.name} is coming soon.
      </div>
    );
  }

  return (
    <AnalysisErrorBoundary name={analysis.name}>
      <div className="min-h-0 flex-1 space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: appTheme.cyan }}
            >
              {analysis.data_product_label}
            </p>
            <h2
              className="ip-heading mt-1 text-[28px] font-semibold tracking-tight lg:text-[32px]"
              style={{ color: appTheme.white }}
            >
              {analysis.name}
            </h2>
            <p
              className="mt-1 max-w-2xl text-sm"
              style={{ color: appTheme.silver }}
            >
              {analysis.description}
            </p>
          </div>
        </header>
        <div
          className="ip-analysis-panel overflow-hidden rounded-xl"
          style={{
            background: "#F5F7FA",
            color: "#0A1624",
            border: `1px solid ${appTheme.borderActive}`,
            boxShadow: `0 0 0 1px rgba(3,5,7,0.35), ${appTheme.glowSoft}`,
          }}
        >
          <div className="p-4 sm:p-5">
            <RuntimeBody analysis={analysis} />
          </div>
        </div>
      </div>
    </AnalysisErrorBoundary>
  );
}
