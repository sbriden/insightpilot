"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPlayer } from "@/services/api";

interface Props {
  players: DfsPlayer[];
  onSelectPlayer: (playerId: string) => void;
}

export default function ValuePlays({
  players,
  onSelectPlayer,
}: Props) {
  const top = [...players]
    .filter((player) => player.value != null)
    .sort(
      (left, right) =>
        (right.value || 0) - (left.value || 0)
    )
    .slice(0, 6);

  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-[15px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Top Value Plays
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Highest projection per $1,000 of salary — not must-plays.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead
            className="text-[11px] uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            <tr>
              <th className="py-1.5 pr-2 font-medium">Player</th>
              <th className="px-2 py-1.5 font-medium">Pos</th>
              <th className="px-2 py-1.5 text-right font-medium">
                Proj
              </th>
              <th className="px-2 py-1.5 text-right font-medium">
                Salary
              </th>
              <th className="px-2 py-1.5 text-right font-medium">
                Value
              </th>
            </tr>
          </thead>
          <tbody>
            {top.map((player) => (
              <tr
                key={player.player_id}
                className="border-t"
                style={{ borderColor: snapshotTokens.divider }}
              >
                <td className="py-2 pr-2">
                  <button
                    type="button"
                    className="font-medium"
                    style={{ color: snapshotTokens.textPrimary }}
                    onClick={() =>
                      onSelectPlayer(player.player_id)
                    }
                  >
                    {player.name}
                  </button>
                </td>
                <td
                  className="px-2 py-2"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {player.position}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {player.projection.toFixed(1)}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">
                  ${player.salary.toLocaleString()}
                </td>
                <td
                  className="px-2 py-2 text-right font-semibold tabular-nums"
                  style={{ color: snapshotTokens.blue }}
                >
                  {player.value?.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
