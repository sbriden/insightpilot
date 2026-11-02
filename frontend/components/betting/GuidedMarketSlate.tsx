"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Check,
  ChevronLeft,
  RefreshCw,
  Replace,
  Sparkles,
  TrendingUp,
} from "lucide-react";

import {
  DailySlatePickCard,
  StakeDisplay,
  formatStake,
  formatWinPct,
} from "@/components/betting/DailySlatePickCard";
import { formatAmerican } from "@/components/betting/formatMarketValues";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import { TeamMatchupLabel } from "@/components/teams/TeamLogo";
import {
  DailyBettingPick,
  DailyBettingRisk,
  DailyBettingSport,
  GuidedSlateCandidate,
  GuidedSlateResponse,
  GuidedSlateSession,
  GuidedSlateStep,
  GuidedSlateTicket,
  backGuidedDailySlate,
  confirmGuidedDailySlate,
  listDailyBettingSports,
  listGuidedDailySlateCandidates,
  replaceGuidedDailySlatePick,
  reviewGuidedDailySlate,
  selectGuidedDailySlatePick,
  startGuidedDailySlate,
} from "@/services/api";

const STORAGE_KEY = "ip-guided-slate:v1";

const RISK_OPTIONS: Array<{
  id: DailyBettingRisk;
  label: string;
  hint: string;
}> = [
  {
    id: "conservative",
    label: "Low",
    hint: "Mostly favorites and near-even singles",
  },
  {
    id: "balanced",
    label: "Medium",
    hint: "Mix of singles and short parlays",
  },
  {
    id: "aggressive",
    label: "High",
    hint: "More parlays and underdogs when available",
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

function jointFairProbability(
  legs: GuidedSlateTicket["legs"]
): number | null {
  let product = 1;
  for (const leg of legs) {
    const fair = leg.selection?.fair_probability;
    if (fair == null || Number.isNaN(fair)) return null;
    product *= Number(fair);
  }
  return product;
}

const CANDIDATE_PAGE_SIZE = 6;

function sampleCandidates(
  pool: GuidedSlateCandidate[],
  count: number,
  seed: number
): GuidedSlateCandidate[] {
  if (pool.length <= count) return [...pool];
  // Mulberry32 — deterministic shuffle for a refresh seed.
  let t = seed >>> 0;
  const rand = () => {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
  const copy = [...pool];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1));
    const tmp = copy[i];
    copy[i] = copy[j];
    copy[j] = tmp;
  }
  return copy.slice(0, count);
}

function ticketToDailyPick(ticket: GuidedSlateTicket): DailyBettingPick {
  const isParlay = ticket.ticket_type === "parlay";
  const legs = ticket.legs || [];
  const first = legs[0]?.selection;
  const sports = Array.from(
    new Set(
      legs
        .map((leg) => String(leg.selection?.sport || "").toUpperCase())
        .filter(Boolean)
    )
  );
  const selectionLabel = isParlay
    ? legs
        .map((leg) => leg.selection?.selection)
        .filter(Boolean)
        .join(" + ")
    : first?.selection || undefined;

  return {
    kind: isParlay ? "parlay" : "single",
    sport: isParlay
      ? sports.length === 1
        ? sports[0]
        : "MULTI"
      : first?.sport || null,
    sports,
    event_id: first?.event_id || null,
    event_label: first?.event_label || null,
    market_key: first?.market_key || null,
    market_type: isParlay ? "parlay" : first?.market_type || null,
    selection: selectionLabel || null,
    line: first?.line ?? null,
    price: ticket.combined_odds ?? first?.price ?? null,
    offered_odds: ticket.combined_odds ?? first?.price ?? null,
    units: Number(ticket.stake || 0),
    fair_probability: isParlay
      ? jointFairProbability(legs)
      : first?.fair_probability ?? null,
    win_probability: isParlay
      ? jointFairProbability(legs)
      : first?.fair_probability ?? null,
    potential_profit: ticket.potential_profit ?? null,
    potential_payout: ticket.potential_payout ?? null,
    home_team: first?.home_team ?? null,
    away_team: first?.away_team ?? null,
    home_logo_url: first?.home_logo_url ?? null,
    away_logo_url: first?.away_logo_url ?? null,
    start_time: first?.start_time ?? null,
    slate_mode: "guided_market_slate",
    slate_mode_label: "Guided Market Slate",
    legs: isParlay
      ? legs.map((leg) => ({
          sport: leg.selection?.sport ?? null,
          event_id: leg.selection?.event_id ?? null,
          event_label: leg.selection?.event_label ?? null,
          market_type: leg.selection?.market_type ?? null,
          selection: leg.selection?.selection ?? null,
          line: leg.selection?.line ?? null,
          price: leg.selection?.price ?? null,
          home_team: leg.selection?.home_team ?? null,
          away_team: leg.selection?.away_team ?? null,
          home_logo_url: leg.selection?.home_logo_url ?? null,
          away_logo_url: leg.selection?.away_logo_url ?? null,
          win_probability: leg.selection?.fair_probability ?? null,
        }))
      : undefined,
  };
}

