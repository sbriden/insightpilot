"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";

import DatasetPreviewTable from "@/components/datasets/DatasetPreviewTable";
import DfsSalaryUploadModal from "@/components/fantasy/dfs/DfsSalaryUploadModal";
import ProductWorkspace from "@/components/products/ProductWorkspace";

import {
  previewNflverseDataset,
  refreshNflverseData,
  getNflverseCatalog,
  getDatasetTypeDataProducts,
} from "@/services/api";

import {
  NflversePreviewResult,
} from "@/types/dataset";

import {
  getNativeProduct,
  NATIVE_DEFINITION_IDS,
} from "@/lib/prebuiltProducts";

import {
  FANTASY_FOOTBALL_ANALYSES,
} from "@/lib/fantasyFootballAnalyses";

import {
  PRODUCT_TYPE_LABELS,
  PRODUCT_TYPE_NATIVE,
  isNativeProduct,
} from "@/lib/productTypes";

import {
  useSavedProducts,
} from "@/hooks/useSavedProducts";

import {
  AnalysisDashboard,
  DataProduct,
  DataProductAnalysis,
} from "@/types/report";


type FantasyTableId =
  | "curated_fantasy_signals"
  | "curated_player_profiles"
  | "curated_player_game_logs"
  | "curated_player_usage"
  | "curated_opportunity_trends"
  | "curated_injury_reports"
  | "curated_depth_charts"
  | "curated_matchup_outlook"
  | "curated_team_offense"
  | "curated_defense_allowed"
  | "curated_market"
  | "curated_game_lines"
  | "curated_players"
  | "curated_schedule";

type CuratedDatasetGroup =
  | "signals"
  | "performance"
  | "opportunity"
  | "availability"
  | "context"
  | "reference";

interface CuratedDataset {
  id: FantasyTableId;
  title: string;
  description: string;
  group: CuratedDatasetGroup;
}

const CURATED_GROUPS: Array<{
  id: CuratedDatasetGroup;
  label: string;
  description: string;
}> = [
  {
    id: "signals",
    label: "Signals & Profiles",
    description:
      "Actionable fantasy intelligence with player and team context.",
  },
  {
    id: "performance",
    label: "Player Performance",
    description:
      "Game-by-game production with opponents — not raw IDs.",
  },
  {
    id: "opportunity",
    label: "Usage & Opportunity",
    description:
      "Combined usage, efficiency, and opportunity trend views.",
  },
  {
    id: "availability",
    label: "Availability & Depth",
    description:
      "Injury status and depth-chart movement.",
  },
  {
    id: "context",
    label: "Matchups & Market",
    description:
      "Opponent, team environment, and market context.",
  },
  {
    id: "reference",
    label: "Reference",
    description:
      "Roster and schedule for browsing.",
  },
];

/**
 * Denormalized exploration datasets.
 * Backend joins related tables and replaces IDs with names.
 */
