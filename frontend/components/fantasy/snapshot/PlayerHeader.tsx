"use client";

import { User } from "lucide-react";

import {
  FantasyPlayerSnapshot,
} from "@/services/api";

import {
  assessmentStyles,
  formatMetricValue,
  formatScore,
  snapshotTokens,
} from "./tokens";

interface Props {
  active: FantasyPlayerSnapshot;
}

export default function PlayerHeader({
  active,
}: Props) {
  const assessment = assessmentStyles(
    active.overall_assessment
  );
  const subtitle = [
    active.depth_chart || active.position,
    active.team,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 items-start gap-4">
        <div
          className="relative h-24 w-24 shrink-0 overflow-hidden rounded-2xl border bg-white sm:h-[108px] sm:w-[108px]"
          style={{ borderColor: snapshotTokens.border }}
        >
          {active.headshot_url ? (
            // External ESPN CDN headshot
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={active.headshot_url}
              alt=""
              className="h-full w-full object-cover object-top"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          ) : (
            <div
              className="flex h-full w-full items-center justify-center"
              style={{ background: snapshotTokens.background }}
            >
              <User
                className="h-10 w-10"
                style={{ color: snapshotTokens.textMuted }}
              />
            </div>
          )}
        </div>

        <div className="min-w-0 pt-0.5">
          <h2
            id="player-snapshot-title"
            className="truncate text-[28px] font-bold leading-tight tracking-tight sm:text-[32px]"
            style={{ color: snapshotTokens.navy }}
          >
            {active.name || active.player_id}
          </h2>
          <p
            className="mt-1 text-sm font-medium"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {subtitle || "—"}
          </p>

          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs">
            {(
              [
                ["Age", active.age],
                ["Exp", active.experience_years != null
                  ? `${active.experience_years} yrs`
                  : null],
                ["Status", active.status],
                ["Injury", active.injury_status],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <p
                  className="font-medium uppercase tracking-wide"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {label}
                </p>
                <p
                  className="mt-0.5 text-sm font-semibold"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {value == null || value === ""
                    ? "—"
                    : String(value)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 gap-3 sm:gap-4">
        <div
          className="min-w-[5.5rem] rounded-[10px] border bg-white px-4 py-3 text-center"
          style={{ borderColor: snapshotTokens.border }}
        >
          <p
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Overall Rank
          </p>
          <p
            className="mt-1 text-[26px] font-bold tabular-nums leading-none"
            style={{ color: snapshotTokens.navy }}
          >
            {active.overall_rank != null
              ? `#${active.overall_rank}`
              : "—"}
          </p>
        </div>

        <div
          className="min-w-[5.5rem] rounded-[10px] border bg-white px-4 py-3 text-center"
          style={{ borderColor: snapshotTokens.border }}
        >
          <p
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Fantasy Points
          </p>
          <p
            className="mt-1 text-[26px] font-bold tabular-nums leading-none"
            style={{ color: snapshotTokens.navy }}
          >
            {formatMetricValue(
              active.season_stats?.fantasy_points
            )}
          </p>
        </div>

        <div
          className="min-w-[5.5rem] rounded-[10px] border px-4 py-3 text-center"
          style={{
            borderColor: assessment.border,
            background: assessment.bg,
          }}
        >
          <p
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: assessment.text }}
          >
            Assessment
          </p>
          <p
            className="mt-1 text-[26px] font-bold tabular-nums leading-none"
            style={{ color: assessment.text }}
          >
            {formatScore(active.fantasy_value_score)}
          </p>
          <p
            className="mt-1 text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: assessment.text }}
          >
            {active.overall_assessment || "—"}
          </p>
        </div>
      </div>
    </div>
  );
}
