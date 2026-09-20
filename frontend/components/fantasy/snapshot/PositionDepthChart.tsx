"use client";

import { FantasyPlayerSnapshot } from "@/services/api";

import { snapshotTokens } from "./tokens";

interface Props {
  active: FantasyPlayerSnapshot;
  onSelectPlayer?: (playerId: string) => void;
}

export default function PositionDepthChart({
  active,
  onSelectPlayer,
}: Props) {
  const depth = active.position_depth_chart;
  const players = depth?.players ?? [];
  const position =
    depth?.position || active.position || "Position";

  const subtitleParts: string[] = [];
  if (active.team) {
    subtitleParts.push(active.team);
  }
  if (depth?.season != null) {
    let asOf = `As of ${depth.season}`;
    if (depth.week != null) {
      asOf += ` W${depth.week}`;
    }
    subtitleParts.push(asOf);
  }

  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3
            className="text-[15px] font-semibold"
            style={{ color: snapshotTokens.navy }}
          >
            {position} Depth Chart
          </h3>
          {subtitleParts.length > 0 && (
            <p
              className="mt-1 text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              {subtitleParts.join(" · ")}
            </p>
          )}
        </div>
        {active.depth_chart && (
          <span
            className="rounded-full border px-2.5 py-1 text-xs font-semibold"
            style={{
              borderColor: snapshotTokens.border,
              background: snapshotTokens.blueLight,
              color: snapshotTokens.blue,
            }}
          >
            {active.depth_chart}
          </span>
        )}
      </div>

      {players.length === 0 ? (
        <p
          className="mt-4 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Depth chart data is not available for this
          position yet.
        </p>
      ) : (
        <ul className="mt-4 space-y-1.5">
          {players.map((player) => {
            const highlighted = Boolean(
              player.is_current_player
              || player.player_id === active.player_id
            );
            const meta = [
              player.depth_chart,
              player.role,
            ]
              .filter(Boolean)
              .join(" · ");
            const name = (
              <>
                {player.depth_order != null
                  && `${player.depth_order}. `}
                {player.name || "—"}
              </>
            );

            if (onSelectPlayer && !highlighted) {
              return (
                <li key={player.player_id}>
                  <button
                    type="button"
                    onClick={() =>
                      onSelectPlayer(player.player_id)
                    }
                    className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition"
                    style={{ color: snapshotTokens.textPrimary }}
                    onMouseEnter={(event) => {
                      event.currentTarget.style.background =
                        snapshotTokens.background;
                    }}
                    onMouseLeave={(event) => {
                      event.currentTarget.style.background =
                        "transparent";
                    }}
                  >
                    <span className="truncate font-medium">
                      {name}
                    </span>
                    {meta && (
                      <span
                        className="shrink-0 text-[11px]"
                        style={{
                          color: snapshotTokens.textMuted,
                        }}
                      >
                        {meta}
                      </span>
                    )}
                  </button>
                </li>
              );
            }

            return (
              <li key={player.player_id}>
                <div
                  className="flex items-center justify-between gap-2 rounded-lg border px-2.5 py-2 text-sm"
                  style={{
                    borderColor: highlighted
                      ? snapshotTokens.blue
                      : "transparent",
                    background: highlighted
                      ? snapshotTokens.blueLight
                      : "transparent",
                    color: snapshotTokens.textPrimary,
                  }}
                >
                  <span className="truncate font-semibold">
                    {name}
                  </span>
                  {meta && (
                    <span
                      className="shrink-0 text-[11px] font-medium"
                      style={{
                        color: highlighted
                          ? snapshotTokens.blue
                          : snapshotTokens.textMuted,
                      }}
                    >
                      {meta}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