const CURATED_DATASETS: CuratedDataset[] = [
  {
    id: "curated_fantasy_signals",
    title: "Fantasy Signals",
    description:
      "Breakout, buy/sell, start/sit, and regression signals with player names.",
    group: "signals",
  },
  {
    id: "curated_player_profiles",
    title: "Player Fantasy Profiles",
    description:
      "Weekly production, opportunity, efficiency, matchup, and value scores.",
    group: "signals",
  },
  {
    id: "curated_player_game_logs",
    title: "Player Game Logs",
    description:
      "Passing, rushing, and receiving production with team and opponent.",
    group: "performance",
  },
  {
    id: "curated_player_usage",
    title: "Usage & Efficiency",
    description:
      "Snaps, shares, and efficiency rates combined into one player-game view.",
    group: "opportunity",
  },
  {
    id: "curated_opportunity_trends",
    title: "Opportunity Trends",
    description:
      "Rolling usage shares with opportunity and efficiency scores.",
    group: "opportunity",
  },
  {
    id: "curated_injury_reports",
    title: "Injury Reports",
    description:
      "Practice and game status with player and team names.",
    group: "availability",
  },
  {
    id: "curated_depth_charts",
    title: "Depth Charts",
    description:
      "Weekly depth order and role with player and team names.",
    group: "availability",
  },
  {
    id: "curated_matchup_outlook",
    title: "Matchup Outlook",
    description:
      "Matchup scores plus pace, script, and team-total environment.",
    group: "context",
  },
  {
    id: "curated_team_offense",
    title: "Team Offense",
    description:
      "Team pace, pass rate, EPA, and red-zone efficiency by game.",
    group: "context",
  },
  {
    id: "curated_defense_allowed",
    title: "Defense Allowed",
    description:
      "What each defense allows, with defense and opponent names.",
    group: "context",
  },
  {
    id: "curated_market",
    title: "Market Snapshot",
    description:
      "Ranks, projections, ADP, and ownership with player names.",
    group: "context",
  },
  {
    id: "curated_game_lines",
    title: "Betting Lines",
    description:
      "Spreads, totals, and implied scores for each matchup.",
    group: "context",
  },
  {
    id: "curated_players",
    title: "Players",
    description:
      "Fantasy roster with position, team, and status.",
    group: "reference",
  },
  {
    id: "curated_schedule",
    title: "Schedule",
    description:
      "NFL schedule with home/away teams and scores.",
    group: "reference",
  },
];

const DEFAULT_DATASET_ID: FantasyTableId =
  "curated_fantasy_signals";


const DEFAULT_ANALYSES: DataProductAnalysis[] =
  FANTASY_FOOTBALL_ANALYSES.map(
    (analysis) => ({
      id: analysis.id,
      title: analysis.title,
      description: analysis.description,
    })
  );


type TableCache = Partial<
  Record<
    FantasyTableId,
    {
      rows: Record<string, unknown>[];
      rowCount: number;
      label: string;
    }
  >
>;


function buildShellProduct(
  native: ReturnType<typeof getNativeProduct>,
  analyses: DataProductAnalysis[]
): Pick<
  DataProduct,
  | "name"
  | "business_purpose"
  | "description"
  | "product_type"
  | "analyses"
  | "metrics"
  | "insights"
  | "promoted_insights"
  | "insight_initial_results"
  | "dashboards"
  | "change_summary"
  | "executive_summary"
  | "executive_brief"
> {
  return {
    name: native?.name ?? "Fantasy Football",
    description:
      native?.description
      ?? "InsightPilot-native fantasy football analyses over nflverse-backed data.",
    business_purpose:
      "Fantasy Football analyses over nflverse-backed data.",
    product_type: PRODUCT_TYPE_NATIVE,
    analyses,
    metrics: [],
    insights: [],
    promoted_insights: [],
    insight_initial_results: undefined,
    dashboards: analyses.map(
      placeholderDashboard
    ),
    change_summary: null,
    executive_summary: null,
    executive_brief: null,
  };
}


function placeholderDashboard(
  analysis: DataProductAnalysis
): AnalysisDashboard {
  return {
    id: analysis.id,
    title: analysis.title,
    summary: analysis.description ?? "",
    metrics: [],
    visualizations: [],
    insights: [],
    actions: [],
    datasets: {},
  };
}


function withFantasyAnalyses(
  product: Pick<
    DataProduct,
    | "name"
    | "business_purpose"
    | "description"
    | "product_type"
    | "analyses"
    | "metrics"
    | "insights"
    | "promoted_insights"
    | "insight_initial_results"
    | "dashboards"
    | "change_summary"
    | "executive_summary"
    | "executive_brief"
  > & Partial<DataProduct>,
  analyses: DataProductAnalysis[]
) {
  const existingDashboards =
    product.dashboards ?? [];

  const dashboards = analyses.map(
    (analysis) => {
      const match =
        existingDashboards.find(
          (dashboard) =>
            dashboard.id === analysis.id
        )
        ?? existingDashboards.find(
          (dashboard) =>
            dashboard.id === "fantasy_signals"
        );

      if (match) {
        return {
          ...match,
          id: analysis.id,
          title: analysis.title,
          summary:
            analysis.description
            || match.summary
            || "",
        };
      }

      return placeholderDashboard(analysis);
    }
  );

  return {
    ...product,
    analyses,
    dashboards,
  };
}


