"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Trophy } from "lucide-react";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import TeamLogo from "@/components/teams/TeamLogo";
import {
  BettingSport,
  getPowerRankings,
  listBettingWeeks,
  PowerRankingsResult,
} from "@/services/api";

function formatSigned(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  const rounded = Number(value.toFixed(digits));
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

/** Week-over-week rank movement: positive = moved up. */
function formatRankTrend(
  change: number | null | undefined
): { label: string; up: boolean | null } {
  if (change == null || Number.isNaN(change)) {
    return { label: "—", up: null };
  }
  if (change === 0) return { label: "—", up: null };
  if (change > 0) return { label: `↑${change}`, up: true };
  return { label: `↓${Math.abs(change)}`, up: false };
}

const SPORTS: BettingSport[] = ["NFL", "CFB"];

export default function PowerRankings() {
  const [sport, setSport] = useState<BettingSport>("NFL");
  const [season, setSeason] = useState<number | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const [weeks, setWeeks] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PowerRankingsResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    (async () => {
      try {
        const payload = await listBettingWeeks(null, sport);
        if (cancelled) return;
        setSeason(payload.season);
        setWeeks(payload.weeks || []);
        setWeek(payload.current_week);
      } catch (err) {
        if (!cancelled) {
          setSeason(null);
          setWeeks([]);
          setWeek(null);
          setError(
            err instanceof Error
              ? err.message
              : `Failed to load ${sport} weeks.`
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sport]);

  useEffect(() => {
    if (season == null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const payload = await getPowerRankings({
          sport,
          season,
          week,
          persist: false,
        });
        if (cancelled) return;
        setResult(payload);
      } catch (err) {
        if (!cancelled) {
          setResult(null);
          setError(
            err instanceof Error
              ? err.message
              : "Failed to build power rankings."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sport, season, week]);

  const top = useMemo(
    () => (result?.rankings || []).slice(0, 5),
    [result]
  );
  const showConference = sport === "CFB";

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p
            className="text-xs font-semibold uppercase tracking-[0.18em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            {sport === "CFB" ? "CFB" : "NFL"} Power Rankings
          </p>
          <p
            className="mt-1 text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {sport === "CFB"
              ? "Opponent-adjusted FBS team strength from scoring and yards efficiency. Independent of sportsbook prices."
              : "Opponent-adjusted team strength from EPA and scoring efficiency. Independent of sportsbook prices."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div
            className="inline-flex rounded-lg border p-0.5"
            style={{ borderColor: snapshotTokens.border }}
            role="group"
            aria-label="Sport"
          >
            {SPORTS.map((value) => {
              const selected = sport === value;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setSport(value)}
                  className="rounded-md px-2.5 py-1.5 text-xs font-semibold"
                  style={{
                    background: selected
                      ? snapshotTokens.blue
                      : "transparent",
                    color: selected
                      ? snapshotTokens.white
                      : snapshotTokens.textPrimary,
                  }}
                >
                  {value}
                </button>
              );
            })}
          </div>
          <label
            className="text-xs font-semibold uppercase tracking-[0.12em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            Week
            <select
              className="ml-2 rounded-lg border px-2 py-1.5 text-sm font-semibold"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textPrimary,
                background: snapshotTokens.white,
              }}
              value={week ?? ""}
              onChange={(event) =>
                setWeek(
                  event.target.value ? Number(event.target.value) : null
                )
              }
            >
              <option value="">Latest</option>
              {weeks.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={loading || season == null}
            onClick={() => {
              setLoading(true);
              void getPowerRankings({
                sport,
                season,
                week,
                persist: false,
              })
                .then(setResult)
                .catch((err) =>
                  setError(
                    err instanceof Error
                      ? err.message
                      : "Failed to refresh rankings."
                  )
                )
                .finally(() => setLoading(false));
            }}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl px-3 text-xs font-semibold disabled:opacity-60"
            style={{
              background: snapshotTokens.background,
              color: snapshotTokens.textPrimary,
            }}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
            Refresh
          </button>
        </div>
      </header>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div
          className="rounded-2xl border border-dashed px-4 py-10 text-center text-sm"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textMuted,
          }}
        >
          Building rankings…
        </div>
      ) : null}

      {!loading && result ? (
        <>
          <div
            className="flex flex-wrap items-center gap-3 rounded-2xl border border-l-4 px-4 py-3"
            style={{
              borderColor: snapshotTokens.border,
              borderLeftColor: snapshotTokens.blue,
              background: snapshotTokens.background,
            }}
          >
            <div
              className="flex h-11 w-11 items-center justify-center rounded-xl"
              style={{
                background: snapshotTokens.blueLight,
                color: snapshotTokens.blue,
              }}
            >
              <Trophy className="h-5 w-5" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <p
                className="text-sm font-semibold"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {result.sport} · Season {result.season}
                {result.week != null ? ` · Week ${result.week}` : ""}
              </p>
              <p
                className="text-xs"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {result.team_count} teams · {result.games_used ?? 0}{" "}
                games · {result.calculation_version}
              </p>
            </div>
            {top.length ? (
              <p
                className="text-xs"
                style={{ color: snapshotTokens.textMuted }}
              >
                Top:{" "}
                {top
                  .map((row) => row.team_abbreviation || row.team_id)
                  .join(" · ")}
              </p>
            ) : null}
          </div>

          <div
            className="overflow-x-auto rounded-2xl border bg-white"
            style={{ borderColor: snapshotTokens.border }}
          >
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr
                  className="border-b text-xs uppercase tracking-[0.12em]"
                  style={{
                    borderColor: snapshotTokens.border,
                    color: snapshotTokens.textMuted,
                  }}
                >
                  <th className="px-3 py-3 font-semibold">Rank</th>
                  <th className="px-3 py-3 font-semibold">Team</th>
                  {showConference ? (
                    <th className="px-3 py-3 font-semibold">Conf</th>
                  ) : null}
                  <th className="px-3 py-3 font-semibold">W-L</th>
                  <th className="px-3 py-3 font-semibold">Overall</th>
                  <th className="px-3 py-3 font-semibold">Off</th>
                  <th className="px-3 py-3 font-semibold">Def</th>
                  <th className="px-3 py-3 font-semibold">ST</th>
                  <th className="px-3 py-3 font-semibold">Form</th>
                  <th className="px-3 py-3 font-semibold">SOS</th>
                  <th className="px-3 py-3 font-semibold">Conf%</th>
                  <th className="px-3 py-3 font-semibold">Trend</th>
                </tr>
              </thead>
              <tbody>
                {(result.rankings || []).map((row) => {
                  const trend = formatRankTrend(
                    row.rank_change ?? row.rating_trend
                  );
                  const recordLabel =
                    row.wins == null || row.losses == null
                      ? "—"
                      : row.ties
                        ? `${row.wins}-${row.losses}-${row.ties}`
                        : `${row.wins}-${row.losses}`;
                  return (
                    <tr
                      key={row.team_id}
                      className="border-b last:border-b-0"
                      style={{ borderColor: snapshotTokens.divider }}
                    >
                      <td className="px-3 py-2.5 tabular-nums font-semibold">
                        {row.rank}
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="inline-flex items-center gap-2 font-medium">
                          <TeamLogo
                            abbreviation={row.team_abbreviation}
                            logoUrl={row.logo_url}
                            sport={sport}
                            size={20}
                          />
                          {row.team_abbreviation || row.team_name}
                        </span>
                      </td>
                      {showConference ? (
                        <td
                          className="px-3 py-2.5 text-xs"
                          style={{ color: snapshotTokens.textMuted }}
                        >
                          {row.conference || "—"}
                        </td>
                      ) : null}
                      <td className="px-3 py-2.5 tabular-nums font-medium">
                        {recordLabel}
                      </td>
                      <td className="px-3 py-2.5 font-semibold tabular-nums">
                        {formatSigned(row.overall_power_rating)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {formatSigned(row.offensive_rating)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {formatSigned(row.defensive_rating)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {formatSigned(row.special_teams_rating)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {formatSigned(row.recent_form)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {formatSigned(row.strength_of_schedule)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {row.confidence == null
                          ? "—"
                          : `${Math.round(row.confidence * 100)}%`}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums font-medium">
                        <span
                          style={{
                            color:
                              trend.up === true
                                ? snapshotTokens.blue
                                : trend.up === false
                                  ? snapshotTokens.textMuted
                                  : snapshotTokens.textSecondary,
                          }}
                        >
                          {trend.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {(result.data_limitations || []).length ? (
            <div className="space-y-1">
              <p
                className="text-xs font-semibold uppercase tracking-[0.12em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                Data limitations
              </p>
              <ul
                className="space-y-1 text-xs"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {(result.data_limitations || []).map((item) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