function loadStoredSession(): GuidedSlateSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as GuidedSlateSession;
    if (!parsed?.session_id) return null;
    return parsed;
  } catch {
    return null;
  }
}

function persistSession(session: GuidedSlateSession | null) {
  if (typeof window === "undefined") return;
  try {
    if (!session) {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Ignore quota / private mode failures.
  }
}

function applyResponse(
  response: GuidedSlateResponse,
  setters: {
    setSession: (s: GuidedSlateSession) => void;
    setStep: (s: GuidedSlateStep | null) => void;
    setCandidates: (c: GuidedSlateCandidate[]) => void;
  }
) {
  setters.setSession(response.session);
  setters.setStep(response.current_step ?? null);
  setters.setCandidates(response.candidates ?? []);
  persistSession(response.session);
}

export default function GuidedMarketSlate() {
  const [ticketCount, setTicketCount] = useState(6);
  const [totalExposure, setTotalExposure] = useState(30);
  const [stakeDisplay, setStakeDisplay] =
    useState<StakeDisplay>("units");
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
  const [session, setSession] = useState<GuidedSlateSession | null>(
    null
  );
  const [currentStep, setCurrentStep] =
    useState<GuidedSlateStep | null>(null);
  const [candidates, setCandidates] = useState<
    GuidedSlateCandidate[]
  >([]);
  const [candidateSampleSeed, setCandidateSampleSeed] = useState(
    () => Date.now() % 1_000_000_000
  );
  const [view, setView] = useState<"config" | "picking" | "review">(
    "config"
  );

  const displayedCandidates = useMemo(
    () =>
      sampleCandidates(
        candidates,
        CANDIDATE_PAGE_SIZE,
        candidateSampleSeed
      ),
    [candidates, candidateSampleSeed]
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

  useEffect(() => {
    const stored = loadStoredSession();
    if (!stored) return;
    let cancelled = false;
    setSession(stored);
    const incomplete = (stored.steps || []).some(
      (step) => step.status !== "complete"
    );
    (async () => {
      try {
        if (stored.confirmed || stored.status === "confirmed") {
          if (!cancelled) setView("review");
          return;
        }
        if (incomplete) {
          const idx = stored.current_step_index ?? 0;
          if (!cancelled) {
            setCurrentStep(stored.steps?.[idx] ?? null);
            setView("picking");
          }
          const response = await listGuidedDailySlateCandidates({
            session: stored,
          });
          if (cancelled) return;
          setCandidates(response.candidates ?? []);
          setCandidateSampleSeed(Date.now() % 1_000_000_000);
          return;
        }
        const reviewed = await reviewGuidedDailySlate({
          session: stored,
        });
        if (cancelled) return;
        applyResponse(reviewed, {
          setSession,
          setStep: setCurrentStep,
          setCandidates,
        });
        setView("review");
      } catch {
        if (!cancelled) {
          // Keep stored session; user can restart if candidates fail.
          setView(incomplete ? "picking" : "review");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setters = useMemo(
    () => ({
      setSession,
      setStep: (step: GuidedSlateStep | null) => {
        setCurrentStep(step);
        setCandidateSampleSeed(Date.now() % 1_000_000_000);
      },
      setCandidates: (next: GuidedSlateCandidate[]) => {
        setCandidates(next);
        setCandidateSampleSeed(Date.now() % 1_000_000_000);
      },
    }),
    []
  );

  const progress = useMemo(() => {
    const total = session?.summary?.total_steps ?? 0;
    const done = session?.summary?.completed_steps ?? 0;
    return { total, done };
  }, [session]);

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

  async function handleStart() {
    const bets = Math.max(1, Math.min(25, Math.round(ticketCount)));
    const exposure = Math.max(1, Math.round(totalExposure));
    setTicketCount(bets);
    setTotalExposure(exposure);
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
      const response = await startGuidedDailySlate({
        ticket_count: bets,
        total_exposure: exposure,
        risk,
        sports,
        seed: Date.now() % 1_000_000_000,
      });
      applyResponse(response, setters);
      setView(
        response.session.status === "ready_for_review"
          ? "review"
          : "picking"
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to start guided slate."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleSelect(candidateId: string) {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const response = await selectGuidedDailySlatePick({
        session,
        candidate_id: candidateId,
      });
      applyResponse(response, setters);
      if (
        response.session.status === "ready_for_review"
        || !response.current_step
      ) {
        const reviewed = await reviewGuidedDailySlate({
          session: response.session,
        });
        applyResponse(reviewed, setters);
        setView("review");
      } else {
        setView("picking");
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to lock that pick."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleBack() {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const response = await backGuidedDailySlate({ session });
      applyResponse(response, setters);
      setView("picking");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to go back."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleReplace(stepIndex: number) {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const response = await replaceGuidedDailySlatePick({
        session,
        step_index: stepIndex,
      });
      applyResponse(response, setters);
      setView("picking");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to reopen that pick."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const reviewed = await reviewGuidedDailySlate({ session });
      applyResponse(reviewed, setters);
      if ((reviewed.odds_alerts || []).length > 0) {
        setError(
          "Some odds moved since you locked picks. Replace those legs before confirming."
        );
        setView("review");
        return;
      }
      const confirmed = await confirmGuidedDailySlate({
        session: reviewed.session,
      });
      applyResponse(confirmed, setters);
      setView("review");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to confirm slate."
      );
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    persistSession(null);
    setSession(null);
    setCurrentStep(null);
    setCandidates([]);
    setView("config");
    setError(null);
  }

  const showingConfig = view === "config" && !session;

  return (
    <div className="grid w-full gap-5 lg:grid-cols-[minmax(280px,22rem)_minmax(0,1fr)] lg:items-start lg:gap-6">
      <div className="space-y-5 lg:sticky lg:top-4">
        <header>
          <p
            className="text-xs font-semibold uppercase tracking-[0.18em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            Guided Market Slate
          </p>
          <p
            className="mt-1 text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Step through odds-based requirements. No model edge
            ranking.
          </p>
        </header>

        {(showingConfig || view === "config") && !session ? (
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

            <label className="block space-y-2">
              <span
                className="text-xs font-semibold uppercase tracking-[0.14em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                Number of bets
              </span>
              <input
                type="number"
                min={1}
                max={25}
                value={ticketCount}
                onChange={(event) =>
                  setTicketCount(
                    Math.max(
                      1,
                      Math.min(
                        25,
                        Math.round(Number(event.target.value) || 1)
                      )
                    )
                  )
                }
                className="h-11 w-full rounded-xl border px-3 text-center text-lg font-semibold tabular-nums"
                style={{
                  borderColor: snapshotTokens.border,
                  color: snapshotTokens.textPrimary,
                }}
              />
            </label>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span
                  className="text-xs font-semibold uppercase tracking-[0.14em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {stakeDisplay === "dollars"
                    ? "Total dollars"
                    : "Total units"}
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
              <input
                type="number"
                min={1}
                value={totalExposure}
                onChange={(event) =>
                  setTotalExposure(
                    Math.max(
                      1,
                      Math.round(Number(event.target.value) || 1)
                    )
                  )
                }
                className="h-11 w-full rounded-xl border px-3 text-center text-lg font-semibold tabular-nums"
                style={{
                  borderColor: snapshotTokens.border,
                  color: snapshotTokens.textPrimary,
                }}
              />
            </div>

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
                {RISK_OPTIONS.find((option) => option.id === risk)?.hint}
              </p>
            </div>

            <button
              type="button"
              disabled={
                loading
                || selectedSports.filter((sport) =>
                  availableSports.has(sport)
                ).length === 0
              }
              onClick={() => void handleStart()}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-xl text-sm font-semibold disabled:opacity-60"
              style={{
                background: snapshotTokens.blue,
                color: snapshotTokens.white,
              }}
            >
              <Sparkles className="h-4 w-4" aria-hidden />
              {loading ? "Building…" : "Start guided slate"}
            </button>
          </section>
        ) : (
          <section
            className="space-y-3 rounded-2xl border bg-white p-4 sm:p-5"
            style={{ borderColor: snapshotTokens.border }}
          >
            <div className="flex items-center justify-between gap-2">
              <p
                className="text-sm font-semibold"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {session?.risk_label || "Guided"} ·{" "}
                {formatStake(
                  Number(session?.total_exposure || 0),
                  stakeDisplay
                )}
              </p>
              <button
                type="button"
                onClick={handleReset}
                className="text-xs font-semibold"
                style={{ color: snapshotTokens.blue }}
              >
                New slate
              </button>
            </div>
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              {progress.done} of {progress.total} picks locked
            </p>
            <div
              className="h-2 overflow-hidden rounded-full"
              style={{ background: snapshotTokens.background }}
            >
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${
                    progress.total
                      ? (100 * progress.done) / progress.total
                      : 0
                  }%`,
                  background: snapshotTokens.blue,
                }}
              />
            </div>
            {session?.adjustment_message ? (
              <p
                className="text-xs"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {session.adjustment_message}
              </p>
            ) : null}
            {view === "picking" ? (
              <button
                type="button"
                disabled={loading || progress.done === 0}
                onClick={() => void handleBack()}
                className="flex h-10 w-full items-center justify-center gap-1 rounded-xl text-sm font-semibold disabled:opacity-50"
                style={{
                  background: snapshotTokens.background,
                  color: snapshotTokens.textPrimary,
                }}
              >
                <ChevronLeft className="h-4 w-4" aria-hidden />
                Back
              </button>
            ) : null}
            {view === "review" && !session?.confirmed ? (
              <button
                type="button"
                disabled={loading}
                onClick={() => void handleConfirm()}
                className="flex h-11 w-full items-center justify-center gap-2 rounded-xl text-sm font-semibold disabled:opacity-60"
                style={{
                  background: snapshotTokens.blue,
                  color: snapshotTokens.white,
                }}
              >
                <Check className="h-4 w-4" aria-hidden />
                Confirm slate
              </button>
            ) : null}
          </section>
        )}
      </div>

      <div className="min-w-0 space-y-3">
        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}

        {!session && !loading && !error ? (
          <div
            className="rounded-2xl border border-dashed px-4 py-10 text-center text-sm"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textMuted,
            }}
          >
            Choose bet count, exposure, and risk, then start the
            guided walkthrough.
          </div>
        ) : null}

        {view === "picking" && currentStep ? (
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
                className="text-xs font-semibold uppercase tracking-[0.14em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                Bet {currentStep.ticket_index} of{" "}
                {session?.ticket_count || "—"} ·{" "}
                {currentStep.ticket_type === "parlay"
                  ? `Parlay · leg ${currentStep.leg_index} of ${currentStep.leg_count}`
                  : "Single"}
              </p>
              <p
                className="mt-1 text-base font-semibold"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {currentStep.prompt}
              </p>
              <p
                className="mt-1 text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                Stake{" "}
                {formatStake(Number(currentStep.stake || 0), stakeDisplay)}
              </p>
            </div>

            {candidates.length === 0 ? (
              <div
                className="rounded-xl border px-4 py-6 text-sm"
                style={{
                  borderColor: snapshotTokens.border,
                  color: snapshotTokens.textMuted,
                }}
              >
                No eligible markets in this odds range with remaining
                diversity. Go back or start a new slate.
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p
                    className="text-sm font-medium"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    Showing {displayedCandidates.length} of{" "}
                    {candidates.length} available
                  </p>
                  {candidates.length > CANDIDATE_PAGE_SIZE ? (
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() =>
                        setCandidateSampleSeed(
                          (Date.now() % 1_000_000_000)
                            + Math.floor(Math.random() * 10_000)
                        )
                      }
                      className="inline-flex h-9 items-center gap-1.5 rounded-xl px-3 text-xs font-semibold disabled:opacity-60"
                      style={{
                        background: snapshotTokens.background,
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                      Refresh picks
                    </button>
                  ) : null}
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {displayedCandidates.map((candidate) => (
                    <button
                      key={candidate.candidate_id}
                      type="button"
                      disabled={loading}
                      onClick={() =>
                        void handleSelect(candidate.candidate_id)
                      }
                      className="flex h-full w-full flex-col gap-3 rounded-2xl border bg-white px-4 py-3 text-left transition hover:border-blue-300 disabled:opacity-60"
                      style={{ borderColor: snapshotTokens.border }}
                    >
                      <div className="flex min-w-0 flex-1 items-start justify-between gap-3">
                        <div className="min-w-0 space-y-1">
                          <p
                            className="text-xs font-semibold uppercase tracking-[0.12em]"
                            style={{ color: snapshotTokens.textMuted }}
                          >
                            {candidate.sport} ·{" "}
                            {String(
                              candidate.market_type || ""
                            ).replace(/_/g, " ")}
                          </p>
                          <TeamMatchupLabel
                            label={candidate.event_label}
                            away={candidate.away_team}
                            home={candidate.home_team}
                            awayLogoUrl={candidate.away_logo_url}
                            homeLogoUrl={candidate.home_logo_url}
                            sport={String(candidate.sport || "NBA")}
                            size={18}
                          />
                          <p
                            className="text-sm font-semibold"
                            style={{
                              color: snapshotTokens.textPrimary,
                            }}
                          >
                            {candidate.selection}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          <p
                            className="text-lg font-semibold tabular-nums"
                            style={{
                              color: snapshotTokens.textPrimary,
                            }}
                          >
                            {formatAmerican(candidate.price)}
                          </p>
                          <p
                            className="text-xs"
                            style={{ color: snapshotTokens.textMuted }}
                          >
                            {formatWinPct(candidate.fair_probability)}{" "}
                            market
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              Market-implied probabilities only. Parlay joint
              probability assumes independence.
            </p>
          </section>
        ) : null}

        {view === "review" && session?.confirmed ? (
          <ConfirmedGuidedSlate
            session={session}
            stakeDisplay={stakeDisplay}
          />
        ) : null}

        {view === "review" && session && !session.confirmed ? (
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
                className="text-sm font-semibold"
                style={{ color: snapshotTokens.textPrimary }}
              >
                Review Guided Market Slate
              </p>
              <p
                className="mt-1 text-xs"
                style={{ color: snapshotTokens.textMuted }}
              >
                {session.summary?.ticket_count ?? 0} bets ·{" "}
                {session.summary?.individual_picks ?? 0} individual
                picks ·{" "}
                {formatStake(
                  Number(session.total_exposure || 0),
                  stakeDisplay
                )}{" "}
                exposure
              </p>
            </div>

            {(session.odds_alerts || []).length > 0 ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                Odds moved on{" "}
                {(session.odds_alerts || []).length} locked pick
                {(session.odds_alerts || []).length === 1 ? "" : "s"}.
                Replace affected legs before confirming.
              </div>
            ) : null}

            <div className="space-y-3">
              {(session.tickets || []).map((ticket) => (
                <article
                  key={ticket.ticket_index}
                  className="rounded-2xl border bg-white p-4"
                  style={{ borderColor: snapshotTokens.border }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p
                        className="text-xs font-semibold uppercase tracking-[0.14em]"
                        style={{ color: snapshotTokens.textMuted }}
                      >
                        Bet {ticket.ticket_index} ·{" "}
                        {ticket.ticket_type === "parlay"
                          ? `${ticket.leg_count}-leg parlay`
                          : "Single"}
                      </p>
                      <p
                        className="mt-1 text-sm font-semibold"
                        style={{ color: snapshotTokens.textPrimary }}
                      >
                        Stake{" "}
                        {formatStake(ticket.stake, stakeDisplay)}
                        {ticket.combined_odds != null
                          ? ` · ${formatAmerican(ticket.combined_odds)}`
                          : ""}
                      </p>
                    </div>
                    {ticket.potential_profit != null ? (
                      <p
                        className="text-sm font-semibold tabular-nums"
                        style={{ color: snapshotTokens.textPrimary }}
                      >
                        {formatStake(
                          ticket.potential_profit,
                          stakeDisplay,
                          { signed: true }
                        )}{" "}
                        to win
                      </p>
                    ) : null}
                  </div>
                  <ul className="mt-3 space-y-2">
                    {ticket.legs.map((leg) => {
                      const sel = leg.selection;
                      const step = (session.steps || []).find(
                        (row) =>
                          row.ticket_index === ticket.ticket_index
                          && row.leg_index === leg.leg_index
                      );
                      return (
                        <li
                          key={`${ticket.ticket_index}-${leg.leg_index}`}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-xl px-3 py-2"
                          style={{
                            background: snapshotTokens.background,
                          }}
                        >
                          <div className="min-w-0">
                            <p
                              className="text-xs"
                              style={{
                                color: snapshotTokens.textMuted,
                              }}
                            >
                              {leg.bucket_label}
                              {ticket.ticket_type === "parlay"
                                ? ` · leg ${leg.leg_index}`
                                : ""}
                            </p>
                            <p
                              className="text-sm font-medium"
                              style={{
                                color: snapshotTokens.textPrimary,
                              }}
                            >
                              {sel?.sport ? `${sel.sport} · ` : ""}
                              {sel?.selection || "—"}
                              {sel?.price != null
                                ? ` (${formatAmerican(sel.price)})`
                                : ""}
                            </p>
                          </div>
                          {step ? (
                            <button
                              type="button"
                              disabled={loading}
                              onClick={() =>
                                void handleReplace(step.step_index)
                              }
                              className="inline-flex items-center gap-1 text-xs font-semibold"
                              style={{ color: snapshotTokens.blue }}
                            >
                              <Replace className="h-3.5 w-3.5" />
                              Replace
                            </button>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}

function ConfirmedGuidedSlate({
  session,
  stakeDisplay,
}: {
  session: GuidedSlateSession;
  stakeDisplay: StakeDisplay;
}) {
  const picks = useMemo(
    () => (session.tickets || []).map(ticketToDailyPick),
    [session.tickets]
  );
  const singlesCount = picks.filter((pick) => pick.kind === "single")
    .length;
  const parlaysCount = picks.filter((pick) => pick.kind === "parlay")
    .length;
  const picksCount = picks.length;
  const totalPossibleWin = useMemo(() => {
    let total = 0;
    let any = false;
    for (const pick of picks) {
      if (
        pick.potential_profit != null
        && !Number.isNaN(pick.potential_profit)
      ) {
        total += Number(pick.potential_profit);
        any = true;
      }
    }
    return any ? total : null;
  }, [picks]);
  const allocated = Number(session.total_exposure || 0);
  const possibleRoiPct =
    totalPossibleWin != null && allocated > 0
      ? (totalPossibleWin / allocated) * 100
      : null;

  return (
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
        {picks.map((pick, index) => (
          <DailySlatePickCard
            key={`${pick.kind}-${pick.event_id ?? "x"}-${index}`}
            pick={pick}
            stakeDisplay={stakeDisplay}
          />
        ))}
      </div>

      <p
        className="text-xs leading-relaxed"
        style={{ color: snapshotTokens.textMuted }}
      >
        Guided Market Slate · market-implied probabilities only.
        Parlay joint probability assumes independence.
      </p>
    </section>
  );
}
