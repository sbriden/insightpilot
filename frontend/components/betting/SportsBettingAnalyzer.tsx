"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { useShowAnalysisTitle } from "@/components/analysis/AnalysisFormatContext";
import MarketDetailDrawer from "@/components/betting/MarketDetailDrawer";
import BettingGameCard from "@/components/betting/BettingGameCard";
import MarketOpportunityTable from "@/components/betting/MarketOpportunityTable";
import ModelVsMarket from "@/components/betting/ModelVsMarket";
import DailyBetSlate from "@/components/betting/DailyBetSlate";
import BettingPortfolio from "@/components/betting/portfolio/BettingPortfolio";
import BettingResults from "@/components/betting/portfolio/BettingResults";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import {
  BettingEvent,
  BettingMarket,
  BettingSlate,
  BettingSport,
  getBettingSlate,
  listBettingWeeks,
} from "@/services/api";

type WorkspaceTab =
  | "daily"
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
  { id: "daily", label: "Daily" },
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
  const [sport, setSport] = useState<BettingSport>("NFL");
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

  useEffect(() => {
    let cancelled = false;
    loadedSlateKey.current = null;
    setSlate(null);
    setSeason(null);
    setWeek(null);
    setWeeks([]);
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const weekResult = await listBettingWeeks(undefined, sport);
        if (cancelled) return;
        if (
          String(weekResult.sport || "").toUpperCase() !== sport
        ) {
          setLoading(false);
          setError(
            `Betting API returned ${weekResult.sport || "unknown"} `
            + `instead of ${sport}. Restart the API server to load `
            + "the latest sport routing."
          );
          return;
        }
        setSeason(weekResult.season);
        setWeeks(weekResult.weeks || []);
        const nextWeek =
          weekResult.current_week
          ?? weekResult.weeks?.[weekResult.weeks.length - 1]
          ?? null;
        setWeek(nextWeek);
        if (nextWeek == null) {
          setLoading(false);
          setError("No betting weeks available for this season.");
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
  }, [sport]);

  useEffect(() => {
    if (week == null || season == null) return;
    const key = `${sport}:${season}:${week}:${slateReloadKey}`;
    if (loadedSlateKey.current === key) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const result = await getBettingSlate({
          season,
          week,
          sport,
        });
        if (cancelled) return;
        if (String(result.sport || "").toUpperCase() !== sport) {
          setSlate(null);
          setError(
            `Betting slate returned ${result.sport || "unknown"} `
            + `instead of ${sport}. Restart the API server to load `
            + "the latest sport routing."
          );
          return;
        }
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
  }, [sport, season, week, slateReloadKey]);

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

  const isDailyTab = tab === "daily";
  const showTitle = useShowAnalysisTitle();
  const showSportControls = !isDailyTab;
  const showHeaderChrome =
    showTitle || showSportControls || !hideTabBar;

  return (
    <div className="space-y-6">
      {showHeaderChrome ? (
      <header className="space-y-3">
        {showTitle || showSportControls ? (
        <div className="flex flex-wrap items-end justify-between gap-4">
          {showTitle ? (
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
              {isDailyTab
                ? "Daily Bet Slate"
                : sport === "CFB"
                  ? "CFB Market Analysis"
                  : "NFL Market Analysis"}
            </h2>
            <p
              className="mt-1 max-w-2xl text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {isDailyTab
                ? "Generate a same-day multi-sport card from units and risk."
                : "Compare what the market is pricing with what InsightPilot expects — and where those differ."}
            </p>
          </div>
          ) : (
            <div />
          )}
          {showSportControls ? (
            <div className="flex flex-wrap gap-2">
              <select
                className="rounded-lg border bg-white px-3 py-2 text-sm"
                style={{ borderColor: snapshotTokens.border }}
                value={sport}
                onChange={(event) =>
                  setSport(event.target.value as BettingSport)
                }
                aria-label="Sport"
              >
                <option value="NFL">NFL</option>
                <option value="CFB">CFB</option>
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
            </div>
          ) : null}
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
      ) : null}

      {isDailyTab ? <DailyBetSlate /> : null}

      {!isDailyTab && error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {!isDailyTab && loading ? (
        <div
          className="rounded-xl border bg-white px-5 py-10 text-sm"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textMuted,
          }}
        >
          {`Loading ${sport} betting slate…`}
        </div>
      ) : null}

      {!isDailyTab && !loading && slate ? (
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
                  sport={sport}
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
                    sport={sport}
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
                sport={sport}
                onSelect={openMarket}
              />
            </div>
          )}

          {tab === "portfolio" && (
            <BettingPortfolio
              slate={slate}
              season={season}
              week={week}
              sport={sport}
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
              sport={sport}
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
  const pickMix = useMemo(
    () => computePickMix(slate.markets ?? []),
    [slate.markets]
  );
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
      label: "Avg Confidence",
      value: slate.average_confidence || "—",
    },
  ];
  const charts: PickMixChartSpec[] = [
    {
      title: "Moneyline",
      subtitle: "Model winner vs market favorite",
      slices: [
        {
          key: "favorite",
          label: "Favorite",
          value: pickMix.moneyline.left,
          color: snapshotTokens.blue,
        },
        {
          key: "underdog",
          label: "Underdog",
          value: pickMix.moneyline.right,
          color: snapshotTokens.warning,
        },
      ],
    },
    {
      title: "Total",
      subtitle: "Over vs under",
      slices: [
        {
          key: "over",
          label: "Over",
          value: pickMix.total.left,
          color: snapshotTokens.success,
        },
        {
          key: "under",
          label: "Under",
          value: pickMix.total.right,
          color: snapshotTokens.navy,
        },
      ],
    },
    {
      title: "Spread",
      subtitle: "Getting vs giving points",
      slices: [
        {
          key: "getting",
          label: "Getting",
          value: pickMix.spread.left,
          color: snapshotTokens.blue,
        },
        {
          key: "giving",
          label: "Giving",
          value: pickMix.spread.right,
          color: snapshotTokens.navy,
        },
      ],
    },
  ];

  return (
    <div
      className="space-y-4 rounded-xl border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {items.map((item) => (
          <div key={item.label}>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              {item.label}
            </p>
            <p
              className="mt-1 text-xl font-semibold leading-tight"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {item.value}
            </p>
          </div>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {charts.map((chart) => (
          <PickMixDonut key={chart.title} chart={chart} />
        ))}
      </div>
      <p
        className="text-xs"
        style={{ color: snapshotTokens.textMuted }}
      >
        {pickMix.materialNote}.
      </p>
    </div>
  );
}

type PickMixSlice = {
  key: string;
  label: string;
  value: number;
  color: string;
};

type PickMixChartSpec = {
  title: string;
  subtitle: string;
  slices: PickMixSlice[];
};

type PickMixSplit = { left: number; right: number };

function PickMixDonut({ chart }: { chart: PickMixChartSpec }) {
  const total = chart.slices.reduce((sum, slice) => sum + slice.value, 0);
  const data =
    total > 0
      ? chart.slices.filter((slice) => slice.value > 0)
      : [{ key: "empty", label: "None", value: 1, color: snapshotTokens.border }];
  const primary = chart.slices[0];
  const primaryPct =
    total > 0 && primary
      ? Math.round((primary.value / total) * 100)
      : null;

  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[108px] w-[108px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius={32}
              outerRadius={48}
              paddingAngle={total > 0 ? 2 : 0}
              stroke="none"
            >
              {data.map((slice) => (
                <Cell key={slice.key} fill={slice.color} />
              ))}
            </Pie>
            {total > 0 ? (
              <Tooltip
                formatter={(value, name) => {
                  const count = typeof value === "number" ? value : 0;
                  const pct = Math.round((count / total) * 100);
                  return [`${pct}% (${count})`, String(name)];
                }}
              />
            ) : null}
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-sm font-semibold tabular-nums"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {primaryPct != null ? `${primaryPct}%` : "—"}
          </span>
          <span
            className="text-[10px] font-medium uppercase tracking-[0.08em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            {primary?.label ?? ""}
          </span>
        </div>
      </div>
      <div className="min-w-0">
        <p
          className="text-sm font-semibold"
          style={{ color: snapshotTokens.textPrimary }}
        >
          {chart.title}
        </p>
        <p
          className="text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          {chart.subtitle}
        </p>
        <ul className="mt-2 space-y-1">
          {chart.slices.map((slice) => {
            const pct =
              total > 0
                ? Math.round((slice.value / total) * 100)
                : 0;
            return (
              <li
                key={slice.key}
                className="flex items-center gap-2 text-xs"
                style={{ color: snapshotTokens.textSecondary }}
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: slice.color }}
                />
                <span className="truncate">
                  {slice.label} {total > 0 ? `${pct}%` : "—"}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function computePickMix(markets: BettingMarket[]): {
  moneyline: PickMixSplit;
  total: PickMixSplit;
  spread: PickMixSplit;
  materialNote: string;
} {
  let mlFav = 0;
  let mlDog = 0;
  let over = 0;
  let under = 0;
  let getting = 0;
  let giving = 0;

  for (const market of markets) {
    const type = String(market.market_type || "").toLowerCase();
    if (type === "moneyline") {
      const side = moneylineFavoriteSide(market);
      if (side === "favorite") mlFav += 1;
      else if (side === "underdog") mlDog += 1;
    } else if (type === "total") {
      const sel = String(market.selection || "").toLowerCase();
      if (sel.startsWith("over")) over += 1;
      else if (sel.startsWith("under")) under += 1;
    } else if (type === "spread") {
      const line = market.line;
      if (line == null || line === 0) continue;
      if (line > 0) getting += 1;
      else giving += 1;
    }
  }

  const sides = mlFav + mlDog + over + under + getting + giving;
  const materialNote =
    sides > 0
      ? "All model-sided markets on this slate"
      : "No priced markets";

  return {
    moneyline: { left: mlFav, right: mlDog },
    total: { left: over, right: under },
    spread: { left: getting, right: giving },
    materialNote,
  };
}

function moneylineFavoriteSide(
  market: BettingMarket
): "favorite" | "underdog" | null {
  if (market.price != null && market.price !== 0) {
    return market.price < 0 ? "favorite" : "underdog";
  }
  if (market.market_probability != null) {
    if (market.market_probability > 0.5) return "favorite";
    if (market.market_probability < 0.5) return "underdog";
  }
  return null;
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
