"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import PipelineDag from "@/components/refresh/PipelineDag";
import RefreshJobCard from "@/components/refresh/RefreshJobCard";
import {
  jobsForPipeline,
  readOddsLastRefresh,
  writeOddsLastRefresh,
  REFRESH_PIPELINES,
  type OddsLastRefreshMap,
  type RefreshJob,
  type RefreshPipelineId,
} from "@/lib/refreshJobs";
import {
  getNflverseCatalog,
  getNflverseIngestionStatus,
  getSportsdataverseCatalog,
  getSportsdataverseIngestionStatus,
  refreshNflverseData,
  refreshScoresandoddsData,
  refreshSportsdataverseData,
  type ScoresandoddsLeague,
} from "@/services/api";
import type {
  IngestionStatusResult,
  NflverseCatalog,
  NflverseRefreshResult,
} from "@/types/dataset";

export default function DataRefreshPage() {
  const [catalog, setCatalog] = useState<NflverseCatalog | null>(null);
  const [cfbCatalog, setCfbCatalog] =
    useState<NflverseCatalog | null>(null);
  const [nflStatus, setNflStatus] =
    useState<IngestionStatusResult | null>(null);
  const [cfbStatus, setCfbStatus] =
    useState<IngestionStatusResult | null>(null);
  const [oddsLastRefresh, setOddsLastRefresh] =
    useState<OddsLastRefreshMap>({});
  const [statusLoading, setStatusLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshLoading, setRefreshLoading] = useState<string | null>(
    null
  );
  const [refreshMessage, setRefreshMessage] = useState<string | null>(
    null
  );
  const [lastResult, setLastResult] =
    useState<NflverseRefreshResult | null>(null);
  const [activePipeline, setActivePipeline] =
    useState<RefreshPipelineId>("nfl_fantasy");

  const load = useCallback(async () => {
    setStatusLoading(true);
    setError(null);
    setOddsLastRefresh(readOddsLastRefresh());

    await Promise.allSettled([
      getNflverseCatalog().then(setCatalog).catch((reason: unknown) => {
        setError(
          reason instanceof Error
            ? reason.message
            : "Unable to load NFL catalog."
        );
      }),
      getSportsdataverseCatalog()
        .then(setCfbCatalog)
        .catch(() => null),
      getNflverseIngestionStatus()
        .then(setNflStatus)
        .catch(() => null),
      getSportsdataverseIngestionStatus()
        .then(setCfbStatus)
        .catch(() => null),
    ]);
    setStatusLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const pipelineMeta = useMemo(() => {
    return {
      nfl_fantasy: {
        currentSeason: catalog?.current_season,
        historical:
          catalog?.historical_seasons?.length
            ? `${catalog.historical_seasons[0]}–${
              catalog.historical_seasons[
                catalog.historical_seasons.length - 1
              ]
            }`
            : null,
      },
      college_football: {
        currentSeason: cfbCatalog?.current_season,
        historical:
          cfbCatalog?.historical_seasons?.length
            ? `${cfbCatalog.historical_seasons[0]}–${
              cfbCatalog.historical_seasons[
                cfbCatalog.historical_seasons.length - 1
              ]
            }`
            : null,
      },
      market_odds: {
        currentSeason: null as number | null | undefined,
        historical: null as string | null,
      },
    };
  }, [catalog, cfbCatalog]);

  function lastRefreshedForJob(job: RefreshJob): {
    at: string | null;
    status: string | null;
  } {
    if (job.kind === "scoresandodds" && job.league) {
      return {
        at: oddsLastRefresh[job.league] ?? null,
        status: oddsLastRefresh[job.league] ? "local" : null,
      };
    }
    const status =
      job.kind === "nflverse" ? nflStatus : cfbStatus;
    if (!job.mode || !status?.by_mode) {
      return { at: null, status: null };
    }
    const record = status.by_mode[job.mode];
    return {
      at: record?.finished_at ?? record?.updated_at ?? null,
      status: record?.status ?? null,
    };
  }

  async function handleRun(job: RefreshJob) {
    try {
      setRefreshLoading(job.id);
      setRefreshMessage(null);
      setError(null);

      if (job.kind === "nflverse" && job.mode) {
        const result = await refreshNflverseData(job.mode);
        setLastResult(result);
        setRefreshMessage(formatRunMessage(job.title, result));
        window.dispatchEvent(
          new CustomEvent("insightpilot:fantasy-data-refreshed", {
            detail: { mode: job.mode, result },
          })
        );
        const next = await getNflverseIngestionStatus();
        setNflStatus(next);
      } else if (job.kind === "sportsdataverse" && job.mode) {
        const result = await refreshSportsdataverseData(job.mode);
        setLastResult(result);
        setRefreshMessage(formatRunMessage(job.title, result));
        const next = await getSportsdataverseIngestionStatus();
        setCfbStatus(next);
      } else if (job.kind === "scoresandodds" && job.league) {
        const result = await refreshScoresandoddsData({
          league: job.league,
        });
        if (result.status === "accepted" || result.background) {
          setRefreshMessage(
            result.note
              || result.message
              || `${job.title} started in the background.`
          );
        } else {
          setRefreshMessage(
            `${job.title}: matched ${result.matched ?? 0} of `
              + `${result.fetched ?? 0} games`
              + (
                result.weeks?.length
                  ? ` (week ${result.weeks.join(", ")})`
                  : ""
              )
              + "."
          );
        }
        const iso = new Date().toISOString();
        setOddsLastRefresh(writeOddsLastRefresh(job.league, iso));
        window.dispatchEvent(
          new CustomEvent("insightpilot:fantasy-data-refreshed", {
            detail: {
              mode: "scoresandodds",
              league: job.league as ScoresandoddsLeague,
              result,
            },
          })
        );
      }
    } catch (runError) {
      const raw =
        runError instanceof Error
          ? runError.message
          : "Refresh failed.";
      setError(
        /failed to fetch/i.test(raw)
          ? `${raw} — long refreshes should start in the background `
            + "after you redeploy the API. For a first seed, use "
            + "Render Shell on insightpilot-api: "
            + "python -m app.scripts.seed_data"
          : raw
      );
    } finally {
      setRefreshLoading(null);
    }
  }

  const active = REFRESH_PIPELINES.find(
    (pipeline) => pipeline.id === activePipeline
  )!;
  const jobs = jobsForPipeline(activePipeline);
  const meta = pipelineMeta[activePipeline];

  return (
    <div className="mx-auto max-w-7xl">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Data Refresh
          </h1>
          <p className="mt-2 max-w-3xl text-gray-600">
            One refresh per job — no overlapping product shortcuts.
            Each job shows the tables it writes, the products that
            depend on them, and when it last finished.
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

      <section className="mt-8 grid gap-3 sm:grid-cols-3">
        <StatusCard
          label="NFL fantasy"
          value={
            statusLoading
              ? "Loading…"
              : formatRelative(
                nflStatus?.latest?.finished_at
                  ?? nflStatus?.latest?.updated_at
              )
          }
          hint={
            nflStatus?.latest?.mode
              ? `Last mode: ${nflStatus.latest.mode}`
              : "No ingest recorded yet"
          }
        />
        <StatusCard
          label="College football"
          value={
            statusLoading
              ? "Loading…"
              : formatRelative(
                cfbStatus?.latest?.finished_at
                  ?? cfbStatus?.latest?.updated_at
              )
          }
          hint={
            cfbStatus?.latest?.mode
              ? `Last mode: ${cfbStatus.latest.mode}`
              : "No ingest recorded yet"
          }
        />
        <StatusCard
          label="Pipelines"
          value={String(REFRESH_PIPELINES.length)}
          hint={`${jobsForPipeline("nfl_fantasy").length + jobsForPipeline("college_football").length + jobsForPipeline("market_odds").length} unique refresh jobs`}
        />
      </section>

      <nav
        className="mt-8 flex flex-wrap gap-2 border-b border-gray-200 pb-px"
        aria-label="Refresh pipelines"
      >
        {REFRESH_PIPELINES.map((pipeline) => {
          const selected = pipeline.id === activePipeline;
          return (
            <button
              key={pipeline.id}
              type="button"
              onClick={() => setActivePipeline(pipeline.id)}
              className={
                "rounded-t-lg border px-4 py-2 text-sm font-medium transition-colors "
                + (
                  selected
                    ? "border-gray-200 border-b-white bg-white text-gray-900"
                    : "border-transparent text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )
              }
            >
              {pipeline.title}
            </button>
          );
        })}
      </nav>

      <section className="rounded-b-xl rounded-tr-xl border border-gray-200 border-t-0 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {active.title}
            </h2>
            <p className="mt-1 max-w-3xl text-sm text-gray-600">
              {active.description}
            </p>
            <p className="mt-2 text-xs text-gray-500">
              Source: {active.source}
              {" · "}
              Schema: <span className="font-mono">{active.schema}</span>
              {meta.currentSeason != null
                ? ` · Current season ${meta.currentSeason}`
                : ""}
              {meta.historical
                ? ` · Historical ${meta.historical}`
                : ""}
            </p>
          </div>
        </div>

        <div className="mt-5 rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-3">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
            Data freshness DAG
          </p>
          <PipelineDag pipeline={active} />
        </div>

        <div className="mt-6 space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">
                Refresh jobs
              </h3>
              <p className="mt-0.5 text-sm text-gray-600">
                Each job below is unique — running one does not
                duplicate another product&apos;s refresh button.
              </p>
            </div>
          </div>

          {jobs.map((job) => {
            const last = lastRefreshedForJob(job);
            return (
              <RefreshJobCard
                key={job.id}
                job={job}
                pipeline={active}
                lastRefreshed={last.at}
                lastStatus={
                  last.status === "local"
                    ? "from this browser"
                    : last.status
                }
                loading={refreshLoading === job.id}
                disabled={refreshLoading != null}
                onRun={() => void handleRun(job)}
              />
            );
          })}
        </div>
      </section>

      <section className="mt-8 rounded-xl border border-dashed border-gray-300 bg-gray-50 p-5">
        <h2 className="text-lg font-semibold text-gray-900">
          User-created data products
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Uploaded CSV products refresh by remapping and re-analyzing
          a new file from the product workspace — they do not use the
          pipelines above.
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
        <section className="mt-8 rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-gray-900">
            Last run details
          </h2>
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
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
  );
}

function formatRunMessage(
  title: string,
  result: NflverseRefreshResult
): string {
  const accepted = result.status === "accepted" || result.background;
  return (
    result.message
    ?? result.validation?.message
    ?? (
      accepted
        ? `${title} started in the background. Check Data Quality in a few minutes.`
        : `${result.mode_label || title} completed.`
    )
  );
}

function StatusCard({
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
      <p className="mt-1 text-lg font-semibold text-gray-900">
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

function formatRelative(value?: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
