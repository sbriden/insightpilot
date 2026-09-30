"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import { BettingGameScript } from "@/services/api";

interface Props {
  scripts: BettingGameScript[];
  compact?: boolean;
}

export default function GameScriptsPanel({
  scripts,
  compact = false,
}: Props) {
  if (!scripts.length) return null;

  const rows = compact ? scripts.slice(0, 3) : scripts;

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      {!compact ? (
        <div>
          <p
            className="text-xs font-semibold uppercase tracking-[0.14em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            Game Script Projections
          </p>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Independent scenario chances from InsightPilot projected
            margin and total. Scripts can overlap.
          </p>
        </div>
      ) : (
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.12em]"
          style={{ color: snapshotTokens.textMuted }}
        >
          Top scripts
        </p>
      )}

      <ul className="space-y-2">
        {rows.map((script) => (
          <li
            key={script.script_id}
            className="rounded-lg border px-3 py-2"
            style={{ borderColor: snapshotTokens.border }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p
                  className="text-sm font-medium"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {script.label}
                </p>
                {!compact && script.summary ? (
                  <p
                    className="mt-0.5 text-xs"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {script.summary}
                  </p>
                ) : null}
              </div>
              <p
                className="shrink-0 text-sm font-semibold tabular-nums"
                style={{ color: snapshotTokens.blue }}
              >
                {pct(script.probability)}
              </p>
            </div>
            <div
              className="mt-2 h-1.5 overflow-hidden rounded-full"
              style={{ background: snapshotTokens.divider }}
            >
              <div
                className="h-full rounded-full transition-[width]"
                style={{
                  width: `${Math.max(2, Math.min(100, script.probability * 100))}%`,
                  background: snapshotTokens.blue,
                }}
              />
            </div>
            {!compact && script.explanation ? (
              <p
                className="mt-2 text-xs leading-relaxed"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {script.explanation}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}
