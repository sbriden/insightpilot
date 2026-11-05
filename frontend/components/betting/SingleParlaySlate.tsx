"use client";

import { ReactNode, useEffect, useMemo, useState } from "react";
import { Sparkles } from "lucide-react";

import {
  DailySlatePickCard,
  StakeDisplay,
} from "@/components/betting/DailySlatePickCard";
import { formatAmerican } from "@/components/betting/formatMarketValues";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import {
  DailyBettingSport,
  SingleParlayResult,
  generateSingleParlay,
  listDailyBettingSports,
} from "@/services/api";

const SPORT_OPTIONS: DailyBettingSport[] = [
  "NFL",
  "NCAAF",
  "NBA",
  "NHL",
  "MLB",
  "NCAAB",
];

const MIN_LEGS = 2;
const MAX_LEGS = 8;

function parseTargetOddsInput(raw: string): number | null {
  const text = raw.trim().replace(/,/g, "").replace(/\s/g, "");
  if (!text || text === "+" || text === "-") return null;
  const value = Number(text);
  if (!Number.isFinite(value) || Math.abs(value) < 100) return null;
  return value;
}

export default function SingleParlaySlate({
  dateLabel,
  modeSwitcher,
}: {
  dateLabel?: string;
  modeSwitcher?: ReactNode;
} = {}) {
  const [totalUnits, setTotalUnits] = useState(5);
  const [stakeDisplay, setStakeDisplay] =
    useState<StakeDisplay>("units");
  const [legCount, setLegCount] = useState(3);
  const [targetOddsInput, setTargetOddsInput] = useState("+250");
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
  const [result, setResult] = useState<SingleParlayResult | null>(
    null
  );

  const targetOdds = useMemo(
    () => parseTargetOddsInput(targetOddsInput),
    [targetOddsInput]
  );

  useEffect(() => {
    let cancelled = false;
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
          const next = current.filter((sport) => available.has(sport));
          if (next.length > 0) return next;
          return [...available];
        });
      } catch {
        if (!cancelled) {
          setAvailableSports(new Set(SPORT_OPTIONS));
        }
      } finally {
        if (!cancelled) setAvailabilityReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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
    if (units !== totalUnits) setTotalUnits(units);
    const legs = Math.min(
      MAX_LEGS,
      Math.max(MIN_LEGS, Math.round(legCount))
    );
    if (legs !== legCount) setLegCount(legs);
    if (targetOdds == null) {
      setError("Enter a valid American target (e.g. +250 or -110).");
      return;
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
      const next = await generateSingleParlay({
        units,
        leg_count: legs,
        target_odds: targetOdds,
        sports,
      });
      setResult(next);
    } catch (err) {
      setResult(null);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to generate single parlay."
      );
    } finally {
      setLoading(false);
    }
  }

  const pick = result?.picks?.[0] ?? null;

  return (
    <div className="grid w-full gap-5 lg:grid-cols-[minmax(280px,22rem)_minmax(0,1fr)] lg:items-stretch lg:gap-6">
      <div className="space-y-5 lg:sticky lg:top-4 lg:self-start">
        <header>
          <p
            className="text-xs font-semibold uppercase tracking-[0.18em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            Daily slate
            {dateLabel ? ` · ${dateLabel}` : ""}
          </p>
        </header>

        {modeSwitcher}

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
                    onClick={() => toggleSport(sport)}
                    className="rounded-full px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
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
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span
                className="text-xs font-semibold uppercase tracking-[0.14em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                {stakeDisplay === "dollars" ? "Stake dollars" : "Stake units"}
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

          <label className="block space-y-2">
            <span
              className="text-xs font-semibold uppercase tracking-[0.14em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Number of legs
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="h-11 w-11 shrink-0 rounded-xl text-lg font-semibold"
                style={{
                  background: snapshotTokens.background,
                  color: snapshotTokens.textPrimary,
                }}
                onClick={() =>
                  setLegCount((value) => Math.max(MIN_LEGS, value - 1))
                }
              >
                −
              </button>
              <input
                type="number"
                min={MIN_LEGS}
                max={MAX_LEGS}
                step={1}
                inputMode="numeric"
                value={legCount}
                onChange={(event) => {
                  const next = Math.round(Number(event.target.value));
                  if (!Number.isFinite(next)) return;
                  setLegCount(
                    Math.min(MAX_LEGS, Math.max(MIN_LEGS, next))
                  );
                }}
                className="h-11 w-full rounded-xl border px-3 text-center text-lg font-semibold tabular-nums"
                style={{
                  borderColor: snapshotTokens.border,
                  color: snapshotTokens.textPrimary,
                }}
              />
              <button
                type="button"
                className="h-11 w-11 shrink-0 rounded-xl text-lg font-semibold"
                style={{
                  background: snapshotTokens.background,
                  color: snapshotTokens.textPrimary,
                }}
                onClick={() =>
                  setLegCount((value) => Math.min(MAX_LEGS, value + 1))
                }
              >
                +
              </button>
            </div>
          </label>

          <label className="block space-y-2">
            <span
              className="text-xs font-semibold uppercase tracking-[0.14em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Target odds
            </span>
            <input
              type="text"
              inputMode="text"
              placeholder="+250"
              value={targetOddsInput}
              onChange={(event) =>
                setTargetOddsInput(event.target.value)
              }
              className="h-11 w-full rounded-xl border px-3 text-center text-lg font-semibold tabular-nums"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textPrimary,
              }}
            />
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              American price to aim for (e.g. +250, +400, -110).
            </p>
          </label>

          <button
            type="button"
            disabled={
              loading
              || targetOdds == null
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
                ? "Regenerate parlay"
                : "Generate parlay"}
          </button>
        </section>
      </div>

      <div className="flex min-w-0 flex-col space-y-3 lg:h-full">
        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}

        {!result && !loading && !error ? (
          <div
            className="flex flex-1 items-center justify-center rounded-2xl border border-dashed px-4 py-10 text-center text-sm"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textMuted,
            }}
          >
            Set stake, legs, and target odds, then generate a single
            parlay.
          </div>
        ) : null}

        {result && pick ? (
          <section className="space-y-3">
            <div
              className="rounded-2xl border border-l-4 px-4 py-3"
              style={{
                borderColor: snapshotTokens.border,
                borderLeftColor: snapshotTokens.blue,
                background: snapshotTokens.background,
              }}
            >
              <p
                className="text-sm font-semibold tracking-tight"
                style={{ color: snapshotTokens.textPrimary }}
              >
                Single Parlay
              </p>
              <p
                className="mt-0.5 text-xs"
                style={{ color: snapshotTokens.textSecondary }}
              >
                Target {formatAmerican(result.target_odds)} · got{" "}
                {formatAmerican(result.achieved_odds)} ·{" "}
                {result.leg_count ?? pick.legs?.length ?? "—"} legs
              </p>
            </div>
            <div className="max-w-xl">
              <DailySlatePickCard
                pick={pick}
                stakeDisplay={stakeDisplay}
              />
            </div>
            {result.meta?.probability_note ? (
              <p
                className="text-xs leading-relaxed"
                style={{ color: snapshotTokens.textMuted }}
              >
                {result.meta.probability_note}
              </p>
            ) : null}
          </section>
        ) : null}
      </div>
    </div>
  );
}
