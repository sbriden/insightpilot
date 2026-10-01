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
  BettingClvBreakdownRow,
  BettingEdgeConfidenceDiagnostics,
  BettingMarketPerformance,
  BettingMarketPerformanceCard,
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

function formatSettledLine(
  line: number | null | undefined,
  marketType?: string | null,
): string {
  if (line == null) return "—";
  if (marketType === "spread") {
    return `${line > 0 ? "+" : ""}${line}`;
  }
  return String(line);
}

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
  const probCal = modelPayload?.probability_calibration;

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
          <ProbabilityCalibrationPanel calibration={probCal} />
          <EdgeConfidencePanel
            diagnostics={
              model?.edge_confidence
              ?? modelPayload?.edge_confidence
              ?? null
            }
            buckets={model?.by_edge_bucket ?? []}
          />
          <MarketPerformancePanel
            performance={
              model?.market_performance
              ?? modelPayload?.market_performance
              ?? null
            }
            rows={model?.by_market ?? []}
          />
          <div className="grid gap-4 lg:grid-cols-2">
            <ModelBreakdown
              title="By Confidence"
              rows={model?.by_confidence ?? []}
            />
            <ModelBreakdown
              title="By Favorite / Underdog"
              rows={model?.by_favorite_underdog ?? []}
            />
            <ModelBreakdown
              title="By Home / Away"
              rows={model?.by_home_away ?? []}
            />
            <ModelBreakdown
              title="By Week"
              rows={model?.by_week ?? []}
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
      label: "Avg CLV",
      value:
        model?.average_clv != null
          ? `${model.average_clv > 0 ? "+" : ""}${model.average_clv}`
          : "—",
    },
    {
      label: "Median CLV",
      value:
        model?.median_clv != null
          ? `${model.median_clv > 0 ? "+" : ""}${model.median_clv}`
          : "—",
    },
    {
      label: "Beat close %",
      value:
        model?.beat_close_pct != null
          ? `${model.beat_close_pct}%`
          : "—",
    },
    {
      label: "ROI / Units",
      value:
        model?.roi_pct != null && model?.units != null
          ? `${model.roi_pct > 0 ? "+" : ""}${model.roi_pct}% / ${model.units > 0 ? "+" : ""}${model.units}u`
          : "—",
    },
    {
      label: "ATS / O-U / ML",
      value: [
        model?.ats_win_pct != null ? `${model.ats_win_pct}%` : "—",
        model?.ou_win_pct != null ? `${model.ou_win_pct}%` : "—",
        model?.ml_win_pct != null ? `${model.ml_win_pct}%` : "—",
      ].join(" · "),
    },
    {
      label: "Avg edge",
      value:
        model?.average_edge != null
          ? `${model.average_edge > 0 ? "+" : ""}${model.average_edge}`
          : "—",
    },
    {
      label: "Avg closing edge",
      value:
        model?.average_closing_edge != null
          ? `${model.average_closing_edge > 0 ? "+" : ""}${model.average_closing_edge}`
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

function MarketPerformancePanel({
  performance,
  rows,
}: {
  performance?: BettingMarketPerformance | null;
  rows: BettingClvBreakdownRow[];
}) {
  const cards: BettingMarketPerformanceCard[] = performance?.markets
    ? (["spread", "total", "moneyline"] as const).map((key) => {
        const card = performance.markets?.[key];
        return (
          card || {
            market_type: key,
            label:
              key === "spread"
                ? "Spread"
                : key === "total"
                  ? "Total"
                  : "Moneyline",
            sample_size: 0,
          }
        );
      })
    : rows.map((row) => ({
        ...row,
        label: row.key,
        market_type: row.key,
      }));

  const winLabel = (card: BettingMarketPerformanceCard) => {
    if (card.market_type === "spread" || card.ats_win_pct != null) {
      return {
        label: "ATS %",
        value: card.ats_win_pct ?? card.hit_rate,
      };
    }
    if (card.market_type === "total" || card.ou_win_pct != null) {
      return {
        label: "O/U %",
        value: card.ou_win_pct ?? card.hit_rate,
      };
    }
    return {
      label: "Win %",
      value: card.win_pct ?? card.hit_rate,
    };
  };

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
            Model performance by market
          </h3>
          <p
            className="mt-1 max-w-3xl text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {performance?.note
              || "Spread, total, and moneyline are scored as separate models. Confidence floors follow market quality."}
          </p>
        </div>
        {performance?.best_market ? (
          <div
            className="text-sm"
            style={{ color: snapshotTokens.textMuted }}
          >
            Leading:{" "}
            <strong style={{ color: snapshotTokens.textPrimary }}>
              {performance.best_market}
            </strong>
          </div>
        ) : null}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {cards.map((card) => {
          const win = winLabel(card);
          const showMae = card.market_type !== "moneyline";
          return (
            <div
              key={card.market_type || card.label || card.key}
              className="rounded-[10px] border px-3 py-3"
              style={{ borderColor: snapshotTokens.divider }}
            >
              <div className="flex items-baseline justify-between gap-2">
                <h4
                  className="text-sm font-semibold"
                  style={{ color: snapshotTokens.navy }}
                >
                  {card.label || card.market_type}
                </h4>
                <span
                  className="text-xs tabular-nums"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  n={card.sample_size ?? card.decided ?? card.bets ?? 0}
                </span>
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
                <div>
                  <dt style={{ color: snapshotTokens.textMuted }}>
                    {win.label}
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {win.value != null ? `${win.value}%` : "—"}
                  </dd>
                </div>
                <div>
                  <dt style={{ color: snapshotTokens.textMuted }}>
                    ROI
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {card.roi_pct != null
                      ? `${card.roi_pct > 0 ? "+" : ""}${card.roi_pct}%`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt style={{ color: snapshotTokens.textMuted }}>
                    CLV
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {card.average_clv != null
                      ? `${card.average_clv > 0 ? "+" : ""}${card.average_clv.toFixed(2)}`
                      : "—"}
                  </dd>
                </div>
                {showMae ? (
                  <div>
                    <dt style={{ color: snapshotTokens.textMuted }}>
                      MAE
                    </dt>
                    <dd className="font-medium tabular-nums">
                      {card.mae != null ? card.mae.toFixed(2) : "—"}
                    </dd>
                  </div>
                ) : (
                  <div>
                    <dt style={{ color: snapshotTokens.textMuted }}>
                      Brier
                    </dt>
                    <dd className="font-medium tabular-nums">
                      {card.brier != null
                        ? card.brier.toFixed(3)
                        : "—"}
                    </dd>
                  </div>
                )}
                <div>
                  <dt style={{ color: snapshotTokens.textMuted }}>
                    Cal gap
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {card.calibration_gap != null
                      ? `${card.calibration_gap > 0 ? "+" : ""}${card.calibration_gap}`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt style={{ color: snapshotTokens.textMuted }}>
                    Conf weight
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {card.confidence_weight != null
                      ? card.confidence_weight.toFixed(2)
                      : "—"}
                  </dd>
                </div>
              </dl>
              {card.high_min != null || card.moderate_min != null ? (
                <p
                  className="mt-3 text-xs"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Floors · High ≥ {card.high_min ?? "—"} · Moderate ≥{" "}
                  {card.moderate_min ?? "—"}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function EdgeConfidencePanel({
  diagnostics,
  buckets,
}: {
  diagnostics?: BettingEdgeConfidenceDiagnostics | null;
  buckets: BettingClvBreakdownRow[];
}) {
  const thresholds = diagnostics?.thresholds;
  const rows =
    (diagnostics?.buckets && diagnostics.buckets.length > 0
      ? diagnostics.buckets
      : buckets) ?? [];
  const active = Boolean(thresholds?.active);
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
            Point-edge backtest
            {active
              ? " · thresholds learned"
              : " · learning"}
          </h3>
          <p
            className="mt-1 max-w-3xl text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {diagnostics?.note
              || thresholds?.note
              || "Confidence is learned from historical win rate, ROI, CLV, and calibration by point-edge bucket — not fixed 1.5 / 3.5 cutoffs."}
          </p>
        </div>
        <div className="text-right text-sm tabular-nums">
          <div style={{ color: snapshotTokens.textMuted }}>
            High ≥{" "}
            <strong style={{ color: snapshotTokens.textPrimary }}>
              {thresholds?.high_min != null
                ? thresholds.high_min
                : "3.5"}
            </strong>
            {" · "}
            Moderate ≥{" "}
            <strong style={{ color: snapshotTokens.textPrimary }}>
              {thresholds?.moderate_min != null
                ? thresholds.moderate_min
                : "1.5"}
            </strong>
          </div>
          <div
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textMuted }}
          >
            n={thresholds?.sample_size ?? 0}
          </div>
        </div>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr
              className="text-xs uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              <th className="py-2 pr-3 font-semibold">Edge pts</th>
              <th className="py-2 pr-3 font-semibold text-right">n</th>
              <th className="py-2 pr-3 font-semibold text-right">
                Win %
              </th>
              <th className="py-2 pr-3 font-semibold text-right">
                ROI
              </th>
              <th className="py-2 pr-3 font-semibold text-right">
                Avg CLV
              </th>
              <th className="py-2 font-semibold text-right">
                Cal gap
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.key}
                className="border-t"
                style={{ borderColor: snapshotTokens.divider }}
              >
                <td className="py-2 pr-3">{row.key}</td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {row.sample_size ?? row.decided ?? row.bets ?? 0}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {row.win_rate != null
                    ? `${row.win_rate}%`
                    : row.hit_rate != null
                      ? `${row.hit_rate}%`
                      : "—"}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {row.roi_pct != null
                    ? `${row.roi_pct > 0 ? "+" : ""}${row.roi_pct}%`
                    : "—"}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {row.average_clv != null
                    ? `${row.average_clv > 0 ? "+" : ""}${row.average_clv.toFixed(2)}`
                    : "—"}
                </td>
                <td className="py-2 text-right tabular-nums">
                  {row.calibration_gap != null
                    ? `${row.calibration_gap > 0 ? "+" : ""}${row.calibration_gap}`
                    : row.calibration?.gap_pp != null
                      ? `${row.calibration.gap_pp > 0 ? "+" : ""}${row.calibration.gap_pp}`
                      : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ProbabilityCalibrationPanel({
  calibration,
}: {
  calibration?: BettingResultsPayload["probability_calibration"];
}) {
  if (!calibration) return null;
  const metrics = calibration.metrics;
  return (
    <section
      className="rounded-[10px] border px-4 py-3"
      style={{
        borderColor: calibration.active
          ? "#BBF7D0"
          : snapshotTokens.border,
        background: calibration.active
          ? snapshotTokens.successLight
          : snapshotTokens.background,
      }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Probability Calibration
        {calibration.active
          ? ` · ${calibration.method || "active"}`
          : " · Warming up"}
      </h3>
      <p
        className="mt-1 text-sm"
        style={{ color: snapshotTokens.textSecondary }}
      >
        {calibration.note
          || "Maps raw logistic probabilities onto historical win rates (Platt / isotonic)."}
      </p>
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        <span style={{ color: snapshotTokens.textPrimary }}>
          Sample bets:{" "}
          <strong>{calibration.sample_size ?? 0}</strong>
        </span>
        <span style={{ color: snapshotTokens.textPrimary }}>
          Brier:{" "}
          <strong>
            {metrics?.brier_raw != null
              && metrics?.brier_calibrated != null
              ? `${metrics.brier_raw.toFixed(3)} → ${metrics.brier_calibrated.toFixed(3)}`
              : "—"}
          </strong>
        </span>
        <span style={{ color: snapshotTokens.textPrimary }}>
          ECE:{" "}
          <strong>
            {metrics?.ece_raw != null
              && metrics?.ece_calibrated != null
              ? `${metrics.ece_raw.toFixed(3)} → ${metrics.ece_calibrated.toFixed(3)}`
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
            <th className="py-2 pr-3 font-semibold text-right">
              Avg CLV
            </th>
            <th className="py-2 font-semibold text-right">
              ROI
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
              <td className="py-2 pr-3 text-right tabular-nums">
                {row.average_clv != null
                  ? `${row.average_clv > 0 ? "+" : ""}${row.average_clv.toFixed(2)}`
                  : "—"}
              </td>
              <td className="py-2 text-right tabular-nums">
                {row.roi_pct != null
                  ? `${row.roi_pct > 0 ? "+" : ""}${row.roi_pct.toFixed(1)}%`
                  : "—"}
              </td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={5}
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
                Bet
              </th>
              <th className="px-3 py-2 font-semibold text-right">
                Close
              </th>
              <th className="px-3 py-2 font-semibold text-right">
                CLV
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
                  {formatSettledLine(row.bet_line ?? row.line, row.market_type)}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">
                  {formatSettledLine(row.closing_line, row.market_type)}
                </td>
                <td
                  className="px-3 py-2.5 text-right tabular-nums font-medium"
                  style={{
                    color:
                      row.clv != null && row.clv > 0
                        ? snapshotTokens.success
                        : row.clv != null && row.clv < 0
                          ? snapshotTokens.negative
                          : snapshotTokens.textPrimary,
                  }}
                >
                  {row.clv != null
                    ? `${row.clv > 0 ? "+" : ""}${row.clv}`
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
