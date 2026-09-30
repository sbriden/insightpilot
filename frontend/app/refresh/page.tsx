"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { NATIVE_PRODUCTS } from "@/lib/prebuiltProducts";
import {
  getNflverseCatalog,
  getNflverseDataQuality,
  refreshNflverseData,
} from "@/services/api";
import type {
  NflverseCatalog,
  NflverseDataQualityResult,
  NflverseIngestMode,
  NflverseRefreshResult,
} from "@/types/dataset";

const LAYER_DETAILS: Record<
  string,
  { label: string; description: string }
> = {
  dims: {
    label: "Dimensions",
    description:
      "Identity tables for teams, players, and games. Establishes "
      + "canonical keys used by every downstream fact and analysis.",
  },
  facts: {
    label: "Facts",
    description:
      "Game-level production, usage, efficiency, injuries, depth "
      + "charts, and market lines ingested from nflverse sources.",
  },
  analytics: {
    label: "Analytics",
    description:
      "Derived usage trends, opportunity, efficiency, matchup, and "
      + "environment scores built from stored facts.",
  },
  intelligence: {
    label: "Intelligence",
    description:
      "Fantasy profiles and InsightPilot signals that power Player "
      + "Overview, DFS projections, and betting edges.",
  },
  domain: {
    label: "Domain",
    description:
      "Domain-specific enrichment such as player fundamentals used "
      + "by product analyses.",
  },
};

const PRODUCT_REFRESH: Array<{
  productId: string;
  modes: NflverseIngestMode[];
  summary: string;
  consumes: string[];
  outputs: string[];
}> = [
  {
    productId: "fantasy_football",
    modes: ["incremental", "historical", "reprocess"],
    summary:
      "Primary owner of the nflverse fantasy pipeline. Refresh "
      + "updates dims/facts and rebuilds analytics used by Player "
      + "Overview, DFS Optimizer, and Portfolio Builder.",
    consumes: [
      "nflverse schedules & rosters",
      "player game / usage / efficiency",
      "injuries & depth charts",
    ],
    outputs: [
      "Player Snapshot / Overview",
      "DFS slate projections",
      "Fantasy signals & profiles",
    ],
  },
  {
    productId: "sports_betting",
    modes: ["incremental", "reprocess"],
    summary:
      "Shares the same nflverse foundation (games/game markets and "
      + "projection inputs). Incremental refresh pulls latest lines "
      + "and scores; reprocess rebuilds projection calibration "
      + "inputs without re-fetching raw sources.",
    consumes: [
      "fact_game_market / fact_market",
      "team & game dims",
      "projection / PPG context",
    ],
    outputs: [
      "Market analysis slate",
      "Model vs market edges",
      "Results & calibration",
    ],
  },
];

const FALLBACK_MODES: Array<{
  id: NflverseIngestMode;
  label: string;
  description: string;
  layers: string[];
  season_scope: string;
}> = [
  {
    id: "incremental",
    label: "Incremental update",
    description:
      "Retrieve and process newly available current-season data "
      + "(weekly). Upserts the live season without rebuilding "
      + "stored historical seasons.",
    layers: ["dims", "facts", "analytics", "intelligence", "domain"],
    season_scope: "current",
  },
  {
    id: "historical",
    label: "Historical load",
    description:
      "One-time initial ingestion across several seasons. Seeds "
      + "dims, facts, analytics, and intelligence for trends, "
      + "matchups, and backtesting.",
    layers: ["dims", "facts", "analytics", "intelligence", "domain"],
    season_scope: "historical",
  },
  {
    id: "reprocess",
    label: "Reprocess derived",
    description:
      "Rebuild analytics and intelligence from facts already in "
      + "Postgres when transformation logic changes. Does not "
      + "re-fetch raw nflverse source tables.",
    layers: ["analytics", "intelligence"],
    season_scope: "historical",
  },
];

