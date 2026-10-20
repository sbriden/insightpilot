"use client";

import { Component, type ReactNode } from "react";

import { AnalysisFormatProvider } from "@/components/analysis/AnalysisFormatContext";
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
  if (analysis.runtime === "player_overview") {
    const view = analysis.view || "table";
    const overview =
      view === "scatter" ||
      view === "compare" ||
      view === "teams" ||
      view === "table"
        ? view
        : "table";
    return <PlayerAnalysisRuntime view={overview} />;
  }
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
      <div
        className="ip-analysis-panel overflow-hidden rounded-xl"
        style={{
          background: appTheme.midnight,
          color: appTheme.white,
          border: `1px solid ${appTheme.border}`,
          boxShadow: appTheme.glowSoft,
        }}
      >
        <div className="p-4 sm:p-5">
          <AnalysisFormatProvider format="application">
            <RuntimeBody analysis={analysis} />
          </AnalysisFormatProvider>
        </div>
      </div>
    </AnalysisErrorBoundary>
  );
}
