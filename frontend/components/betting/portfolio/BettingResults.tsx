"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatAmerican } from "@/components/betting/formatMarketValues";
import {
  loadBettingPortfolio,
  saveBettingPortfolio,
} from "@/components/betting/portfolio/portfolioStorage";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import {
  analyzeBettingPortfolio,
  BettingCalibrationFeedback,
  BettingModelResultsSummary,
  BettingPerformanceTrendPoint,
  BettingPerformanceTrendSummary,
  BettingPortfolioAnalyzeResult,
  BettingResultsPayload,
  BettingSlate,
  getBettingResults,
} from "@/services/api";

interface Props {
  slate: BettingSlate;
  season: number | null;
  week: number | null;
}

type ResultsView = "model" | "portfolio";

const SETTLED_TABLE_MAX_HEIGHT = 360;

export default function BettingResults({
  slate,
  season,
  week,
}: Props) {
  const [view, setView] = useState<ResultsView>("model");
  const [modelPayload, setModelPayload] =
    useState<BettingResultsPayload | null>(null);
  const [portfolioAnalysis, setPortfolioAnalysis] =
    useState<BettingPortfolioAnalyzeResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [model, portfolioStored] = await Promise.all([
          getBettingResults({ season, week }),
          Promise.resolve(loadBettingPortfolio()),
        ]);
        if (cancelled) return;
        setModelPayload(model);
        if (portfolioStored.positions.length > 0) {
          const analyzed = await analyzeBettingPortfolio({
            positions: portfolioStored.positions,
            season,
            week,
            status_filter: "all",
          });
          if (cancelled) return;
          setPortfolioAnalysis(analyzed);
          // Persist auto-settled portfolio statuses.
          saveBettingPortfolio(analyzed.positions);
        } else {
          setPortfolioAnalysis(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load betting results."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [season, week, slate.slate_id]);

  const model = modelPayload?.model_results;
  const feedback = modelPayload?.calibration_feedback;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2
            className="text-2xl font-semibold tracking-tight"
            style={{ color: snapshotTokens.textPrimary }}
          >
            Results & Calibration
          </h2>
          <p
            className="mt-1 max-w-2xl text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            When final scores arrive, InsightPilot freezes the
            latest pregame projection, settles every market, and
            feeds residuals into future projections.
          </p>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textMuted }}
          >
            {modelPayload?.label || slate.label}
          </p>
        </div>
        <div
          className="flex rounded-lg border p-1"
          style={{ borderColor: snapshotTokens.border }}
        >
          {(
            [
              ["model", "All markets"],
              ["portfolio", "My portfolio"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setView(id)}
              className="rounded-md px-3 py-1.5 text-sm font-medium"
              style={
                view === id
                  ? {
                      background: snapshotTokens.blue,
                      color: snapshotTokens.white,
                    }
                  : { color: snapshotTokens.textSecondary }
              }
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p
          className="text-sm"
          style={{ color: snapshotTokens.textMuted }}
        >
          Settling completed games against frozen projections…
        </p>
      ) : null}

      {view === "model" ? (
        <>
          <ModelSummaryGrid model={model} />
          <PerformanceTrendPanel
            trend={model?.performance_trend ?? []}
            summary={model?.trend_summary}
          />
          <FeedbackPanel feedback={feedback} />
          <div className="grid gap-4 lg:grid-cols-2">
            <ModelBreakdown
              title="By Market Type"
              rows={model?.by_market ?? []}
            />
            <ModelBreakdown
              title="By Confidence"
              rows={model?.by_confidence ?? []}
            />
          </div>
          <CalibrationPanel
            calibration={model?.calibration ?? []}
          />
          <SettledMarketsTable
            rows={model?.settled_markets ?? []}
            note={model?.note}
          />
        </>
      ) : (
        <PortfolioResultsPanel analysis={portfolioAnalysis} />
      )}
    </div>
  );
}