export default function FantasyFootballProductPage() {

  const native =
    getNativeProduct(
      "fantasy_football"
    );

  const {
    products: savedProducts,
    loaded: savedLoaded,
  } = useSavedProducts();

  const latestFantasyProduct =
    useMemo(() => {
      const versions = savedProducts
        .filter(
          (item) =>
            isNativeProduct(
              item,
              NATIVE_DEFINITION_IDS
            )
            && (
              item.definition_id === "fantasy_football"
              || String(item.id ?? "").includes(
                "fantasy_football"
              )
            )
        )
        .slice()
        .sort(
          (left, right) =>
            (right.version ?? 0)
            - (left.version ?? 0)
        );
      return versions[0] ?? null;
    }, [savedProducts]);

  const [
    catalogAnalyses,
    setCatalogAnalyses,
  ] =
    useState<DataProductAnalysis[]>(
      DEFAULT_ANALYSES
    );

  const [
    dataTabActive,
    setDataTabActive,
  ] =
    useState(false);

  const [
    activeTableId,
    setActiveTableId,
  ] =
    useState<FantasyTableId>(
      DEFAULT_DATASET_ID
    );

  const [
    cache,
    setCache,
  ] =
    useState<TableCache>(
      {}
    );

  const [
    loading,
    setLoading,
  ] =
    useState(true);

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null
    );

  const [
    currentSeason,
    setCurrentSeason,
  ] =
    useState<number | null>(
      null
    );

  const [
    historicalSeasons,
    setHistoricalSeasons,
  ] =
    useState<number[]>(
      []
    );

  const [
    refreshLoading,
    setRefreshLoading,
  ] =
    useState(false);

  const [
    refreshMessage,
    setRefreshMessage,
  ] =
    useState<string | null>(
      null
    );

  const [
    refreshStatus,
    setRefreshStatus,
  ] =
    useState<string | null>(
      null
    );

  const [
    salaryUploadOpen,
    setSalaryUploadOpen,
  ] =
    useState(false);


  const cachedTable =
    cache[activeTableId];

  const workspaceProduct =
    useMemo(() => {
      const base = latestFantasyProduct
        ? latestFantasyProduct
        : buildShellProduct(
            native,
            catalogAnalyses
          );

      return withFantasyAnalyses(
        base,
        catalogAnalyses.length > 0
          ? catalogAnalyses
          : DEFAULT_ANALYSES
      );
    }, [
      latestFantasyProduct,
      native,
      catalogAnalyses,
    ]);


  useEffect(() => {

    let cancelled = false;

    async function loadCatalogMeta() {
      try {
        const [
          catalog,
          typeProducts,
        ] = await Promise.all([
          getNflverseCatalog(),
          getDatasetTypeDataProducts(
            "fantasy_football"
          ).catch(() => null),
        ]);

        if (cancelled) {
          return;
        }

        setCurrentSeason(
          catalog.current_season
        );
        setHistoricalSeasons(
          catalog.historical_seasons
            ?? []
        );

        const products =
          Array.isArray(typeProducts)
            ? typeProducts
            : Array.isArray(
                typeProducts?.products
              )
              ? typeProducts.products
              : Array.isArray(
                  typeProducts?.data_products
                )
                ? typeProducts.data_products
                : [];

        const fantasyDef =
          products.find(
            (item: { id?: string }) =>
              item?.id === "fantasy_football"
          );

        if (
          fantasyDef
          && Array.isArray(fantasyDef.analyses)
          && fantasyDef.analyses.length > 0
        ) {
          setCatalogAnalyses(
            fantasyDef.analyses
              .map(
              (
                analysis:
                  | string
                  | DataProductAnalysis
              ) => {
                if (
                  typeof analysis === "string"
                ) {
                  const known =
                    FANTASY_FOOTBALL_ANALYSES.find(
                      (item) =>
                        item.id === analysis
                    );

                  return {
                    id: analysis,
                    title:
                      known?.title
                      ?? analysis,
                    description:
                      known?.description
                      ?? "",
                  };
                }

                const known =
                  FANTASY_FOOTBALL_ANALYSES.find(
                    (item) =>
                      item.id === analysis.id
                  );

                return {
                  ...analysis,
                  title:
                    analysis.title
                    || known?.title
                    || analysis.id,
                  description:
                    analysis.description
                    || known?.description
                    || "",
                };
              }
            )
              .filter(
                (analysis) =>
                  analysis.id !== "waiver_wire"
              )
          );
        }
      } catch {
        // Table load still works with backend defaults.
      }
    }

    void loadCatalogMeta();

    return () => {
      cancelled = true;
    };

  }, []);

  useEffect(() => {

    let cancelled = false;

    async function loadActiveTable() {

      if (!dataTabActive) {
        return;
      }

      if (cachedTable) {
        setLoading(false);
        setError(null);
        return;
      }

      try {

        setLoading(true);
        setError(null);

        const previewSeasons =
          currentSeason != null
            ? [currentSeason]
            : historicalSeasons.slice(-1);

        const preview:
          NflversePreviewResult =
            await previewNflverseDataset(
              activeTableId,
              previewSeasons
            );

        if (cancelled) {
          return;
        }

        setCache(
          current => ({
            ...current,
            [activeTableId]: {
              rows:
                preview.sample_rows ?? [],
              rowCount:
                preview.row_count,
              label:
                preview.label,
            },
          })
        );

      } catch (loadError) {

        if (cancelled) {
          return;
        }

        console.error(
          "Failed to load fantasy football table:",
          loadError
        );

        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load fantasy football table."
        );

      } finally {

        if (!cancelled) {
          setLoading(false);
        }

      }

    }

    void loadActiveTable();

    return () => {
      cancelled = true;
    };

  }, [
    activeTableId,
    cachedTable,
    dataTabActive,
    currentSeason,
    historicalSeasons,
  ]);


  async function handleRefresh(
    scope: "historical" | "current" | "reprocess"
  ) {
    try {
      setRefreshLoading(true);
      setError(null);
      setRefreshMessage(null);
      setRefreshStatus(null);
      const mode =
        scope === "current"
          ? "incremental"
          : scope;
      const result =
        await refreshNflverseData(mode);
      const message =
        result.message
        ?? result.validation?.message
        ?? "The data loaded successfully and passed validation.";
      setRefreshMessage(message);
      setRefreshStatus(
        result.status
        ?? result.validation?.status
        ?? "succeeded"
      );
      // Always drop curated-table cache so Data tabs reload.
      setCache({});
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent(
            "insightpilot:fantasy-data-refreshed",
            {
              detail: {
                mode,
                status: result.status,
                validation_blocked_derived:
                  result.validation_blocked_derived,
              },
            }
          )
        );
      }
    } catch (refreshError) {
      setRefreshMessage(null);
      setRefreshStatus(null);
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Unable to refresh fantasy football data."
      );
    } finally {
      setRefreshLoading(false);
    }
  }


  const activeTable =
    CURATED_DATASETS.find(
      (table) =>
        table.id === activeTableId
    );

  const activeData =
    cachedTable;

  const analysesCount =
    workspaceProduct.analyses?.length ?? 0;
  const metricsCount =
    (workspaceProduct.metrics ?? []).length;
  const insightsCount =
    (
      workspaceProduct.promoted_insights
      ?? workspaceProduct.insights
      ?? []
    ).length;


  return (

    <main className="mx-auto min-h-screen max-w-7xl p-6 sm:p-10">

      <Link
        href="/"
        className="text-sm text-gray-500 hover:underline"
      >
        ← Data Products
      </Link>


      <div className="mt-8">

        <div className="flex flex-wrap items-start justify-between gap-6">

          <div className="min-w-0">

            <div className="flex flex-wrap items-center gap-3">

              <h1 className="text-4xl font-bold">
                {workspaceProduct.name}
              </h1>

              <span className="rounded-md bg-teal-700 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-white">
                {native?.badge
                  ?? PRODUCT_TYPE_LABELS.native}
              </span>

              {latestFantasyProduct?.version != null && (
                <span className="rounded-full border px-3 py-1 text-xs text-gray-600">
                  v{latestFantasyProduct.version}
                </span>
              )}

            </div>

            <p className="mt-2 max-w-3xl text-gray-600">
              {workspaceProduct.business_purpose
                ?? workspaceProduct.description}
            </p>

            <div className="mt-6 flex flex-wrap gap-3">

              <span className="rounded-full border px-3 py-1 text-xs text-gray-600">
                {analysesCount}{" "}
                {analysesCount === 1
                  ? "analysis"
                  : "analyses"}
              </span>

              <span className="rounded-full border px-3 py-1 text-xs text-gray-600">
                {metricsCount}{" "}
                {metricsCount === 1
                  ? "KPI"
                  : "KPIs"}
              </span>

              <span className="rounded-full border px-3 py-1 text-xs text-gray-600">
                {insightsCount}{" "}
                {insightsCount === 1
                  ? "insight"
                  : "insights"}
              </span>

              {currentSeason != null && (
                <span className="rounded-full border px-3 py-1 text-xs text-gray-600">
                  current: {currentSeason}
                </span>
              )}

            </div>

          </div>

          <div className="flex flex-wrap gap-2">

            <button
              type="button"
              disabled={refreshLoading}
              onClick={() =>
                void handleRefresh("current")
              }
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 disabled:opacity-50"
            >
              {refreshLoading
                ? "Running…"
                : "Incremental update"}
            </button>

            <button
              type="button"
              disabled={refreshLoading}
              onClick={() =>
                void handleRefresh("historical")
              }
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 disabled:opacity-50"
            >
              Historical load
            </button>

            <button
              type="button"
              disabled={refreshLoading}
              onClick={() =>
                void handleRefresh("reprocess")
              }
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 disabled:opacity-50"
            >
              Reprocess derived
            </button>

            <button
              type="button"
              onClick={() =>
                setSalaryUploadOpen(true)
              }
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50"
            >
              Upload DFS salaries
            </button>

          </div>

        </div>

      </div>


      {refreshMessage && (
        <div
          className={[
            "mt-6 rounded-xl border px-4 py-3 text-sm",
            refreshStatus === "failed_validation"
              || refreshStatus === "failed"
              ? "border-red-200 bg-red-50 text-red-800"
              : refreshStatus === "succeeded_with_warnings"
                || refreshStatus === "passed_with_warnings"
                ? "border-amber-200 bg-amber-50 text-amber-900"
                : "border-teal-200 bg-teal-50 text-teal-900",
          ].join(" ")}
        >
          {refreshMessage}
        </div>
      )}


      {!savedLoaded ? (

        <div className="mt-8 rounded-xl border bg-white px-5 py-8 text-sm text-gray-500">
          Loading Fantasy Football product…
        </div>

      ) : (

        <div className="mt-8">

          <ProductWorkspace
            product={workspaceProduct}
            dashboards={
              workspaceProduct.dashboards ?? []
            }
            showViewAllLink={false}
            onTabChange={(tabId) => {
              if (tabId === "data") {
                setDataTabActive(true);
              }
            }}
            extraTabs={[
              {
                id: "data",
                label: "Data",
                count: CURATED_DATASETS.length,
                content: (
                  <FantasyDataBrowser
                    activeTableId={activeTableId}
                    setActiveTableId={setActiveTableId}
                    activeTable={activeTable}
                    historicalSeasons={historicalSeasons}
                    loading={loading}
                    error={error}
                    activeData={activeData}
                  />
                ),
              },
            ]}
          />

        </div>

      )}

      <DfsSalaryUploadModal
        open={salaryUploadOpen}
        defaultSeason={currentSeason}
        onClose={() => setSalaryUploadOpen(false)}
        onUploaded={(uploadResult) => {
          setRefreshMessage(
            `Saved ${uploadResult.persisted} ${uploadResult.site} ${uploadResult.contest_type} salaries for ${uploadResult.season} week ${uploadResult.week} (${uploadResult.matched} matched, ${uploadResult.unmatched} unmatched).`
          );
          setRefreshStatus("succeeded");
          setSalaryUploadOpen(false);
          if (typeof window !== "undefined") {
            window.dispatchEvent(
              new CustomEvent(
                "insightpilot:dfs-salaries-updated",
                {
                  detail: {
                    site: uploadResult.site,
                    contest_type: uploadResult.contest_type,
                    season: uploadResult.season,
                    week: uploadResult.week,
                  },
                }
              )
            );
          }
        }}
      />

    </main>

  );

}


