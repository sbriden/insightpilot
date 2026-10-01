"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import MarketDetailDrawer from "@/components/betting/MarketDetailDrawer";
import BettingGameCard from "@/components/betting/BettingGameCard";
import MarketOpportunityTable from "@/components/betting/MarketOpportunityTable";
import ModelVsMarket from "@/components/betting/ModelVsMarket";
import BettingPortfolio from "@/components/betting/portfolio/BettingPortfolio";
import BettingResults from "@/components/betting/portfolio/BettingResults";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import {
  BettingEvent,
  BettingMarket,
  BettingSlate,
  getBettingSlate,
  listBettingWeeks,
  refreshNflverseData,
} from "@/services/api";

type WorkspaceTab =
  | "overview"
  | "games"
  | "markets"
  | "portfolio"
  | "results";

type MarketFilter =
  | "all"
  | "spread"
  | "total"
  | "moneyline";

type EdgeFilter = "all" | "positive" | "neutral" | "negative";

type ConfidenceFilter = "all" | "High" | "Moderate" | "Low";

const TABS: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "games", label: "Games" },
  { id: "markets", label: "Markets" },
  { id: "portfolio", label: "Portfolio" },
  { id: "results", label: "Results" },
];

export default function SportsBettingAnalyzer({
  initialTab = "overview",
  hideTabBar = false,
}: {
  initialTab?: WorkspaceTab;
  hideTabBar?: boolean;
} = {}) {
  const [weeks, setWeeks] = useState<number[]>([]);
  const [season, setSeason] = useState<number | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const [slate, setSlate] = useState<BettingSlate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<WorkspaceTab>(initialTab);
  const [marketFilter, setMarketFilter] =
    useState<MarketFilter>("all");
  const [edgeFilter, setEdgeFilter] =
    useState<EdgeFilter>("all");
  const [confidenceFilter, setConfidenceFilter] =
    useState<ConfidenceFilter>("all");
  const [selectedMarket, setSelectedMarket] =
    useState<BettingMarket | null>(null);
  const [selectedEvent, setSelectedEvent] =
    useState<BettingEvent | null>(null);
  const [refreshLoading, setRefreshLoading] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(
    null
  );
  const [refreshStatus, setRefreshStatus] = useState<string | null>(
    null
  );
  const [slateReloadKey, setSlateReloadKey] = useState(0);
  const [pendingPortfolioMarket, setPendingPortfolioMarket] =
    useState<BettingMarket | null>(null);
  const [portfolioImpact, setPortfolioImpact] = useState<
    string | null
  >(null);
  const loadedSlateKey = useRef<string | null>(null);

  useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);

  async function loadWeeks() {
    const result = await listBettingWeeks();
    setSeason(result.season);
    setWeeks(result.weeks || []);
    setWeek((current) => {
      if (
        current != null
        && (result.weeks || []).includes(current)
      ) {
        return current;
      }
      return (
        result.current_week
        ?? result.weeks?.[result.weeks.length - 1]
        ?? null
      );
    });
    return result;
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [weekResult, slateResult] = await Promise.all([
          listBettingWeeks(),
          getBettingSlate(),
        ]);
        if (cancelled) return;
        setSeason(weekResult.season);
        setWeeks(weekResult.weeks || []);
        const nextWeek =
          weekResult.current_week
          ?? weekResult.weeks?.[weekResult.weeks.length - 1]
          ?? null;
        setWeek(nextWeek);
        if (
          nextWeek != null
          && slateResult.season === weekResult.season
          && slateResult.week === nextWeek
        ) {
          loadedSlateKey.current = `${weekResult.season}:${nextWeek}:0`;
          setSlate(slateResult);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load betting weeks."
          );
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (week == null || season == null) return;
    const key = `${season}:${week}:${slateReloadKey}`;
    if (loadedSlateKey.current === key) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const result = await getBettingSlate({
          season,
          week,
        });
        if (cancelled) return;
        loadedSlateKey.current = key;
        setSlate(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load betting slate."
          );
          setSlate(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [season, week, slateReloadKey]);

  useEffect(() => {
    function onFantasyRefresh() {
      setSlateReloadKey((value) => value + 1);
    }
    window.addEventListener(
      "insightpilot:fantasy-data-refreshed",
      onFantasyRefresh
    );
    return () => {
      window.removeEventListener(
        "insightpilot:fantasy-data-refreshed",
        onFantasyRefresh
      );
    };
  }, []);

  async function handleRefresh(
    mode: "incremental" | "reprocess"
  ) {
    try {
      setRefreshLoading(true);
      setError(null);
      setRefreshMessage(null);
      setRefreshStatus(null);
      const result = await refreshNflverseData(mode);
      const message =
        result.message
        ?? result.validation?.message
        ?? "Betting source data refreshed.";
      setRefreshMessage(message);
      setRefreshStatus(
        result.status
        ?? result.validation?.status
        ?? "succeeded"
      );
      await loadWeeks();
      setSlateReloadKey((value) => value + 1);
    } catch (refreshError) {
      setRefreshMessage(null);
      setRefreshStatus(null);
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Unable to refresh betting data."
      );
    } finally {
      setRefreshLoading(false);
    }
  }

  const filteredMarkets = useMemo(() => {
    const rows = slate?.markets ?? [];
    return rows.filter((market) => {
      if (
        marketFilter !== "all"
        && market.market_type !== marketFilter
      ) {
        return false;
      }
      const edge = market.edge ?? 0;
      if (edgeFilter === "positive" && edge <= 0.5) return false;
      if (edgeFilter === "negative" && edge >= -0.5) return false;
      if (
        edgeFilter === "neutral"
        && Math.abs(edge) > 0.5
      ) {
        return false;
      }
      if (
        confidenceFilter !== "all"
        && market.confidence !== confidenceFilter
      ) {
        return false;
      }
      return true;
    });
  }, [slate, marketFilter, edgeFilter, confidenceFilter]);

  const topOpportunities = useMemo(
    () => filteredMarkets.slice(0, 8),
    [filteredMarkets]
  );

  function openMarket(market: BettingMarket) {
    setSelectedMarket(market);
    const event = slate?.events.find(
      (item) => item.event_id === market.event_id
    );
    setSelectedEvent(event ?? null);
  }

  function openEvent(event: BettingEvent) {
    setSelectedEvent(event);
    const market = (slate?.markets ?? []).find(
      (item) => item.event_id === event.event_id
    );
    setSelectedMarket(market ?? null);
  }

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p
              className="text-xs font-semibold uppercase tracking-[0.2em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Sports Betting
            </p>
            <h2
              className="mt-1 text-2xl font-semibold tracking-tight"
              style={{ color: snapshotTokens.textPrimary }}
            >
              NFL Market Analysis
            </h2>
            <p
              className="mt-1 max-w-2xl text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              Compare what the market is pricing with what
              InsightPilot expects — and where those differ.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              className="rounded-lg border bg-white px-3 py-2 text-sm"
              style={{ borderColor: snapshotTokens.border }}
              value="NFL"
              disabled
              aria-label="Sport"
            >
              <option value="NFL">NFL</option>
            </select>
            <select
              className="rounded-lg border bg-white px-3 py-2 text-sm"
              style={{ borderColor: snapshotTokens.border }}
              value={week ?? ""}
              onChange={(event) =>
                setWeek(
                  event.target.value
                    ? Number(event.target.value)
                    : null
                )
              }
              aria-label="Week"
            >
              {weeks.map((value) => (
                <option key={value} value={value}>
                  Week {value}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={refreshLoading}
              onClick={() => void handleRefresh("incremental")}
              className="rounded-lg border bg-white px-3 py-2 text-sm font-medium disabled:opacity-50"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textPrimary,
              }}
            >
              {refreshLoading ? "Refreshing…" : "Refresh data"}
            </button>
            <button
              type="button"
              disabled={refreshLoading}
              onClick={() => void handleRefresh("reprocess")}
              className="rounded-lg border bg-white px-3 py-2 text-sm font-medium disabled:opacity-50"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textSecondary,
              }}
            >
              Reprocess derived
            </button>
          </div>
        </div>

        {refreshMessage ? (
          <div
            className={[
              "rounded-xl border px-4 py-3 text-sm",
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
        ) : null}

        {!hideTabBar ? (
        <div
          className="flex gap-2 overflow-x-auto pb-1"
          role="tablist"
          aria-label="Sports betting workspace"
        >
          {TABS.map((item) => {
            const selected = item.id === tab;
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setTab(item.id)}
                className="shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                style={
                  selected
                    ? {
                        background: snapshotTokens.blue,
                        color: snapshotTokens.white,
                      }
                    : {
                        background: snapshotTokens.white,
                        color: snapshotTokens.textSecondary,
                        border: `1px solid ${snapshotTokens.border}`,
                      }
                }
              >
                {item.label}
              </button>
            );
          })}
        </div>
        ) : null}
      </header>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div
          className="rounded-xl border bg-white px-5 py-10 text-sm"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textMuted,
          }}
        >
          Loading NFL betting slate…
        </div>
      ) : null}

      {!loading && slate ? (
        <>
          {(tab === "overview" || tab === "games" || tab === "markets") && (
            <SlateSummaryBar slate={slate} />
          )}

          {tab === "overview" && (
            <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(280px,1fr)]">
              <div className="space-y-4">
                <SectionTitle
                  title="Market Opportunities"
                  subtitle="Sorted by absolute model / market difference."
                />
                <MarketOpportunityTable
                  markets={topOpportunities}
                  onSelect={openMarket}
                />
              </div>
              <aside className="space-y-4">
                <SectionTitle
                  title="Today's Model Signals"
                  subtitle="Structured differences between model and market."
                />
                <SignalsList signals={slate.signals} />
                {topOpportunities[0] ? (
                  <div
                    className="rounded-xl border bg-white p-4"
                    style={{ borderColor: snapshotTokens.border }}
                  >
                    <p
                      className="text-xs font-semibold uppercase tracking-[0.16em]"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      Featured Model vs Market
                    </p>
                    <p
                      className="mt-2 text-sm font-medium"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {topOpportunities[0].event_label} ·{" "}
                      {topOpportunities[0].selection}
                    </p>
                    <div className="mt-3">
                      <ModelVsMarket market={topOpportunities[0]} />
                    </div>
                  </div>
                ) : null}
              </aside>
            </div>
          )}

          {tab === "games" && (
            <div className="space-y-4">
              <SectionTitle
                title="Games"
                subtitle="Projected scores versus market totals and spreads."
              />
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {[...(slate.events ?? [])]
                  .sort((a, b) =>
                    String(a.start_time || "9999").localeCompare(
                      String(b.start_time || "9999")
                    )
                  )
                  .map((event) => (
                  <BettingGameCard
                    key={event.event_id}
                    event={event}
                    markets={(slate.markets ?? []).filter(
                      (market) => market.event_id === event.event_id
                    )}
                    onOpen={() => openEvent(event)}
                    onSelectMarket={openMarket}
                  />
                ))}
              </div>
            </div>
          )}

          {tab === "markets" && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <FilterSelect
                  label="Market"
                  value={marketFilter}
                  onChange={(value) =>
                    setMarketFilter(value as MarketFilter)
                  }
                  options={[
                    ["all", "All"],
                    ["spread", "Spread"],
                    ["total", "Total"],
                    ["moneyline", "Moneyline"],
                  ]}
                />
                <FilterSelect
                  label="Edge"
                  value={edgeFilter}
                  onChange={(value) =>
                    setEdgeFilter(value as EdgeFilter)
                  }
                  options={[
                    ["all", "All"],
                    ["positive", "Positive"],
                    ["neutral", "Neutral"],
                    ["negative", "Negative"],
                  ]}
                />
                <FilterSelect
                  label="Confidence"
                  value={confidenceFilter}
                  onChange={(value) =>
                    setConfidenceFilter(value as ConfidenceFilter)
                  }
                  options={[
                    ["all", "All"],
                    ["High", "High"],
                    ["Moderate", "Moderate"],
                    ["Low", "Low"],
                  ]}
                />
              </div>
              <MarketOpportunityTable
                markets={filteredMarkets}
                onSelect={openMarket}
              />
            </div>
          )}

          {tab === "portfolio" && (
            <BettingPortfolio
              slate={slate}
              season={season}
              week={week}
              pendingMarket={pendingPortfolioMarket}
              onPendingMarketConsumed={() =>
                setPendingPortfolioMarket(null)
              }
              onOpenMarket={(market, position) => {
                openMarket(market);
                if (position) {
                  setPortfolioImpact(
                    position.assumption_tags?.length
                      ? `Assumptions: ${position.assumption_tags
                          .slice(0, 2)
                          .join("; ")}.`
                      : null
                  );
                } else {
                  setPortfolioImpact(null);
                }
              }}
            />
          )}

          {tab === "results" && (
            <BettingResults
              slate={slate}
              season={season}
              week={week}
            />
          )}

          {slate.source_note ? (
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              {slate.source_note}
            </p>
          ) : null}
        </>
      ) : null}

      <MarketDetailDrawer
        open={Boolean(selectedMarket)}
        market={selectedMarket}
        event={selectedEvent}
        portfolioImpact={portfolioImpact}
        onAddToPortfolio={(market) => {
          setPendingPortfolioMarket(market);
          setTab("portfolio");
          setSelectedMarket(null);
          setSelectedEvent(null);
          setPortfolioImpact(null);
        }}
        onClose={() => {
          setSelectedMarket(null);
          setSelectedEvent(null);
          setPortfolioImpact(null);
        }}
      />
    </div>
  );
}