function ModelSummaryGrid({
  model,
}: {
  model?: BettingModelResultsSummary | null;
}) {
  const cells = [
    {
      label: "Games settled",
      value: String(model?.games_settled ?? 0),
    },
    {
      label: "Markets graded",
      value: String(model?.total_markets ?? 0),
    },
    {
      label: "Model hit rate",
      value:
        model?.hit_rate != null ? `${model.hit_rate}%` : "—",
    },
    {
      label: "Correct / incorrect",
      value: `${model?.model_correct ?? 0} / ${model?.model_incorrect ?? 0}`,
    },
    {
      label: "Avg total error",
      value:
        model?.average_total_error != null
          ? `${model.average_total_error > 0 ? "+" : ""}${model.average_total_error}`
          : "—",
    },
    {
      label: "Avg |spread| error",
      value:
        model?.average_abs_spread_error != null
          ? String(model.average_abs_spread_error)
          : "—",
    },
  ];
  return (
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {cells.map((cell) => (
        <div
          key={cell.label}
          className="rounded-[10px] border bg-white px-4 py-3"
          style={{ borderColor: snapshotTokens.border }}
        >
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.12em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            {cell.label}
          </p>
          <p
            className="mt-1 text-xl font-semibold tabular-nums"
            style={{ color: snapshotTokens.navy }}
          >
            {cell.value}
          </p>
        </div>
      ))}
    </section>
  );
}

