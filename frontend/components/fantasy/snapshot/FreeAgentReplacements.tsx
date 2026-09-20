"use client";

import { ArrowRight, User } from "lucide-react";

import {
  FantasyReplacementPlayer,
} from "@/services/api";

import {
  assessmentStyles,
  formatMetricValue,
  formatScore,
  snapshotTokens,
} from "./tokens";

interface Props {
  replacements: FantasyReplacementPlayer[];
  onSelect?: (player: FantasyReplacementPlayer) => void;
}

export default function FreeAgentReplacements({
  replacements,
  onSelect,
}: Props) {
  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-[15px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Free Agent Replacements
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Same-position players under 50% ownership — click to
        compare
      </p>

      {replacements.length === 0 ? (
        <p
          className="mt-4 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          InsightPilot doesn&apos;t have replacement
          candidates for this player yet.
        </p>
      ) : (
        <ul
          className="mt-3 divide-y"
          style={{ borderColor: snapshotTokens.divider }}
        >
          {replacements.map((player) => {
            const tone = assessmentStyles(
              player.overall_assessment
            );
            return (
              <li key={player.player_id}>
                <button
                  type="button"
                  className="group flex w-full items-center gap-3 py-3 text-left transition"
                  onClick={() => onSelect?.(player)}
                  onMouseEnter={(event) => {
                    event.currentTarget.style.background =
                      snapshotTokens.blueLight;
                  }}
                  onMouseLeave={(event) => {
                    event.currentTarget.style.background =
                      "transparent";
                  }}
                >
                  <div
                    className="h-10 w-10 shrink-0 overflow-hidden rounded-full border bg-white"
                    style={{ borderColor: snapshotTokens.border }}
                  >
                    {player.headshot_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={player.headshot_url}
                        alt=""
                        className="h-full w-full object-cover object-top"
                      />
                    ) : (
                      <div
                        className="flex h-full w-full items-center justify-center"
                        style={{
                          background: snapshotTokens.background,
                        }}
                      >
                        <User
                          className="h-4 w-4"
                          style={{
                            color: snapshotTokens.textMuted,
                          }}
                        />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p
                      className="truncate text-sm font-semibold"
                      style={{
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      {player.name}
                    </p>
                    <p
                      className="text-xs"
                      style={{
                        color: snapshotTokens.textMuted,
                      }}
                    >
                      {[player.position, player.team]
                        .filter(Boolean)
                        .join(" · ") || "—"}
                      {player.ownership != null
                        && ` · ${player.ownership.toFixed(1)}% owned`}
                    </p>
                  </div>
                  <div className="text-right">
                    <p
                      className="text-sm font-bold tabular-nums"
                      style={{
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      {formatMetricValue(
                        player.fantasy_points
                      )}
                    </p>
                    <span
                      className="mt-0.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold tabular-nums"
                      style={{
                        background: tone.bg,
                        color: tone.text,
                      }}
                    >
                      {formatScore(
                        player.fantasy_value_score
                      )}
                    </span>
                  </div>
                  <span
                    className="hidden items-center gap-0.5 text-xs font-semibold sm:inline-flex"
                    style={{ color: snapshotTokens.blue }}
                  >
                    Compare
                    <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