export default function DataRefreshPage() {
  const [catalog, setCatalog] = useState<NflverseCatalog | null>(
    null
  );
  const [quality, setQuality] =
    useState<NflverseDataQualityResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshLoading, setRefreshLoading] = useState<
    NflverseIngestMode | null
  >(null);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(
    null
  );
  const [lastResult, setLastResult] =
    useState<NflverseRefreshResult | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [catalogResult, qualityResult] = await Promise.all([
        getNflverseCatalog(),
        getNflverseDataQuality(true),
      ]);
      setCatalog(catalogResult);
      setQuality(qualityResult);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load data refresh catalog."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const modes = useMemo(() => {
    const fromCatalog = catalog?.ingest_modes;
    if (fromCatalog && fromCatalog.length > 0) {
      return fromCatalog.map((mode) => ({
        id: mode.id as NflverseIngestMode,
        label: mode.label,
        description: mode.description,
        layers: mode.layers,
        season_scope: mode.season_scope,
      }));
    }
    return FALLBACK_MODES;
  }, [catalog]);

  const layers = catalog?.ingest_layers?.length
    ? catalog.ingest_layers
    : Object.keys(LAYER_DETAILS);

  const pipelineByLayer = useMemo(() => {
    const datasets = catalog?.datasets ?? [];
    const grouped: Record<string, string[]> = {};
    for (const layer of layers) {
      grouped[layer] = [];
    }
    // Catalog datasets may not expose layer; fall back to known ids
    // from mode layer membership is enough for the ops view.
    for (const dataset of datasets) {
      const id = dataset.id;
      if (!id) continue;
      // Heuristic grouping when layer metadata is absent.
      if (
        id.startsWith("dim_")
        || id === "dim_team"
        || id === "dim_player"
        || id === "dim_game"
      ) {
        grouped.dims = grouped.dims || [];
        if (!grouped.dims.includes(id)) grouped.dims.push(id);
      } else if (id.startsWith("fact_")) {
        grouped.facts = grouped.facts || [];
        if (!grouped.facts.includes(id)) grouped.facts.push(id);
      } else if (
        id.startsWith("player_")
        && !id.includes("fantasy")
        && !id.includes("fundamental")
      ) {
        grouped.analytics = grouped.analytics || [];
        if (!grouped.analytics.includes(id)) {
          grouped.analytics.push(id);
        }
      } else if (
        id.includes("fantasy")
        || id.includes("signal")
      ) {
        grouped.intelligence = grouped.intelligence || [];
        if (!grouped.intelligence.includes(id)) {
          grouped.intelligence.push(id);
        }
      } else if (id.includes("fundamental")) {
        grouped.domain = grouped.domain || [];
        if (!grouped.domain.includes(id)) grouped.domain.push(id);
      }
    }
    return grouped;
  }, [catalog, layers]);

  async function handleRefresh(mode: NflverseIngestMode) {
    try {
      setRefreshLoading(mode);
      setRefreshMessage(null);
      setError(null);
      const result = await refreshNflverseData(mode);
      setLastResult(result);
      const message =
        result.message
        ?? result.validation?.message
        ?? `${result.mode_label || mode} completed.`;
      setRefreshMessage(message);
      window.dispatchEvent(
        new CustomEvent("insightpilot:fantasy-data-refreshed", {
          detail: { mode, result },
        })
      );
      const qualityResult = await getNflverseDataQuality(true);
      setQuality(qualityResult);
    } catch (runError) {
      setError(
        runError instanceof Error
          ? runError.message
          : "Refresh failed."
      );
    } finally {
      setRefreshLoading(null);
    }
  }

  const latest = quality?.latest_ingest;

  return (
    <div className="mx-auto max-w-7xl">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Data Refresh
          </h1>
          <p className="mt-2 max-w-3xl text-gray-600">
            Run InsightPilot source refresh operations for native
            data products, review what each mode rebuilds, and
            inspect the latest ingestion status.
          </p>
        </div>
        <Link
          href="/quality"
          className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50"
        >
          Open Data Quality
        </Link>
      </header>

      {error ? (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {refreshMessage ? (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {refreshMessage}
        </div>
      ) : null}

      {loading ? (
        <p className="mt-8 text-sm text-gray-500">
          Loading refresh catalog…
        </p>
      ) : (
        <div className="mt-8 space-y-8">
          <StatusPanel
            quality={quality}
            catalog={catalog}
            latest={latest}
          />

          <section>
            <h2 className="text-lg font-semibold text-gray-900">
              Data products
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Each product below consumes the shared nflverse
              lifecycle. Choose a refresh mode to update the data
              powering its analyses.
            </p>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              {PRODUCT_REFRESH.map((config) => {
                const product = NATIVE_PRODUCTS.find(
                  (item) => item.id === config.productId
                );
                if (!product) return null;
                return (
                  <ProductRefreshCard
                    key={product.id}
                    name={product.name}
                    href={product.href}
                    badge={product.badge}
                    sourceLabel={product.sourceLabel}
                    summary={config.summary}
                    consumes={config.consumes}
                    outputs={config.outputs}
                    modes={modes.filter((mode) =>
                      config.modes.includes(mode.id)
                    )}
                    refreshLoading={refreshLoading}
                    onRefresh={handleRefresh}
                  />
                );
              })}
            </div>
          </section>

          <section className="rounded-xl border border-gray-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-gray-900">
              Refresh operations
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Full detail for every ingest mode exposed by the
              nflverse lifecycle engine.
            </p>
            <div className="mt-4 space-y-4">
              {modes.map((mode) => (
                <article
                  key={mode.id}
                  className="rounded-lg border border-gray-100 bg-gray-50 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900">
                        {mode.label}
                      </h3>
                      <p className="mt-1 text-sm text-gray-600">
                        {mode.description}
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={refreshLoading != null}
                      onClick={() => void handleRefresh(mode.id)}
                      className="rounded-lg bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
                    >
                      {refreshLoading === mode.id
                        ? "Running…"
                        : `Run ${mode.label.toLowerCase()}`}
                    </button>
                  </div>
                  <dl className="mt-3 grid gap-3 sm:grid-cols-3 text-sm">
                    <div>
                      <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Season scope
                      </dt>
                      <dd className="mt-0.5 capitalize text-gray-900">
                        {mode.season_scope}
                        {mode.season_scope === "current"
                          && catalog?.current_season
                          ? ` (${catalog.current_season})`
                          : ""}
                        {mode.season_scope === "historical"
                          && catalog?.historical_seasons?.length
                          ? ` (${catalog.historical_seasons[0]}–${catalog.historical_seasons[catalog.historical_seasons.length - 1]})`
                          : ""}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Pipeline layers
                      </dt>
                      <dd className="mt-0.5 text-gray-900">
                        {mode.layers
                          .map(
                            (layer) =>
                              LAYER_DETAILS[layer]?.label ?? layer
                          )
                          .join(" → ")}
                      </dd>
                    </div>
                  </dl>
                  <ul className="mt-3 space-y-1.5 text-sm text-gray-600">
                    {mode.layers.map((layer) => (
                      <li key={`${mode.id}-${layer}`}>
                        <span className="font-medium text-gray-800">
                          {LAYER_DETAILS[layer]?.label ?? layer}:
                        </span>{" "}
                        {LAYER_DETAILS[layer]?.description
                          ?? "Pipeline stage."}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-gray-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-gray-900">
              Pipeline layers
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Ordered stages executed during refresh. Historical and
              incremental modes run the full stack; reprocess starts
              at analytics.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {layers.map((layer, index) => {
                const meta = LAYER_DETAILS[layer];
                const datasets = pipelineByLayer[layer] ?? [];
                return (
                  <div
                    key={layer}
                    className="rounded-lg border border-gray-100 p-4"
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
                      Step {index + 1}
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-gray-900">
                      {meta?.label ?? layer}
                    </h3>
                    <p className="mt-1 text-sm text-gray-600">
                      {meta?.description ?? "Pipeline stage."}
                    </p>
                    {datasets.length > 0 ? (
                      <p className="mt-2 text-xs text-gray-500">
                        {datasets.slice(0, 8).join(", ")}
                        {datasets.length > 8
                          ? ` +${datasets.length - 8} more`
                          : ""}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-5">
            <h2 className="text-lg font-semibold text-gray-900">
              User-created data products
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Uploaded CSV products refresh by remapping and
              re-analyzing a new file from the product workspace —
              they do not use the nflverse lifecycle above.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                href="/"
                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50"
              >
                Browse data products
              </Link>
              <Link
                href="/create"
                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50"
              >
                Create product
              </Link>
            </div>
          </section>

          {lastResult ? (
            <section className="rounded-xl border border-gray-200 bg-white p-5">
              <h2 className="text-lg font-semibold text-gray-900">
                Last run details
              </h2>
              <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
                <Detail
                  label="Mode"
                  value={lastResult.mode_label || lastResult.mode || "—"}
                />
                <Detail
                  label="Seasons"
                  value={
                    lastResult.seasons?.length
                      ? lastResult.seasons.join(", ")
                      : "—"
                  }
                />
                <Detail
                  label="Datasets"
                  value={String(lastResult.datasets_refreshed ?? 0)}
                />
                <Detail
                  label="Rows"
                  value={
                    lastResult.row_count_total != null
                      ? lastResult.row_count_total.toLocaleString()
                      : "—"
                  }
                />
              </dl>
              {lastResult.validation ? (
                <p className="mt-3 text-sm text-gray-600">
                  Validation: {lastResult.validation.status} —{" "}
                  {lastResult.validation.message}
                </p>
              ) : null}
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}

function StatusPanel({
  quality,
  catalog,
  latest,
}: {
  quality: NflverseDataQualityResult | null;
  catalog: NflverseCatalog | null;
  latest?: NflverseDataQualityResult["latest_ingest"];
}) {
  return (
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Source"
        value="nflverse"
        hint={
          catalog?.current_season
            ? `Current season ${catalog.current_season}`
            : undefined
        }
      />
      <StatCard
        label="Quality status"
        value={quality?.status ?? "—"}
        hint={quality?.message}
      />
      <StatCard
        label="Last ingest mode"
        value={latest?.mode ?? "—"}
        hint={
          latest?.finished_at
            ? `Finished ${formatTimestamp(latest.finished_at)}`
            : latest?.updated_at
              ? `Updated ${formatTimestamp(latest.updated_at)}`
              : "No ingestion state yet"
        }
      />
      <StatCard
        label="Last ingest rows"
        value={
          latest?.row_count_total != null
            ? latest.row_count_total.toLocaleString()
            : "—"
        }
        hint={
          latest?.seasons?.length
            ? `Seasons ${latest.seasons.join(", ")}`
            : undefined
        }
      />
    </section>
  );
}

function ProductRefreshCard({
  name,
  href,
  badge,
  sourceLabel,
  summary,
  consumes,
  outputs,
  modes,
  refreshLoading,
  onRefresh,
}: {
  name: string;
  href: string;
  badge: string;
  sourceLabel: string;
  summary: string;
  consumes: string[];
  outputs: string[];
  modes: Array<{
    id: NflverseIngestMode;
    label: string;
    description: string;
  }>;
  refreshLoading: NflverseIngestMode | null;
  onRefresh: (mode: NflverseIngestMode) => void;
}) {
  return (
    <article className="flex flex-col rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
            {badge} · {sourceLabel}
          </p>
          <h3 className="mt-1 text-base font-semibold text-gray-900">
            {name}
          </h3>
        </div>
        <Link
          href={href}
          className="text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          Open product
        </Link>
      </div>
      <p className="mt-2 text-sm text-gray-600">{summary}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 text-sm">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Consumes
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-gray-700">
            {consumes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Powers
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-gray-700">
            {outputs.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {modes.map((mode) => (
          <button
            key={mode.id}
            type="button"
            title={mode.description}
            disabled={refreshLoading != null}
            onClick={() => onRefresh(mode.id)}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 disabled:opacity-50"
          >
            {refreshLoading === mode.id
              ? "Running…"
              : mode.label}
          </button>
        ))}
      </div>
    </article>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold capitalize text-gray-900">
        {value}
      </p>
      {hint ? (
        <p className="mt-1 line-clamp-2 text-xs text-gray-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        {label}
      </dt>
      <dd className="mt-0.5 text-gray-900">{value}</dd>
    </div>
  );
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}