function PerformanceTrendPanel({
  trend,
  summary,
}: {
  trend: BettingPerformanceTrendPoint[];
  summary?: BettingPerformanceTrendSummary | null;
}) {
  const direction = summary?.direction ?? "flat";
  const directionLabel =
    direction === "improving"
      ? "Improving"
      : direction === "declining"
        ? "Declining"
        : "Flat";
  const directionColor =
    direction === "improving"
      ? snapshotTokens.success
      : direction === "declining"
        ? snapshotTokens.negative
        : snapshotTokens.textMuted;
  const delta = summary?.hit_rate_delta;

  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3
            className="text-sm font-semibold"
            style={{ color: snapshotTokens.navy }}
          >
            Model Performance Trend
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Weekly and season-to-date hit rate across auto-settled
            markets.
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-right text-sm">
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Season hit rate
            </p>
            <p
              className="mt-0.5 text-lg font-semibold tabular-nums"
              style={{ color: snapshotTokens.navy }}
            >
              {summary?.season_hit_rate != null
                ? `${summary.season_hit_rate}%`
                : "—"}
            </p>
          </div>
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Latest week
            </p>
            <p
              className="mt-0.5 text-lg font-semibold tabular-nums"
              style={{ color: snapshotTokens.navy }}
            >
              {summary?.latest_hit_rate != null
                ? `${summary.latest_hit_rate}%`
                : "—"}
              {delta != null ? (
                <span
                  className="ml-1 text-xs font-semibold"
                  style={{
                    color:
                      delta > 0
                        ? snapshotTokens.success
                        : delta < 0
                          ? snapshotTokens.negative
                          : snapshotTokens.textMuted,
                  }}
                >
                  {delta > 0 ? "+" : ""}
                  {delta} pts
                </span>
              ) : null}
            </p>
          </div>
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Trajectory
            </p>
            <p
              className="mt-0.5 text-lg font-semibold"
              style={{ color: directionColor }}
            >
              {trend.length ? directionLabel : "—"}
            </p>
          </div>
        </div>
      </div>

      {trend.length >= 1 ? (
        <div className="mt-4 h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={trend}
              margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={snapshotTokens.divider}
              />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: snapshotTokens.textMuted }}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: snapshotTokens.textMuted }}
                tickFormatter={(value) => `${value}%`}
                width={40}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 8,
                  borderColor: snapshotTokens.border,
                  fontSize: 12,
                }}
                formatter={(value, name) => {
                  const numeric =
                    typeof value === "number"
                      ? value
                      : Number(value);
                  const label =
                    name === "hit_rate"
                      ? "Week hit rate"
                      : name === "cumulative_hit_rate"
                        ? "Season hit rate"
                        : String(name);
                  return [
                    Number.isFinite(numeric)
                      ? `${numeric}%`
                      : "—",
                    label,
                  ];
                }}
                labelFormatter={(label, payload) => {
                  const point = payload?.[0]?.payload as
                    | BettingPerformanceTrendPoint
                    | undefined;
                  if (!point) return String(label);
                  return `Week ${point.week} · ${point.games_settled} games · ${point.decided} markets`;
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 12 }}
                formatter={(value) =>
                  value === "hit_rate"
                    ? "Weekly hit rate"
                    : "Season-to-date"
                }
              />
              <Line
                type="monotone"
                dataKey="hit_rate"
                stroke={snapshotTokens.blue}
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="cumulative_hit_rate"
                stroke={snapshotTokens.navy}
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p
          className="mt-4 text-sm"
          style={{ color: snapshotTokens.textMuted }}
        >
          Trend appears after markets settle across multiple weeks.
        </p>
      )}

      {trend.length > 0 ? (
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-left text-xs">
            <thead>
              <tr
                className="uppercase tracking-[0.12em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                <th className="py-1.5 pr-3 font-semibold">Week</th>
                <th className="py-1.5 pr-3 font-semibold text-right">
                  Hit %
                </th>
                <th className="py-1.5 pr-3 font-semibold text-right">
                  Season %
                </th>
                <th className="py-1.5 pr-3 font-semibold text-right">
                  Δ
                </th>
                <th className="py-1.5 pr-3 font-semibold text-right">
                  |Spread| err
                </th>
                <th className="py-1.5 font-semibold text-right">
                  Total err
                </th>
              </tr>
            </thead>
            <tbody>
              {[...trend].reverse().map((row) => (
                <tr
                  key={`${row.season}-${row.week}`}
                  className="border-t"
                  style={{ borderColor: snapshotTokens.divider }}
                >
                  <td className="py-1.5 pr-3">{row.label}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {row.hit_rate != null ? `${row.hit_rate}%` : "—"}
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {row.cumulative_hit_rate != null
                      ? `${row.cumulative_hit_rate}%`
                      : "—"}
                  </td>
                  <td
                    className="py-1.5 pr-3 text-right tabular-nums"
                    style={{
                      color:
                        (row.hit_rate_delta ?? 0) > 0
                          ? snapshotTokens.success
                          : (row.hit_rate_delta ?? 0) < 0
                            ? snapshotTokens.negative
                            : snapshotTokens.textMuted,
                    }}
                  >
                    {row.hit_rate_delta != null
                      ? `${row.hit_rate_delta > 0 ? "+" : ""}${row.hit_rate_delta}`
                      : "—"}
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {row.average_abs_spread_error ?? "—"}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {row.average_total_error != null
                      ? `${row.average_total_error > 0 ? "+" : ""}${row.average_total_error}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function FeedbackPanel({
  feedback,
}: {
  feedback?: BettingCalibrationFeedback | null;
}) {
  if (!feedback) return null;
  return (
    <section
      className="rounded-[10px] border px-4 py-3"
      style={{
        borderColor: feedback.active ? "#BBF7D0" : snapshotTokens.border,
        background: feedback.active
          ? snapshotTokens.successLight
          : snapshotTokens.background,
      }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Projection Feedback Loop
        {feedback.active ? " · Active" : " · Warming up"}
      </h3>
      <p
        className="mt-1 text-sm"
        style={{ color: snapshotTokens.textSecondary }}
      >
        {feedback.note}
      </p>
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        <span style={{ color: snapshotTokens.textPrimary }}>
          Sample games:{" "}
          <strong>{feedback.sample_games ?? 0}</strong>
        </span>
        <span style={{ color: snapshotTokens.textPrimary }}>
          Total bias applied:{" "}
          <strong>
            {feedback.total_bias != null
              ? `${feedback.total_bias > 0 ? "+" : ""}${feedback.total_bias}`
              : "—"}
          </strong>
        </span>
        <span style={{ color: snapshotTokens.textPrimary }}>
          Spread bias applied:{" "}
          <strong>
            {feedback.spread_bias != null
              ? `${feedback.spread_bias > 0 ? "+" : ""}${feedback.spread_bias}`
              : "—"}
          </strong>
        </span>
      </div>
    </section>
  );
}

function ModelBreakdown({
  title,
  rows,
}: {
  title: string;
  rows: BettingModelResultsSummary["by_market"];
}) {
  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        {title}
      </h3>
      <table className="mt-3 min-w-full text-left text-sm">
        <thead>
          <tr
            className="text-xs uppercase tracking-[0.12em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            <th className="py-2 pr-3 font-semibold">Segment</th>
            <th className="py-2 pr-3 font-semibold text-right">
              Markets
            </th>
            <th className="py-2 pr-3 font-semibold text-right">
              Hit %
            </th>
            <th className="py-2 font-semibold text-right">
              Avg edge
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className="border-t capitalize"
              style={{ borderColor: snapshotTokens.divider }}
            >
              <td className="py-2 pr-3">{row.key}</td>
              <td className="py-2 pr-3 text-right tabular-nums">
                {row.bets}
              </td>
              <td className="py-2 pr-3 text-right tabular-nums">
                {row.hit_rate != null ? `${row.hit_rate}%` : "—"}
              </td>
              <td className="py-2 text-right tabular-nums">
                {row.average_edge != null
                  ? `${row.average_edge > 0 ? "+" : ""}${row.average_edge.toFixed(1)}%`
                  : "—"}
              </td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={4}
                className="py-4 text-sm"
                style={{ color: snapshotTokens.textMuted }}
              >
                No settled markets yet this week.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </section>
  );
}

function CalibrationPanel({
  calibration,
}: {
  calibration: BettingModelResultsSummary["calibration"];
}) {
  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Model Calibration
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Predicted probability bands versus observed hit rate on
        auto-settled markets.
      </p>
      <ul className="mt-3 space-y-2">
        {calibration.map((row) => (
          <li
            key={row.bucket}
            className="flex items-center justify-between gap-3 text-sm"
          >
            <span style={{ color: snapshotTokens.textSecondary }}>
              {row.bucket}
              <span
                className="ml-2 text-xs"
                style={{ color: snapshotTokens.textMuted }}
              >
                n={row.bets}
              </span>
            </span>
            <span className="tabular-nums font-medium">
              {row.actual_win_rate != null
                ? `${row.actual_win_rate}%`
                : "—"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SettledMarketsTable({
  rows,
  note,
}: {
  rows: BettingModelResultsSummary["settled_markets"];
  note?: string | null;
}) {
  return (
    <section
      className="flex max-h-[480px] flex-col overflow-hidden rounded-[10px] border bg-white"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div
        className="shrink-0 border-b px-4 py-3"
        style={{ borderColor: snapshotTokens.divider }}
      >
        <h3
          className="text-sm font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Settled Markets
          {rows.length > 0 ? (
            <span
              className="ml-2 text-xs font-normal"
              style={{ color: snapshotTokens.textMuted }}
            >
              {rows.length}
            </span>
          ) : null}
        </h3>
        {note ? (
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {note}
          </p>
        ) : null}
      </div>
      <div
        className="min-h-0 flex-1 overflow-auto"
        style={{ maxHeight: SETTLED_TABLE_MAX_HEIGHT }}
      >
        <table className="min-w-full text-left text-sm">
          <thead
            className="sticky top-0 z-[1]"
            style={{ background: "#fff" }}
          >
            <tr
              className="text-xs uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              <th className="px-4 py-2 font-semibold">Game</th>
              <th className="px-3 py-2 font-semibold">Market</th>
              <th className="px-3 py-2 font-semibold text-right">
                Final
              </th>
              <th className="px-3 py-2 font-semibold text-right">
                Model
              </th>
              <th className="px-3 py-2 font-semibold text-right">
                Error
              </th>
              <th className="px-3 py-2 font-semibold">Result</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.market_id}
                className="border-t"
                style={{ borderColor: snapshotTokens.divider }}
              >
                <td className="px-4 py-2.5">
                  <span
                    className="font-medium"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {row.event_label}
                  </span>
                  <span
                    className="mt-0.5 block text-xs"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {row.away_team} {row.away_score} @ {row.home_team}{" "}
                    {row.home_score}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span className="capitalize">
                    {row.market_type}
                  </span>
                  <span
                    className="mt-0.5 block text-xs"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {row.selection}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">
                  {row.market_type === "total"
                    ? row.actual_total
                    : row.actual_spread != null
                      ? `${row.actual_spread > 0 ? "+" : ""}${row.actual_spread}`
                      : "—"}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">
                  {row.market_type === "total"
                    ? row.model_total
                    : row.model_spread != null
                      ? `${row.model_spread > 0 ? "+" : ""}${row.model_spread}`
                      : "—"}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">
                  {row.market_type === "total"
                    ? row.total_error != null
                      ? `${row.total_error > 0 ? "+" : ""}${row.total_error}`
                      : "—"
                    : row.spread_error != null
                      ? `${row.spread_error > 0 ? "+" : ""}${row.spread_error}`
                      : "—"}
                </td>
                <td
                  className="px-3 py-2.5 capitalize font-medium"
                  style={{
                    color:
                      row.result === "won"
                        ? snapshotTokens.success
                        : row.result === "lost"
                          ? snapshotTokens.negative
                          : snapshotTokens.textPrimary,
                  }}
                >
                  {row.result}
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-sm"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  No final scores for this week yet. Results populate
                  automatically after games complete and data
                  refreshes.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PortfolioResultsPanel({
  analysis,
}: {
  analysis: BettingPortfolioAnalyzeResult | null;
}) {
  const results = analysis?.results;
  const settled = results?.settled_positions ?? [];
  if (!analysis) {
    return (
      <p
        className="text-sm"
        style={{ color: snapshotTokens.textMuted }}
      >
        No portfolio positions yet. Open positions auto-settle when
        matching markets grade from final scores.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Settled", String(results?.total_positions ?? 0)],
          [
            "Win rate",
            results?.win_rate != null
              ? `${results.win_rate}%`
              : "—",
          ],
          [
            "P/L",
            results?.profit_loss != null
              ? `${results.profit_loss >= 0 ? "+" : ""}$${results.profit_loss.toFixed(2)}`
              : "—",
          ],
          [
            "ROI",
            results?.roi_pct != null
              ? `${results.roi_pct >= 0 ? "+" : ""}${results.roi_pct}%`
              : "—",
          ],
        ].map(([label, value]) => (
          <div
            key={label}
            className="rounded-[10px] border bg-white px-4 py-3"
            style={{ borderColor: snapshotTokens.border }}
          >
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              {label}
            </p>
            <p
              className="mt-1 text-xl font-semibold tabular-nums"
              style={{ color: snapshotTokens.navy }}
            >
              {value}
            </p>
          </div>
        ))}
      </section>
      <section
        className="flex max-h-[480px] flex-col overflow-hidden rounded-[10px] border bg-white"
        style={{ borderColor: snapshotTokens.border }}
      >
        <div
          className="shrink-0 border-b px-4 py-3"
          style={{ borderColor: snapshotTokens.divider }}
        >
          <h3
            className="text-sm font-semibold"
            style={{ color: snapshotTokens.navy }}
          >
            Portfolio Settlements
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Open portfolio singles are auto-marked when the
            underlying market grades from the final score.
          </p>
        </div>
        <div
          className="min-h-0 flex-1 overflow-auto"
          style={{ maxHeight: SETTLED_TABLE_MAX_HEIGHT }}
        >
          <table className="min-w-full text-left text-sm">
            <thead
              className="sticky top-0 z-[1]"
              style={{ background: "#fff" }}
            >
              <tr
                className="text-xs uppercase tracking-[0.12em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                <th className="px-4 py-2 font-semibold">Position</th>
                <th className="px-3 py-2 font-semibold text-right">
                  Entry
                </th>
                <th className="px-3 py-2 font-semibold text-right">
                  P/L
                </th>
                <th className="px-3 py-2 font-semibold">Result</th>
              </tr>
            </thead>
            <tbody>
              {settled.map((row) => (
                <tr
                  key={row.position_id}
                  className="border-t"
                  style={{ borderColor: snapshotTokens.divider }}
                >
                  <td className="px-4 py-2.5">
                    <span className="font-medium">
                      {row.selection}
                    </span>
                    <span
                      className="mt-0.5 block text-xs"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      {row.event_label}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {formatAmerican(row.entry_price)}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {row.profit_loss != null
                      ? `${row.profit_loss >= 0 ? "+" : ""}$${row.profit_loss.toFixed(2)}`
                      : "—"}
                  </td>
                  <td className="px-3 py-2.5 capitalize">
                    {row.status}
                  </td>
                </tr>
              ))}
              {settled.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-8 text-sm"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    No settled portfolio positions yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