function SlateSummaryBar({ slate }: { slate: BettingSlate }) {
  const items = [
    { label: "Games", value: String(slate.game_count) },
    { label: "Markets", value: String(slate.market_count) },
    {
      label: "Model Coverage",
      value: `${Math.round(slate.model_coverage_pct)}%`,
    },
    {
      label: "Markets With Edge",
      value: String(slate.markets_with_edge),
    },
    {
      label: "Strong Bets",
      value: String(slate.markets_strong_bet ?? 0),
    },
    {
      label: "Leans",
      value: String(slate.markets_lean ?? 0),
    },
    {
      label: "No Bet / Pass",
      value: String(slate.markets_no_bet ?? 0),
    },
    {
      label: "Avg Confidence",
      value: slate.average_confidence || "—",
    },
  ];
  return (
    <div
      className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-8"
      style={{ borderColor: snapshotTokens.border }}
    >
      {items.map((item) => (
        <div key={item.label}>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            {item.label}
          </p>
          <p
            className="mt-1 text-xl font-semibold"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {item.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function SectionTitle({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div>
      <h3
        className="text-lg font-semibold"
        style={{ color: snapshotTokens.textPrimary }}
      >
        {title}
      </h3>
      <p
        className="text-sm"
        style={{ color: snapshotTokens.textSecondary }}
      >
        {subtitle}
      </p>
    </div>
  );
}

function SignalsList({
  signals,
}: {
  signals: BettingSlate["signals"];
}) {
  if (!signals.length) {
    return (
      <div
        className="rounded-xl border bg-white p-4 text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textMuted,
        }}
      >
        No material model/market signals for this slate.
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {signals.map((signal) => (
        <div
          key={signal.signal_id}
          className="rounded-xl border bg-white p-3"
          style={{ borderColor: snapshotTokens.border }}
        >
          <div className="flex items-center justify-between gap-2">
            <p
              className="text-sm font-medium"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {signal.label}
            </p>
            {signal.confidence ? (
              <span
                className="text-xs font-medium"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {signal.confidence}
              </span>
            ) : null}
          </div>
          {signal.event_label ? (
            <p
              className="mt-0.5 text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              {signal.event_label}
            </p>
          ) : null}
          {signal.explanation ? (
            <p
              className="mt-2 text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {signal.explanation}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<[string, string]>;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span style={{ color: snapshotTokens.textMuted }}>
        {label}
      </span>
      <select
        className="rounded-lg border bg-white px-3 py-2"
        style={{ borderColor: snapshotTokens.border }}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

function PlaceholderPanel({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div
      className="rounded-xl border border-dashed bg-white px-5 py-10"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-lg font-semibold"
        style={{ color: snapshotTokens.textPrimary }}
      >
        {title}
      </h3>
      <p
        className="mt-2 max-w-2xl text-sm"
        style={{ color: snapshotTokens.textSecondary }}
      >
        {body}
      </p>
    </div>
  );
}