function FantasyDataBrowser({
  activeTableId,
  setActiveTableId,
  activeTable,
  historicalSeasons,
  loading,
  error,
  activeData,
}: {
  activeTableId: FantasyTableId;
  setActiveTableId: (id: FantasyTableId) => void;
  activeTable: CuratedDataset | undefined;
  historicalSeasons: number[];
  loading: boolean;
  error: string | null;
  activeData:
    | {
        rows: Record<string, unknown>[];
        rowCount: number;
        label: string;
      }
    | undefined;
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-100 bg-gray-50 px-6 py-5">
        <h2 className="text-lg font-semibold text-gray-950">
          Curated datasets
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Denormalized exploration views — player and team names
          instead of IDs, with related sources combined where it
          helps.
        </p>
      </div>

      <div className="grid gap-0 lg:grid-cols-[minmax(16rem,20rem)_minmax(0,1fr)]">
        <aside className="max-h-[70vh] overflow-y-auto border-b border-gray-100 p-4 lg:border-b-0 lg:border-r">
          <div className="space-y-5">
            {CURATED_GROUPS.map((group) => {
              const datasets = CURATED_DATASETS.filter(
                (dataset) => dataset.group === group.id
              );
              if (datasets.length === 0) {
                return null;
              }
              return (
                <div key={group.id}>
                  <p className="px-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
                    {group.label}
                  </p>
                  <p className="mt-0.5 px-1 text-[11px] text-gray-400">
                    {group.description}
                  </p>
                  <ul className="mt-2 space-y-1">
                    {datasets.map((dataset) => {
                      const isActive =
                        dataset.id === activeTableId;
                      return (
                        <li key={dataset.id}>
                          <button
                            type="button"
                            onClick={() =>
                              setActiveTableId(dataset.id)
                            }
                            className={[
                              "w-full rounded-lg px-3 py-2 text-left transition",
                              isActive
                                ? "bg-teal-700 text-white"
                                : "text-gray-700 hover:bg-gray-50",
                            ].join(" ")}
                          >
                            <span className="block text-sm font-medium">
                              {dataset.title}
                            </span>
                            <span
                              className={[
                                "mt-0.5 block text-[11px] leading-snug",
                                isActive
                                  ? "text-teal-100"
                                  : "text-gray-500",
                              ].join(" ")}
                            >
                              {dataset.description}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              );
            })}
          </div>
        </aside>

        <div className="p-4 sm:p-5">
          {activeTable && (
            <div className="mb-4">
              <h3 className="text-base font-semibold text-gray-950">
                {activeTable.title}
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                {activeTable.description}
                {historicalSeasons.length > 0 && (
                  <>
                    {" "}
                    · seasons {historicalSeasons[0]}–
                    {
                      historicalSeasons[
                        historicalSeasons.length - 1
                      ]
                    }
                  </>
                )}
              </p>
            </div>
          )}

          {loading ? (
            <div className="rounded-xl border bg-white px-5 py-8 text-sm text-gray-500">
              Loading {activeTable?.title ?? "dataset"}…
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-6 text-sm text-red-700">
              {error}
            </div>
          ) : (
            <DatasetPreviewTable
              rows={activeData?.rows ?? []}
              totalRowCount={activeData?.rowCount}
              title={activeTable?.title ?? "Dataset"}
              maxHeightClassName="max-h-[70vh]"
              emptyMessage={`No rows available for ${
                activeTable?.title ?? "this dataset"
              }.`}
            />
          )}
        </div>
      </div>
    </section>
  );
}
