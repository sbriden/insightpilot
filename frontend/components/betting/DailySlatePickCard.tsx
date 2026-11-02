"use client";

import { formatAmerican } from "@/components/betting/formatMarketValues";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import { TeamMatchupLabel } from "@/components/teams/TeamLogo";
import { DailyBettingPick } from "@/services/api";

export type StakeDisplay = "units" | "dollars";

export function formatStake(
  value: number,
  display: StakeDisplay,
  options?: { signed?: boolean }
): string {
  const rounded = Math.round(value);
  const sign =
    options?.signed && rounded > 0
      ? "+"
      : options?.signed && rounded < 0
        ? "-"
        : "";
  const abs = Math.abs(rounded);
  if (display === "dollars") {
    return `${sign}$${abs}`;
  }
  return `${sign}\u00A4${abs}`;
}

export function formatWinPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

export function DailySlatePickCard({
  pick,
  stakeDisplay,
}: {
  pick: DailyBettingPick;
  stakeDisplay: StakeDisplay;
}) {
  const isParlay = pick.kind === "parlay";
  const sport = String(pick.sport || "MULTI");
  const marketProb =
    pick.fair_probability ?? pick.win_probability;

  return (
    <article
      className="rounded-2xl border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em]"
              style={{
                background: snapshotTokens.background,
                color: snapshotTokens.textSecondary,
              }}
            >
              {sport}
            </span>
            <span
              className="text-[11px] font-semibold uppercase tracking-[0.08em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              {isParlay ? "Parlay" : pick.market_type || "Pick"}
            </span>
          </div>
          {!isParlay ? (
            <div className="text-sm font-medium">
              <TeamMatchupLabel
                label={pick.event_label}
                away={pick.away_team}
                home={pick.home_team}
                awayLogoUrl={pick.away_logo_url}
                homeLogoUrl={pick.home_logo_url}
                sport={sport}
                size={18}
              />
            </div>
          ) : (
            <p
              className="text-sm font-medium"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {pick.selection}
            </p>
          )}
          <p
            className="text-sm"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {isParlay
              ? `${pick.legs?.length ?? 0} legs`
              : pick.selection}
            {" · "}
            {formatAmerican(pick.offered_odds ?? pick.price)}
          </p>
          {pick.potential_profit != null ? (
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              To win {formatStake(pick.potential_profit, stakeDisplay)}
              {pick.potential_payout != null
                ? ` · pays ${formatStake(pick.potential_payout, stakeDisplay)}`
                : ""}
            </p>
          ) : null}
        </div>
        <div className="shrink-0 text-right">
          <p
            className="text-lg font-semibold tabular-nums"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {formatStake(pick.units, stakeDisplay)}
          </p>
          <p
            className="text-xs tabular-nums"
            style={{ color: snapshotTokens.textMuted }}
          >
            {formatWinPct(marketProb)} mkt
          </p>
        </div>
      </div>

      {isParlay && pick.legs?.length ? (
        <ul
          className="mt-3 space-y-2 border-t pt-3"
          style={{ borderColor: snapshotTokens.divider }}
        >
          {pick.legs.map((leg, index) => (
            <li
              key={`${leg.event_id ?? "leg"}-${index}`}
              className="flex items-start justify-between gap-3 text-sm"
            >
              <div className="min-w-0">
                <p
                  className="text-[11px] font-semibold uppercase tracking-[0.08em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {leg.sport} · {leg.market_type}
                </p>
                <p style={{ color: snapshotTokens.textPrimary }}>
                  {leg.selection}
                </p>
                <p
                  className="text-xs"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  <TeamMatchupLabel
                    label={leg.event_label}
                    away={leg.away_team}
                    home={leg.home_team}
                    awayLogoUrl={leg.away_logo_url}
                    homeLogoUrl={leg.home_logo_url}
                    sport={String(leg.sport || sport)}
                    size={14}
                  />
                </p>
              </div>
              <span
                className="shrink-0 text-xs tabular-nums"
                style={{ color: snapshotTokens.textMuted }}
              >
                {formatAmerican(leg.price)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}
