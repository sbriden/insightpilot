"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, Sparkles, TrendingUp } from "lucide-react";

import GuidedMarketSlate from "@/components/betting/GuidedMarketSlate";
import {
  DailySlatePickCard,
  StakeDisplay,
  formatStake,
} from "@/components/betting/DailySlatePickCard";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import {
  DailyBettingRisk,
  DailyBettingSlateResult,
  DailyBettingSport,
  generateDailyBettingSlate,
  listDailyBettingSports,
} from "@/services/api";

type SlateMode = "auto" | "guided";

const RISK_OPTIONS: Array<{
  id: DailyBettingRisk;
  label: string;
  hint: string;
}> = [
  {
    id: "conservative",
    label: "Low",
    hint: "Concentrates units on favorites; shorter parlays",
  },
  {
    id: "balanced",
    label: "Medium",
    hint: "Mix of singles and 2–3 leg parlays",
  },
  {
    id: "aggressive",
    label: "High",
    hint: "Flatter stakes; more and longer parlays",
  },
];

const SPORT_OPTIONS: DailyBettingSport[] = [
  "NFL",
  "NCAAF",
  "NBA",
  "NHL",
  "MLB",
  "NCAAB",
];

function todayEtLabel(): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  }).format(new Date());
}

export default function DailyBetSlate() {
  const [mode, setMode] = useState<SlateMode>("auto");
  const [totalUnits, setTotalUnits] = useState(10);
  const [stakeDisplay, setStakeDisplay] =
    useState<StakeDisplay>("units");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxPicks, setMaxPicks] = useState<number | null>(null);
  const [risk, setRisk] = useState<DailyBettingRisk>("balanced");
  const [selectedSports, setSelectedSports] = useState<
    DailyBettingSport[]
  >([...SPORT_OPTIONS]);
  const [availableSports, setAvailableSports] = useState<
    Set<DailyBettingSport>
  >(() => new Set(SPORT_OPTIONS));
  const [availabilityReady, setAvailabilityReady] =
    useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] =
    useState<DailyBettingSlateResult | null>(null);

  const dateLabel = useMemo(() => todayEtLabel(), []);

  useEffect(() => {
    let cancelled = false;
    // Render controls immediately; refine sport toggles after the
    // lightweight availability response lands.
    (async () => {
      try {
        const availability = await listDailyBettingSports();
        if (cancelled) return;
        const available = new Set(
          (availability.available_sports || [])
            .map((sport) => String(sport).toUpperCase())
            .filter((sport): sport is DailyBettingSport =>
              (SPORT_OPTIONS as string[]).includes(sport)
            )
        );
        setAvailableSports(available);
        setSelectedSports((current) => {
          const next = current.filter((sport) =>
            available.has(sport)
          );
          if (next.length > 0) return next;
          return [...available];
        });
      } catch {
        if (!cancelled) {
          // Keep all sports enabled if availability lookup fails.
          setAvailableSports(new Set(SPORT_OPTIONS));
        }
      } finally {
        if (!cancelled) {
          setAvailabilityReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const singlesCount = useMemo(
    () =>
      result?.picks.filter((pick) => pick.kind === "single").length
      ?? 0,
    [result]
  );
  const parlaysCount = useMemo(
    () =>
      result?.picks.filter((pick) => pick.kind === "parlay").length
      ?? 0,
    [result]
  );
  const picksCount = result?.picks.length ?? 0;

  const totalPossibleWin = useMemo(() => {
    if (!result?.picks?.length) return null;
    let total = 0;
    for (const pick of result.picks) {
      if (
        pick.potential_profit != null
        && !Number.isNaN(pick.potential_profit)
      ) {
        total += Number(pick.potential_profit);
      }
    }
    return total;
  }, [result]);

  const possibleRoiPct = useMemo(() => {
    if (
      totalPossibleWin == null
      || !result?.allocated_units
      || result.allocated_units <= 0
    ) {
      return null;
    }
    return (totalPossibleWin / result.allocated_units) * 100;
  }, [result, totalPossibleWin]);

  function toggleSport(sport: DailyBettingSport) {
    if (!availableSports.has(sport)) return;
    setSelectedSports((current) => {
      if (current.includes(sport)) {
        if (current.length === 1) return current;
        return current.filter((item) => item !== sport);
      }
      return [...current, sport];
    });
  }

  async function handleGenerate() {
    const units = Math.max(1, Math.round(totalUnits));
    if (units !== totalUnits) {
      setTotalUnits(units);
    }
    const picksCap =
      maxPicks == null
        ? null
        : Math.max(1, Math.round(maxPicks));
    if (picksCap != null && picksCap !== maxPicks) {
      setMaxPicks(picksCap);
    }
    const sports = selectedSports.filter((sport) =>
      availableSports.has(sport)
    );
    if (sports.length === 0) {
      setError("No sports with games today are selected.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await generateDailyBettingSlate({
        total_units: units,
        max_picks: picksCap,
        risk,
        sports,
        seed: Date.now() % 1_000_000_000,
      });
      setResult(next);
    } catch (err) {
      setResult(null);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to generate daily slate."
      );
    } finally {
      setLoading(false);
    }
  }

  if (mode === "guided") {
    return (
      <div className="space-y-4">
        <ModeToggle mode={mode} onChange={setMode} />
        <GuidedMarketSlate />
      </div>
    );
  }

  return (
    <div className="space-y-4">
    <ModeToggle mode={mode} onChange={setMode} />
    <div className="grid w-full gap-5 lg:grid-cols-[minmax(280px,22rem)_minmax(0,1fr)] lg:items-start lg:gap-6">
      <div className="space-y-5 lg:sticky lg:top-4">
      <header>
        <p
          className="text-xs font-semibold uppercase tracking-[0.18em]"
          style={{ color: snapshotTokens.textMuted }}
        >
          Daily slate · {dateLabel}
        </p>
      </header>

      <section
        className="space-y-4 rounded-2xl border bg-white p-4 sm:p-5"
        style={{ borderColor: snapshotTokens.border }}
      >
        <div className="space-y-2">
          <p
            className="text-xs font-semibold uppercase tracking-[0.14em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            Sports
          </p>
          <div className="flex flex-wrap gap-2">
            {SPORT_OPTIONS.map((sport) => {
              const available = availableSports.has(sport);
              const selected =
                available && selectedSports.includes(sport);
              return (
                <button
                  key={sport}
                  type="button"
                  aria-pressed={selected}
                  disabled={availabilityReady && !available}
                  title={
                    !availabilityReady
                      ? sport
                      : available
                        ? sport
                        : `No ${sport} games today`
                  }
                  onClick={() => toggleSport(sport)}
                  className="rounded-full px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40"
                  style={
                    selected
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
                  {sport}
                </button>
              );
            })}
          </div>
          {availabilityReady && availableSports.size === 0 ? (
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              No sports have eligible games today.
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span
              className="text-xs font-semibold uppercase tracking-[0.14em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              {stakeDisplay === "dollars" ? "Total dollars" : "Total units"}
            </span>
            <div
              className="grid grid-cols-2 gap-1 rounded-lg p-0.5"
              style={{ background: snapshotTokens.background }}
              role="radiogroup"
              aria-label="Stake display"
            >
              {(
                [
                  { id: "units", label: "Units" },
                  { id: "dollars", label: "Dollars" },
                ] as const
              ).map((option) => {
                const selected = stakeDisplay === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setStakeDisplay(option.id)}
                    className="rounded-md px-2.5 py-1 text-xs font-semibold"
                    style={
                      selected
                        ? {
                            background: snapshotTokens.blue,
                            color: snapshotTokens.white,
                          }
                        : {
                            background: "transparent",
                            color: snapshotTokens.textSecondary,
                          }
                    }
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label={
                stakeDisplay === "dollars"
                  ? "Decrease dollars"
                  : "Decrease units"
              }
              className="h-11 w-11 shrink-0 rounded-xl text-lg font-semibold"
              style={{
                background: snapshotTokens.background,
                color: snapshotTokens.textPrimary,
              }}
              onClick={() =>
                setTotalUnits((value) => Math.max(1, value - 1))
              }
            >
              −
            </button>
            <div className="relative w-full">
              <span
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-lg font-semibold tabular-nums"
                style={{ color: snapshotTokens.textMuted }}
                aria-hidden
              >
                {stakeDisplay === "dollars" ? "$" : "\u00A4"}
              </span>
              <input
                type="number"
                min={1}
                step={1}
                inputMode="numeric"
                value={totalUnits}
                onChange={(event) =>
                  setTotalUnits(
                    Math.max(
                      0,
                      Math.round(Number(event.target.value) || 0)
                    )
                  )
                }
                className="h-11 w-full rounded-xl border py-0 pl-8 pr-3 text-center text-lg font-semibold tabular-nums"
                style={{
                  borderColor: snapshotTokens.border,
                  color: snapshotTokens.textPrimary,
                }}
              />
            </div>
            <button
              type="button"
              aria-label={
                stakeDisplay === "dollars"
                  ? "Increase dollars"
                  : "Increase units"
              }
              className="h-11 w-11 shrink-0 rounded-xl text-lg font-semibold"
              style={{
                background: snapshotTokens.background,
                color: snapshotTokens.textPrimary,
              }}
              onClick={() => setTotalUnits((value) => value + 1)}
            >
              +
            </button>
          </div>
        </div>

        <div className="space-y-3">
          <button
            type="button"
            aria-expanded={showAdvanced}
            className="flex w-full items-center justify-between gap-2 text-left text-sm font-medium"
            style={{ color: snapshotTokens.blue }}
            onClick={() => setShowAdvanced((open) => !open)}
          >
            <span>Advanced Settings</span>
            <span
              aria-hidden
              className="text-xs tabular-nums"
              style={{ color: snapshotTokens.textMuted }}
            >
              {showAdvanced ? "−" : "+"}
            </span>
          </button>

          {showAdvanced ? (
            <div className="space-y-4">
              <label className="block space-y-2">
                <span
                  className="text-xs font-semibold uppercase tracking-[0.14em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Max picks
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    aria-label="Decrease max picks"
                    className="h-11 w-11 shrink-0 rounded-xl text-lg font-semibold"
                    style={{
                      background: snapshotTokens.background,
                      color: snapshotTokens.textPrimary,
                    }}
                    onClick={() =>
                      setMaxPicks((value) => {
                        if (value == null || value <= 1) return null;
                        return value - 1;
                      })
                    }
                  >
                    −
                  </button>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    inputMode="numeric"
                    placeholder="No Maximum"
                    value={maxPicks ?? ""}
                    onChange={(event) => {
                      const raw = event.target.value.trim();
                      if (!raw) {
                        setMaxPicks(null);
                        return;
                      }
                      const next = Math.round(Number(raw));
                      setMaxPicks(
                        Number.isFinite(next) && next >= 1
                          ? next
                          : null
                      );
                    }}
                    className="h-11 w-full rounded-xl border px-3 text-center text-lg font-semibold tabular-nums placeholder:text-sm placeholder:font-medium"
                    style={{
                      borderColor: snapshotTokens.border,
                      color: snapshotTokens.textPrimary,
                    }}
                  />
                  <button
                    type="button"
                    aria-label="Increase max picks"
                    className="h-11 w-11 shrink-0 rounded-xl text-lg font-semibold"
                    style={{
                      background: snapshotTokens.background,
                      color: snapshotTokens.textPrimary,
                    }}
                    onClick={() =>
                      setMaxPicks((value) =>
                        value == null ? 1 : value + 1
                      )
                    }
                  >
                    +
                  </button>
                </div>
                <p
                  className="text-xs"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Caps singles + parlays in the card
                </p>
              </label>

              <div className="space-y-2">
                <p
                  className="text-xs font-semibold uppercase tracking-[0.14em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Risk
                </p>
                <div
                  className="grid grid-cols-3 gap-1 rounded-xl p-1"
                  style={{ background: snapshotTokens.background }}
                  role="radiogroup"
                  aria-label="Risk level"
                >
                  {RISK_OPTIONS.map((option) => {
                    const selected = risk === option.id;
                    return (
                      <button
                        key={option.id}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        onClick={() => setRisk(option.id)}
                        className="rounded-lg px-2 py-2.5 text-sm font-medium"
                        style={
                          selected
                            ? {
                                background: snapshotTokens.blue,
                                color: snapshotTokens.white,
                              }
                            : {
                                background: "transparent",
                                color: snapshotTokens.textSecondary,
                              }
                        }
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
                <p
                  className="text-xs"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {
                    RISK_OPTIONS.find((option) => option.id === risk)
                      ?.hint
                  }
                </p>
              </div>
            </div>
          ) : null}
        </div>

        <button
          type="button"
          disabled={
            loading
            || selectedSports.filter((sport) =>
              availableSports.has(sport)
            ).length === 0
          }
          onClick={() => void handleGenerate()}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-xl text-sm font-semibold disabled:opacity-60"
          style={{
            background: snapshotTokens.blue,
            color: snapshotTokens.white,
          }}
        >
          <Sparkles className="h-4 w-4 shrink-0" aria-hidden />
          {loading
            ? "Generating…"
            : result
              ? "Regenerate slate"
              : "Generate slate"}
        </button>
      </section>
      </div>

      <div className="min-w-0 space-y-3">
      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {!result && !loading && !error ? (
        <div
          className="rounded-2xl border border-dashed px-4 py-10 text-center text-sm lg:flex lg:min-h-[16rem] lg:items-center lg:justify-center"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textMuted,
          }}
        >
          Pick sports, set units and risk, then generate
          today&apos;s card.
        </div>
      ) : null}

      {result ? (
        <section className="space-y-3">
          <div
            className="flex items-center gap-3 rounded-2xl border border-l-4 px-4 py-3 sm:gap-4"
            style={{
              borderColor: snapshotTokens.border,
              borderLeftColor: snapshotTokens.blue,
              background: snapshotTokens.background,
            }}
          >
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
              style={{
                background: snapshotTokens.blueLight,
                color: snapshotTokens.blue,
              }}
            >
              <BarChart3 className="h-5 w-5" aria-hidden />
            </div>

            <div className="min-w-0 flex-1 text-left">
              <p
                className="text-sm font-semibold tracking-tight"
                style={{ color: snapshotTokens.textPrimary }}
              >
                Today&apos;s Slate
              </p>
              <p
                className="mt-0.5 text-xs"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {picksCount} {picksCount === 1 ? "pick" : "picks"}
                {" · "}
                {parlaysCount}{" "}
                {parlaysCount === 1 ? "parlay" : "parlays"}
                {" · "}
                {singlesCount}{" "}
                {singlesCount === 1 ? "single" : "singles"}
              </p>
            </div>

            {totalPossibleWin != null ? (
              <>
                <div
                  className="hidden h-10 w-px shrink-0 sm:block"
                  style={{ background: snapshotTokens.border }}
                  aria-hidden
                />
                <div className="flex shrink-0 items-center gap-2 text-right">
                  <div>
                    <p
                      className="text-[11px] font-semibold uppercase tracking-[0.14em]"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      Max ROI
                    </p>
                    <p
                      className="mt-0.5 text-xl font-semibold tabular-nums tracking-tight"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {stakeDisplay === "dollars"
                        ? formatStake(totalPossibleWin, "dollars", {
                            signed: true,
                          })
                        : `${totalPossibleWin >= 0 ? "+" : ""}${Math.round(totalPossibleWin)}u`}
                    </p>
                    <p
                      className="text-xs tabular-nums"
                      style={{ color: snapshotTokens.textSecondary }}
                    >
                      {possibleRoiPct == null
                        ? "—"
                        : `${possibleRoiPct >= 0 ? "+" : ""}${Math.round(possibleRoiPct)}%`}
                    </p>
                  </div>
                  <TrendingUp
                    className="h-5 w-5 shrink-0"
                    style={{ color: snapshotTokens.blue }}
                    aria-hidden
                  />
                </div>
              </>
            ) : null}
          </div>

          <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
            {result.picks.map((pick, index) => (
              <DailySlatePickCard
                key={`${pick.kind}-${pick.event_id ?? "x"}-${index}`}
                pick={pick}
                stakeDisplay={stakeDisplay}
              />
            ))}
          </div>

          {result.meta?.probability_note ? (
            <p
              className="text-xs leading-relaxed"
              style={{ color: snapshotTokens.textMuted }}
            >
              {result.meta.probability_note}
            </p>
          ) : null}
          {result.meta?.parlay_probability_note ? (
            <p
              className="text-xs leading-relaxed"
              style={{ color: snapshotTokens.textMuted }}
            >
              {result.meta.parlay_probability_note}
            </p>
          ) : null}
        </section>
      ) : null}
      </div>
    </div>
    </div>
  );
}

function ModeToggle({
  mode,
  onChange,
}: {
  mode: SlateMode;
  onChange: (mode: SlateMode) => void;
}) {
  return (
    <div
      className="grid grid-cols-2 gap-1 rounded-xl p-1 sm:max-w-md"
      style={{ background: snapshotTokens.background }}
      role="radiogroup"
      aria-label="Slate mode"
    >
      {(
        [
          { id: "auto", label: "Auto" },
          { id: "guided", label: "Guided Market Slate" },
        ] as const
      ).map((option) => {
        const selected = mode === option.id;
        return (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.id)}
            className="rounded-lg px-3 py-2.5 text-sm font-semibold"
            style={
              selected
                ? {
                    background: snapshotTokens.blue,
                    color: snapshotTokens.white,
                  }
                : {
                    background: "transparent",
                    color: snapshotTokens.textSecondary,
                  }
            }
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

