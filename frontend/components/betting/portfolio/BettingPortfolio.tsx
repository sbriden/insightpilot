"use client";

import { useEffect, useMemo, useState } from "react";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import { formatAmerican } from "@/components/betting/formatMarketValues";
import {
  exportBettingPortfolio,
  loadBettingPortfolio,
  saveBettingPortfolio,
} from "@/components/betting/portfolio/portfolioStorage";
import {
  analyzeBettingPortfolio,
  BettingMarket,
  BettingPortfolioAnalytics,
  BettingPortfolioAnalyzeResult,
  BettingPortfolioPosition,
  BettingSlate,
  createBettingPortfolioPosition,
  generateBettingPortfolio,
} from "@/services/api";

interface Props {
  slate: BettingSlate;
  season: number | null;
  week: number | null;
  pendingMarket?: BettingMarket | null;
  onPendingMarketConsumed?: () => void;
  onOpenMarket?: (
    market: BettingMarket,
    position?: BettingPortfolioPosition
  ) => void;
}

type ExposureTab = "team" | "game" | "sport" | "market";
type StatusFilter = "open" | "all" | "settled";

export default function BettingPortfolio({
  slate,
  season,
  week,
  pendingMarket = null,
  onPendingMarketConsumed,
  onOpenMarket,
}: Props) {
  const [positions, setPositions] = useState<
    BettingPortfolioPosition[]
  >([]);
  const [hydrated, setHydrated] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [analysis, setAnalysis] =
    useState<BettingPortfolioAnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] =
    useState<StatusFilter>("open");
  const [exposureTab, setExposureTab] =
    useState<ExposureTab>("game");
  const [addOpen, setAddOpen] = useState(false);
  const [addExposure, setAddExposure] = useState(25);
  const [addNotes, setAddNotes] = useState("");
  const [selectedMarketId, setSelectedMarketId] = useState<
    string | null
  >(null);
  const [message, setMessage] = useState<string | null>(null);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [totalExposureInput, setTotalExposureInput] = useState(250);
  const [riskExposureInput, setRiskExposureInput] = useState(75);
  const [riskProfile, setRiskProfile] = useState<
    "conservative" | "balanced" | "aggressive"
  >("balanced");
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    const stored = loadBettingPortfolio();
    setPositions(stored.positions);
    setSavedAt(stored.savedAt);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    void recalculate(positions, statusFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, season, week, statusFilter]);

  useEffect(() => {
    if (!pendingMarket) return;
    setSelectedMarketId(pendingMarket.market_id);
    setAddOpen(true);
    onPendingMarketConsumed?.();
  }, [pendingMarket, onPendingMarketConsumed]);

  async function recalculate(
    nextPositions: BettingPortfolioPosition[],
    filter: StatusFilter
  ) {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeBettingPortfolio({
        positions: nextPositions,
        season,
        week,
        status_filter:
          filter === "settled" ? "all" : filter,
      });
      let visible = result.visible_positions;
      if (filter === "settled") {
        visible = result.positions.filter((row) =>
          ["won", "lost", "push", "void", "cancelled"].includes(
            String(row.status || "").toLowerCase()
          )
        );
      }
      setAnalysis({
        ...result,
        visible_positions: visible,
      });
      // Keep local positions refreshed with current prices.
      setPositions(result.positions);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to analyze portfolio."
      );
    } finally {
      setLoading(false);
    }
  }

  async function runGenerate(replaceOpen: boolean) {
    if (totalExposureInput <= 0 || riskExposureInput <= 0) {
      setError("Enter total exposure and risk exposure amounts.");
      return;
    }
    if (riskExposureInput > totalExposureInput) {
      setError(
        "Risk exposure cannot exceed total exposure."
      );
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const result = await generateBettingPortfolio({
        total_exposure: totalExposureInput,
        risk_exposure: riskExposureInput,
        season,
        week,
        risk: riskProfile,
      });
      const generated = result.positions ?? [];
      const kept = replaceOpen
        ? positions.filter(
            (row) =>
              String(row.status || "").toLowerCase() !== "open"
          )
        : positions;
      const generatedIds = new Set(
        generated.map((row) => row.market_id)
      );
      const merged = [
        ...generated,
        ...kept.filter(
          (row) =>
            !generatedIds.has(row.market_id)
            || String(row.status || "").toLowerCase() !== "open"
        ),
      ];
      persist(merged);
      setGenerateOpen(false);
      setMessage(
        `Generated ${result.generation.position_count} positions (${result.generation.single_count ?? 0} singles · ${result.generation.parlay_count ?? 0} parlays) · $${Math.round(
          result.generation.allocated_exposure
        )} allocated · max $${Math.round(
          result.generation.risk_exposure
        )} per game.`
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to generate portfolio."
      );
    } finally {
      setGenerating(false);
    }
  }

  function persist(next: BettingPortfolioPosition[]) {
    setPositions(next);
    const stamp = saveBettingPortfolio(next);
    setSavedAt(stamp);
    void recalculate(next, statusFilter);
  }

  async function addSelectedPosition() {
    const market =
      slate.markets.find(
        (row) => row.market_id === selectedMarketId
      ) ?? pendingMarket;
    if (!market) {
      setError("Select a market to add.");
      return;
    }
    try {
      const position = await createBettingPortfolioPosition({
        market,
        exposure: addExposure,
        notes: addNotes.trim() || null,
      });
      const withoutDup = positions.filter(
        (row) =>
          row.market_id !== position.market_id
          || row.status !== "open"
      );
      persist([position, ...withoutDup]);
      setAddOpen(false);
      setAddNotes("");
      setMessage(`Added ${position.selection} to portfolio.`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to add position."
      );
    }
  }

  function removePosition(positionId: string) {
    persist(
      positions.filter((row) => row.position_id !== positionId)
    );
  }

  function markStatus(
    positionId: string,
    status: BettingPortfolioPosition["status"]
  ) {
    persist(
      positions.map((row) =>
        row.position_id === positionId
          ? { ...row, status, result: status }
          : row
      )
    );
  }

  const analytics: BettingPortfolioAnalytics | null =
    analysis?.analytics ?? null;
  const visible = analysis?.visible_positions ?? [];

  const marketOptions = useMemo(() => {
    return [...(slate.markets ?? [])].sort((a, b) =>
      Math.abs(b.edge ?? 0) - Math.abs(a.edge ?? 0)
    );
  }, [slate.markets]);

  if (!hydrated) {
    return (
      <p
        className="text-sm"
        style={{ color: snapshotTokens.textMuted }}
      >
        Loading portfolio…
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2
            className="text-2xl font-semibold tracking-tight"
            style={{ color: snapshotTokens.textPrimary }}
          >
            Betting Portfolio
          </h2>
          <p
            className="mt-1 max-w-2xl text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Analyze your positions, market exposure,
            correlations, and portfolio performance with
            InsightPilot.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            className="rounded-lg border bg-white px-3 py-2 text-sm"
            style={{ borderColor: snapshotTokens.border }}
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value as StatusFilter)
            }
            aria-label="Position status filter"
          >
            <option value="open">Open</option>
            <option value="all">All</option>
            <option value="settled">Settled</option>
          </select>
          <button
            type="button"
            onClick={() => void recalculate(positions, statusFilter)}
            className="rounded-lg border bg-white px-3 py-2 text-sm font-medium"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
          >
            {loading ? "Recalculating…" : "Recalculate"}
          </button>
          <button
            type="button"
            onClick={() => {
              const stamp = saveBettingPortfolio(positions);
              setSavedAt(stamp);
              setMessage("Portfolio saved.");
            }}
            className="rounded-lg border bg-white px-3 py-2 text-sm font-medium"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
          >
            Save
          </button>
          <button
            type="button"
            onClick={() => exportBettingPortfolio(positions)}
            className="rounded-lg border bg-white px-3 py-2 text-sm font-medium"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textSecondary,
            }}
          >
            Export
          </button>
          <button
            type="button"
            onClick={() => setGenerateOpen(true)}
            className="rounded-lg border bg-white px-3 py-2 text-sm font-medium"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
          >
            Generate Portfolio
          </button>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="rounded-lg px-3 py-2 text-sm font-medium text-white"
            style={{ background: snapshotTokens.blue }}
          >
            + Add Position
          </button>
        </div>
      </header>

      {savedAt ? (
        <p
          className="text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          Saved {new Date(savedAt).toLocaleString()}
        </p>
      ) : null}

      {message ? (
        <div
          className="rounded-xl border px-4 py-3 text-sm"
          style={{
            borderColor: "#BFDBFE",
            background: snapshotTokens.blueLight,
            color: snapshotTokens.navy,
          }}
        >
          {message}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <SummaryBar analytics={analytics} />

      <HealthPanel health={analytics?.health ?? []} />

      {(analytics?.alerts?.length ?? 0) > 0 ? (
        <AlertsPanel alerts={analytics!.alerts} />
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(260px,0.9fr)]">
        <section
          className="rounded-[10px] border bg-white"
          style={{ borderColor: snapshotTokens.border }}
        >
          <div
            className="border-b px-4 py-3"
            style={{ borderColor: snapshotTokens.divider }}
          >
            <h3
              className="text-sm font-semibold"
              style={{ color: snapshotTokens.navy }}
            >
              Open Positions
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr
                  className="text-xs uppercase tracking-[0.12em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  <th className="px-4 py-2 font-semibold">Position</th>
                  <th className="px-3 py-2 font-semibold">Type</th>
                  <th className="px-3 py-2 font-semibold">Market</th>
                  <th className="px-3 py-2 font-semibold text-right">
                    Entry
                  </th>
                  <th className="px-3 py-2 font-semibold text-right">
                    Current
                  </th>
                  <th className="px-3 py-2 font-semibold text-right">
                    Model
                  </th>
                  <th className="px-3 py-2 font-semibold text-right">
                    Edge
                  </th>
                  <th className="px-3 py-2 font-semibold">Conf.</th>
                  <th className="px-3 py-2 font-semibold text-right">
                    Exposure
                  </th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="px-3 py-2 font-semibold" />
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr
                    key={row.position_id}
                    className="border-t"
                    style={{ borderColor: snapshotTokens.divider }}
                  >
                    <td className="px-4 py-2.5">
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => {
                          const market = slate.markets.find(
                            (item) =>
                              item.market_id === row.market_id
                          );
                          if (market && onOpenMarket) {
                            onOpenMarket(market, row);
                          }
                        }}
                      >
                        <span
                          className="font-medium"
                          style={{
                            color: snapshotTokens.textPrimary,
                          }}
                        >
                          {row.selection || "—"}
                        </span>
                        <span
                          className="mt-0.5 block text-xs"
                          style={{
                            color: snapshotTokens.textMuted,
                          }}
                        >
                          {row.event_label}
                        </span>
                      </button>
                    </td>
                    <td
                      className="px-3 py-2.5"
                      style={{ color: snapshotTokens.textSecondary }}
                    >
                      {row.bet_type === "parlay"
                        ? `Parlay · ${row.parlay_size || "small"} (${row.leg_count ?? row.legs?.length ?? "—"})`
                        : "Single"}
                    </td>
                    <td
                      className="px-3 py-2.5 capitalize"
                      style={{ color: snapshotTokens.textSecondary }}
                    >
                      {row.bet_type === "parlay"
                        ? "parlay"
                        : row.market_type || "—"}
                    </td>
                    <td
                      className="px-3 py-2.5 text-right tabular-nums"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {formatAmerican(row.entry_price)}
                    </td>
                    <td
                      className="px-3 py-2.5 text-right tabular-nums"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {formatAmerican(row.current_price)}
                      {row.price_movement != null
                      && row.price_movement !== 0 ? (
                        <span
                          className="mt-0.5 block text-[11px]"
                          style={{
                            color: snapshotTokens.textMuted,
                          }}
                        >
                          {row.price_movement > 0 ? "+" : ""}
                          {row.price_movement}¢
                        </span>
                      ) : null}
                    </td>
                    <td
                      className="px-3 py-2.5 text-right tabular-nums"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {row.model_probability != null
                        ? `${Math.round(row.model_probability * 100)}%`
                        : "—"}
                    </td>
                    <td
                      className="px-3 py-2.5 text-right tabular-nums"
                      style={{
                        color:
                          (row.edge ?? 0) > 0
                            ? snapshotTokens.success
                            : (row.edge ?? 0) < 0
                              ? snapshotTokens.negative
                              : snapshotTokens.textPrimary,
                      }}
                    >
                      {row.edge != null
                        ? `${row.edge > 0 ? "+" : ""}${row.edge.toFixed(1)}%`
                        : "—"}
                    </td>
                    <td
                      className="px-3 py-2.5"
                      style={{ color: snapshotTokens.textSecondary }}
                    >
                      {row.confidence || "—"}
                    </td>
                    <td
                      className="px-3 py-2.5 text-right tabular-nums"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      ${Math.round(row.exposure)}
                    </td>
                    <td className="px-3 py-2.5">
                      <select
                        className="rounded border bg-white px-1.5 py-1 text-xs"
                        style={{ borderColor: snapshotTokens.border }}
                        value={row.status}
                        onChange={(event) =>
                          markStatus(
                            row.position_id,
                            event.target.value
                          )
                        }
                      >
                        {[
                          "open",
                          "won",
                          "lost",
                          "push",
                          "void",
                        ].map((status) => (
                          <option key={status} value={status}>
                            {status}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <button
                        type="button"
                        className="text-xs"
                        style={{ color: snapshotTokens.negative }}
                        onClick={() =>
                          removePosition(row.position_id)
                        }
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
                {visible.length === 0 ? (
                  <tr>
                    <td
                      colSpan={11}
                      className="px-4 py-8 text-sm"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      No positions yet. Add from market analysis
                      or use + Add Position.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="space-y-4">
          <ModelVsMarketPanel
            modelVsMarket={analytics?.model_vs_market}
          />
          <AssumptionsPanel
            assumptions={analytics?.assumptions ?? []}
          />
        </aside>
      </div>

      <ExposurePanel
        tab={exposureTab}
        onTab={setExposureTab}
        exposure={analytics?.exposure}
      />

      <CorrelationPanel
        correlations={analytics?.correlations ?? []}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <DistributionPanel
          title="Edge Distribution"
          rows={(analytics?.edge_distribution ?? []).map(
            (row) => ({
              label: row.bucket,
              value: row.count,
            })
          )}
        />
        <DistributionPanel
          title="Confidence Distribution"
          rows={(analytics?.confidence_distribution ?? []).map(
            (row) => ({
              label: row.confidence,
              value: `${row.pct}%`,
            })
          )}
        />
      </div>

      <MovementPanel movements={analytics?.price_movements ?? []} />

      {generateOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/30"
            aria-label="Close generate portfolio"
            onClick={() => setGenerateOpen(false)}
          />
          <div
            className="relative z-10 w-full max-w-lg rounded-xl border bg-white p-5 shadow-xl"
            style={{ borderColor: snapshotTokens.border }}
          >
            <h3
              className="text-lg font-semibold"
              style={{ color: snapshotTokens.textPrimary }}
            >
              Generate Portfolio
            </h3>
            <p
              className="mt-1 text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              InsightPilot builds a mix of singles and
              small/medium/large parlays. Selection stance sets
              that mix; risk exposure caps how much can sit in
              any single game.
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <label
                  className="text-xs font-semibold uppercase tracking-[0.12em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Total exposure ($)
                </label>
                <input
                  type="number"
                  min={1}
                  className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                  style={{ borderColor: snapshotTokens.border }}
                  value={totalExposureInput}
                  onChange={(event) =>
                    setTotalExposureInput(
                      Number(event.target.value) || 0
                    )
                  }
                />
              </div>
              <div>
                <label
                  className="text-xs font-semibold uppercase tracking-[0.12em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Risk exposure ($)
                </label>
                <input
                  type="number"
                  min={1}
                  className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                  style={{ borderColor: snapshotTokens.border }}
                  value={riskExposureInput}
                  onChange={(event) =>
                    setRiskExposureInput(
                      Number(event.target.value) || 0
                    )
                  }
                />
                <p
                  className="mt-1 text-[11px]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Max allocated to one game
                </p>
              </div>
            </div>
            <label
              className="mt-3 block text-xs font-semibold uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Selection stance
            </label>
            <select
              className="mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm"
              style={{ borderColor: snapshotTokens.border }}
              value={riskProfile}
              onChange={(event) =>
                setRiskProfile(
                  event.target.value as
                    | "conservative"
                    | "balanced"
                    | "aggressive"
                )
              }
            >
              <option value="conservative">
                Conservative — ~80% singles, mostly small parlays
              </option>
              <option value="balanced">
                Balanced — ~55% singles, mix of small/medium parlays
              </option>
              <option value="aggressive">
                Aggressive — ~30% singles, more medium/large parlays
              </option>
            </select>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border px-3 py-2 text-sm"
                style={{ borderColor: snapshotTokens.border }}
                onClick={() => setGenerateOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={generating}
                className="rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-50"
                style={{
                  borderColor: snapshotTokens.border,
                  color: snapshotTokens.textPrimary,
                }}
                onClick={() => void runGenerate(false)}
              >
                {generating ? "Generating…" : "Merge with open"}
              </button>
              <button
                type="button"
                disabled={generating}
                className="rounded-lg px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                style={{ background: snapshotTokens.blue }}
                onClick={() => void runGenerate(true)}
              >
                {generating
                  ? "Generating…"
                  : "Replace open positions"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {addOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/30"
            aria-label="Close add position"
            onClick={() => setAddOpen(false)}
          />
          <div
            className="relative z-10 w-full max-w-lg rounded-xl border bg-white p-5 shadow-xl"
            style={{ borderColor: snapshotTokens.border }}
          >
            <h3
              className="text-lg font-semibold"
              style={{ color: snapshotTokens.textPrimary }}
            >
              Add Position
            </h3>
            <p
              className="mt-1 text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              Select a market from this week&apos;s slate.
              Entry price and model fields populate automatically.
            </p>
            <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Market
            </label>
            <select
              className="mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm"
              style={{ borderColor: snapshotTokens.border }}
              value={selectedMarketId ?? ""}
              onChange={(event) =>
                setSelectedMarketId(event.target.value || null)
              }
            >
              <option value="">Select market…</option>
              {marketOptions.map((market) => (
                <option
                  key={market.market_id}
                  value={market.market_id}
                >
                  {market.event_label} · {market.selection} (
                  {market.market_type})
                </option>
              ))}
            </select>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <label
                  className="text-xs font-semibold uppercase tracking-[0.12em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Exposure ($)
                </label>
                <input
                  type="number"
                  min={1}
                  className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                  style={{ borderColor: snapshotTokens.border }}
                  value={addExposure}
                  onChange={(event) =>
                    setAddExposure(Number(event.target.value) || 0)
                  }
                />
              </div>
              <div>
                <label
                  className="text-xs font-semibold uppercase tracking-[0.12em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Notes
                </label>
                <input
                  type="text"
                  className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                  style={{ borderColor: snapshotTokens.border }}
                  value={addNotes}
                  onChange={(event) =>
                    setAddNotes(event.target.value)
                  }
                  placeholder="Optional"
                />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border px-3 py-2 text-sm"
                style={{ borderColor: snapshotTokens.border }}
                onClick={() => setAddOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-lg px-3 py-2 text-sm font-medium text-white"
                style={{ background: snapshotTokens.blue }}
                onClick={() => void addSelectedPosition()}
              >
                Add to Portfolio
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SummaryBar({
  analytics,
}: {
  analytics: BettingPortfolioAnalytics | null;
}) {
  const summary = analytics?.summary;
  const cells = [
    {
      label: "Open Positions",
      value: String(summary?.open_positions ?? 0),
    },
    {
      label: "Total Exposure",
      value: `$${Math.round(summary?.total_exposure ?? 0)}`,
    },
    {
      label: "Average Model Edge",
      value:
        summary?.average_model_edge != null
          ? `${summary.average_model_edge > 0 ? "+" : ""}${summary.average_model_edge.toFixed(1)}%`
          : "—",
    },
    {
      label: "Average Confidence",
      value: summary?.average_confidence ?? "—",
    },
    {
      label: "Games Represented",
      value: String(summary?.games_represented ?? 0),
    },
    {
      label: "Correlation",
      value: summary?.correlation ?? "—",
    },
  ];
  return (
    <section
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6"
    >
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

function HealthPanel({
  health,
}: {
  health: BettingPortfolioAnalytics["health"];
}) {
  if (!health.length) return null;
  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Portfolio Health
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Descriptive dimensions of the current portfolio — not
        universal quality rankings.
      </p>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {health.map((row) => (
          <li
            key={row.id}
            className="rounded-lg border px-3 py-2"
            style={{ borderColor: snapshotTokens.border }}
            title={row.detail || undefined}
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className="text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {row.label}
              </span>
              <span
                className="text-sm font-semibold"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {row.value}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AlertsPanel({
  alerts,
}: {
  alerts: BettingPortfolioAnalytics["alerts"];
}) {
  return (
    <section className="space-y-2">
      {alerts.map((alert) => (
        <div
          key={alert.signal_id + alert.title}
          className="rounded-[10px] border px-4 py-3"
          style={{
            borderColor: "#FDE68A",
            background: snapshotTokens.warningLight,
          }}
        >
          <p
            className="text-sm font-semibold"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {alert.title}
          </p>
          <p
            className="mt-1 text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {alert.body}
          </p>
        </div>
      ))}
    </section>
  );
}

function ModelVsMarketPanel({
  modelVsMarket,
}: {
  modelVsMarket?: BettingPortfolioAnalytics["model_vs_market"];
}) {
  if (!modelVsMarket) return null;
  const rows = [
    [
      "Market implied probability",
      modelVsMarket.average_market_probability != null
        ? `${modelVsMarket.average_market_probability}%`
        : "—",
    ],
    [
      "InsightPilot probability",
      modelVsMarket.average_model_probability != null
        ? `${modelVsMarket.average_model_probability}%`
        : "—",
    ],
    [
      "Average model difference",
      modelVsMarket.average_difference != null
        ? `${modelVsMarket.average_difference > 0 ? "+" : ""}${modelVsMarket.average_difference} pts`
        : "—",
    ],
  ];
  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Model vs Market
      </h3>
      <ul className="mt-3 space-y-2">
        {rows.map(([label, value]) => (
          <li
            key={label}
            className="flex items-center justify-between gap-2 text-sm"
          >
            <span style={{ color: snapshotTokens.textSecondary }}>
              {label}
            </span>
            <span
              className="font-semibold tabular-nums"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {value}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AssumptionsPanel({
  assumptions,
}: {
  assumptions: BettingPortfolioAnalytics["assumptions"];
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
        Portfolio Assumptions
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        What you are actually betting on across positions.
      </p>
      {assumptions.length === 0 ? (
        <p
          className="mt-3 text-sm"
          style={{ color: snapshotTokens.textMuted }}
        >
          Add positions to surface underlying assumptions.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {assumptions.map((row) => (
            <li
              key={row.assumption}
              className="flex items-start justify-between gap-3"
            >
              <span
                className="text-sm"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {row.assumption}
              </span>
              <span
                className="shrink-0 text-xs tabular-nums"
                style={{ color: snapshotTokens.textMuted }}
              >
                {row.positions} position
                {row.positions === 1 ? "" : "s"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ExposurePanel({
  tab,
  onTab,
  exposure,
}: {
  tab: ExposureTab;
  onTab: (tab: ExposureTab) => void;
  exposure?: BettingPortfolioAnalytics["exposure"];
}) {
  const tabs: Array<{ id: ExposureTab; label: string }> = [
    { id: "game", label: "Game" },
    { id: "team", label: "Team" },
    { id: "market", label: "Market" },
    { id: "sport", label: "Sport" },
  ];
  const rows = exposure?.[tab] ?? [];
  return (
    <section
      id="portfolio-exposure"
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3
          className="text-sm font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Exposure
        </h3>
        <div className="flex flex-wrap gap-1">
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onTab(item.id)}
              className="rounded-lg px-2.5 py-1 text-xs font-medium"
              style={
                tab === item.id
                  ? {
                      background: snapshotTokens.blue,
                      color: snapshotTokens.white,
                    }
                  : {
                      background: snapshotTokens.background,
                      color: snapshotTokens.textSecondary,
                    }
              }
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr
              className="text-xs uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              <th className="py-2 pr-3 font-semibold">
                {tab === "game"
                  ? "Game"
                  : tab === "team"
                    ? "Team"
                    : tab === "market"
                      ? "Market"
                      : "Sport"}
              </th>
              <th className="py-2 pr-3 font-semibold text-right">
                Positions
              </th>
              <th className="py-2 font-semibold text-right">
                Exposure
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={
                  row.event_id
                  || row.team
                  || row.market
                  || row.sport
                  || row.game
                }
                className="border-t"
                style={{ borderColor: snapshotTokens.divider }}
              >
                <td
                  className="py-2 pr-3 capitalize"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {row.game
                    || row.team
                    || row.market
                    || row.sport
                    || "—"}
                </td>
                <td
                  className="py-2 pr-3 text-right tabular-nums"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {row.positions}
                </td>
                <td
                  className="py-2 text-right tabular-nums"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {row.exposure_pct}%
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={3}
                  className="py-4 text-sm"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  No exposure yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CorrelationPanel({
  correlations,
}: {
  correlations: BettingPortfolioAnalytics["correlations"];
}) {
  const high = correlations.filter((row) => row.score >= 0.45);
  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Portfolio Correlation
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Highly correlated positions share similar game outcomes
        or underlying assumptions.
      </p>
      {high.length === 0 ? (
        <p
          className="mt-3 text-sm"
          style={{ color: snapshotTokens.textMuted }}
        >
          No material correlations yet.
        </p>
      ) : (
        <ul className="mt-3 space-y-3">
          {high.slice(0, 8).map((row) => (
            <li
              key={`${row.left_position_id}-${row.right_position_id}`}
              className="rounded-lg border px-3 py-2"
              style={{ borderColor: snapshotTokens.border }}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p
                  className="text-sm font-medium"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {row.left_selection}
                  <span
                    className="mx-1"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    ↔
                  </span>
                  {row.right_selection}
                </p>
                <span
                  className="text-xs font-semibold"
                  style={{ color: snapshotTokens.blue }}
                >
                  {row.label} ({row.score.toFixed(2)})
                </span>
              </div>
              <ul
                className="mt-1 list-disc pl-4 text-xs"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {row.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DistributionPanel({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: string | number }>;
}) {
  const max =
    Math.max(
      ...rows.map((row) =>
        typeof row.value === "number" ? row.value : 0
      ),
      1
    ) || 1;
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
      <ul className="mt-3 space-y-2">
        {rows.map((row) => (
          <li key={row.label}>
            <div className="flex items-center justify-between text-sm">
              <span style={{ color: snapshotTokens.textSecondary }}>
                {row.label}
              </span>
              <span
                className="tabular-nums"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {row.value}
              </span>
            </div>
            {typeof row.value === "number" ? (
              <div
                className="mt-1 h-1.5 overflow-hidden rounded-full"
                style={{ background: snapshotTokens.divider }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max(
                      4,
                      (row.value / max) * 100
                    )}%`,
                    background: snapshotTokens.blue,
                  }}
                />
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function MovementPanel({
  movements,
}: {
  movements: BettingPortfolioAnalytics["price_movements"];
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
        Market Movement
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Entry vs current price. Favorable movement does not
        guarantee a favorable result.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr
              className="text-xs uppercase tracking-[0.12em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              <th className="py-2 pr-3 font-semibold">Position</th>
              <th className="py-2 pr-3 font-semibold text-right">
                Entry
              </th>
              <th className="py-2 pr-3 font-semibold text-right">
                Current
              </th>
              <th className="py-2 font-semibold text-right">
                Movement
              </th>
            </tr>
          </thead>
          <tbody>
            {movements.map((row) => (
              <tr
                key={row.position_id}
                className="border-t"
                style={{ borderColor: snapshotTokens.divider }}
              >
                <td
                  className="py-2 pr-3"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {row.selection}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatAmerican(row.entry_price)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatAmerican(row.current_price)}
                </td>
                <td className="py-2 text-right tabular-nums">
                  {row.movement != null
                    ? `${row.movement > 0 ? "+" : ""}${row.movement}¢`
                    : "—"}
                </td>
              </tr>
            ))}
            {movements.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  className="py-4 text-sm"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  No price movement recorded yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
