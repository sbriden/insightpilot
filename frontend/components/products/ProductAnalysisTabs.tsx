"use client";

import {
  useMemo,
  useState,
} from "react";

import AnalysisDashboard from "@/components/AnalysisDashboard";
import DailyFantasyAnalyzer from "@/components/fantasy/dfs/DailyFantasyAnalyzer";
import SportsBettingAnalyzer from "@/components/betting/SportsBettingAnalyzer";
import PlayerSnapshot, {
  snapshotsFromDashboard,
} from "@/components/fantasy/PlayerSnapshot";

import {
  AnalysisDashboard as AnalysisDashboardType,
  DataProductAnalysis,
} from "@/types/report";


interface AnalysisItem {
  id: string;
  title: string;
  dashboard?: AnalysisDashboardType;
  available: boolean;
}


interface Props {
  analyses?: Array<
    string | DataProductAnalysis
  >;
  dashboards?: AnalysisDashboardType[];
}


export default function ProductAnalysisTabs({
  analyses = [],
  dashboards = [],
}: Props) {

  const items =
    useMemo(
      () =>
        buildAnalysisItems(
          analyses,
          dashboards
        ),
      [analyses, dashboards]
    );

  const [
    activeId,
    setActiveId,
  ] = useState(
    () =>
      items.find(
        item => item.available
      )?.id ??
      items[0]?.id ??
      ""
  );


  const activeItem =
    items.find(
      item =>
        item.id === activeId
    );


  if (
    items.length === 0
  ) {

    return (
      <div className="rounded-xl border bg-white p-6 text-sm text-gray-500">
        No analysis is currently available for this product.
      </div>
    );

  }


  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">

      <div className="border-b border-gray-100 bg-gray-50 px-4 py-4 sm:px-6">

        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-500">
          Analyses
        </p>

        <p className="mt-1 text-sm text-gray-600">
          Select an analysis to explore its candidate findings,
          metrics, charts, and insights.
        </p>


        <div
          className="mt-4 flex gap-2 overflow-x-auto pb-1"
          role="tablist"
          aria-label="Product analyses"
        >

          {items.map(
            (item) => {

              const selected =
                item.id === activeId;

              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  disabled={!item.available}
                  onClick={() =>
                    setActiveId(item.id)
                  }
                  className={`shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                    selected
                      ? "bg-gray-900 text-white"
                      : item.available
                        ? "bg-white text-gray-700 ring-1 ring-gray-200 hover:bg-gray-100"
                        : "cursor-not-allowed bg-gray-100 text-gray-400"
                  }`}
                >
                  {item.title}

                  {!item.available && (
                    <span className="ml-2 text-xs opacity-80">
                      unavailable
                    </span>
                  )}

                </button>
              );

            }
          )}

        </div>

      </div>


      <div
        className="p-4 sm:p-6 space-y-8"
        role="tabpanel"
      >

        {activeItem?.id === "player_overview" && (
          <PlayerSnapshot
            snapshots={
              activeItem.dashboard
                ? snapshotsFromDashboard(
                    activeItem.dashboard
                  )
                : []
            }
          />
        )}

        {activeItem?.id === "daily_fantasy" && (
          <DailyFantasyAnalyzer />
        )}

        {activeItem?.id === "sports_betting" && (
          <SportsBettingAnalyzer />
        )}

        {activeItem?.dashboard
          && activeItem.id !== "player_overview"
          && activeItem.id !== "daily_fantasy"
          && activeItem.id !== "sports_betting" ? (
          <AnalysisDashboard
            dashboard={
              activeItem.dashboard as any
            }
            embedded
          />
        ) : null}

        {!activeItem?.dashboard
          && activeItem?.id !== "player_overview"
          && activeItem?.id !== "daily_fantasy"
          && activeItem?.id !== "sports_betting" && (
          <div className="rounded-xl border border-dashed p-6 text-sm text-gray-500">
            {activeItem
              ? `${activeItem.title} is not available for this dataset or field mapping.`
              : "Select an analysis to view details."}
          </div>
        )}

      </div>

    </div>

  );

}


function buildAnalysisItems(
  analyses: Array<
    string | DataProductAnalysis
  >,
  dashboards: AnalysisDashboardType[]
): AnalysisItem[] {

  const dashboardById =
    new Map(
      dashboards.map(
        dashboard => [
          dashboard.id,
          dashboard,
        ]
      )
    );

  if (
    analyses.length > 0
  ) {

    return analyses.map(
      (analysis) => {

        const id =
          typeof analysis === "string"
            ? analysis
            : analysis.id;

        const title =
          typeof analysis === "string"
            ? formatAnalysisTitle(
                analysis
              )
            : analysis.title ??
              formatAnalysisTitle(
                analysis.id
              );

        const dashboard =
          dashboardById.get(id);

        return {
          id,
          title,
          dashboard,
          available: !!dashboard,
        };

      }
    );

  }

  return dashboards.map(
    dashboard => ({
      id: dashboard.id,
      title: dashboard.title,
      dashboard,
      available: true,
    })
  );

}


function formatAnalysisTitle(
  value: string
): string {

  return value
    .replace(/_/g, " ")
    .replace(
      /\b\w/g,
      char =>
        char.toUpperCase()
    );

}
