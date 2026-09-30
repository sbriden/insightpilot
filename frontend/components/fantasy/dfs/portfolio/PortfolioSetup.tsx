"use client";

import { useState } from "react";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPortfolioStrategy } from "@/services/api";

const PRESETS = [5, 10, 20, 50, 100];

const STRATEGIES: Array<{
  id: DfsPortfolioStrategy;
  label: string;
  blurb: string;
}> = [
  {
    id: "max_projection",
    label: "Max Projection",
    blurb:
      "Maximize total projected points with only minimum portfolio constraints.",
  },
  {
    id: "balanced",
    label: "Balanced",
    blurb:
      "Strong lineups first, with moderate exposure and game-script diversification.",
  },
  {
    id: "tournament",
    label: "Tournament",
    blurb:
      "Ceiling, leverage, and uniqueness under controlled exposure caps.",
  },
  {
    id: "contrarian",
    label: "Contrarian",
    blurb:
      "Lower-owned constructions with a hard floor on projection quality.",
  },
];

interface Props {
  lineupCount: number;
  strategy: DfsPortfolioStrategy;
  maxSimilarity: number;
  minUniquePlayers: number;
  defaultMaxExposure: number;
  defaultMaxCaptainExposure?: number;
  gameScriptDiversification?: boolean;
  showCaptainLimits?: boolean;
  onLineupCount: (value: number) => void;
  onStrategy: (value: DfsPortfolioStrategy) => void;
  onMaxSimilarity: (value: number) => void;
  onMinUniquePlayers: (value: number) => void;
  onDefaultMaxExposure: (value: number) => void;
  onDefaultMaxCaptainExposure?: (value: number) => void;
  onGameScriptDiversification?: (value: boolean) => void;
}

export default function PortfolioSetup({
  lineupCount,
  strategy,
  maxSimilarity,
  minUniquePlayers,
  defaultMaxExposure,
  defaultMaxCaptainExposure = 0.4,
  gameScriptDiversification = true,
  showCaptainLimits = false,
  onLineupCount,
  onStrategy,
  onMaxSimilarity,
  onMinUniquePlayers,
  onDefaultMaxExposure,
  onDefaultMaxCaptainExposure,
  onGameScriptDiversification,
}: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Portfolio Size
          </p>
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              className="h-8 w-8 rounded-md border text-sm font-semibold"
              style={{ borderColor: snapshotTokens.border }}
              onClick={() =>
                onLineupCount(Math.max(1, lineupCount - 1))
              }
            >
              −
            </button>
            <input
              type="number"
              min={1}
              max={100}
              value={lineupCount}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isFinite(next)) {
                  onLineupCount(
                    Math.max(1, Math.min(100, Math.round(next)))
                  );
                }
              }}
              className="w-16 rounded-md border px-2 py-1.5 text-center text-sm"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textPrimary,
              }}
            />
            <button
              type="button"
              className="h-8 w-8 rounded-md border text-sm font-semibold"
              style={{ borderColor: snapshotTokens.border }}
              onClick={() =>
                onLineupCount(Math.min(100, lineupCount + 1))
              }
            >
              +
            </button>
            <div className="ml-2 flex flex-wrap gap-1">
              {PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => onLineupCount(preset)}
                  className="rounded-md border px-2 py-1 text-xs font-semibold"
                  style={{
                    borderColor:
                      lineupCount === preset
                        ? snapshotTokens.blue
                        : snapshotTokens.border,
                    color:
                      lineupCount === preset
                        ? snapshotTokens.blue
                        : snapshotTokens.textSecondary,
                  }}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="min-w-[14rem] flex-1">
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Strategy
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {STRATEGIES.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onStrategy(item.id)}
                className="rounded-md border px-2.5 py-1.5 text-xs font-semibold"
                style={{
                  borderColor:
                    strategy === item.id
                      ? snapshotTokens.blue
                      : snapshotTokens.border,
                  background:
                    strategy === item.id
                      ? snapshotTokens.blueLight
                      : "transparent",
                  color:
                    strategy === item.id
                      ? snapshotTokens.blue
                      : snapshotTokens.textPrimary,
                }}
                title={item.blurb}
              >
                {item.label}
              </button>
            ))}
          </div>
          <p
            className="mt-1.5 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {STRATEGIES.find((item) => item.id === strategy)?.blurb}
          </p>
        </div>
      </div>

      <div
        className={[
          "mt-4 grid gap-3",
          showCaptainLimits ? "sm:grid-cols-3" : "sm:grid-cols-2",
        ].join(" ")}
      >
        <label className="block">
          <span
            className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Default Max Player Exposure (
            {Math.round(defaultMaxExposure * 100)}%)
          </span>
          <input
            type="range"
            min={20}
            max={100}
            step={5}
            value={Math.round(defaultMaxExposure * 100)}
            onChange={(event) =>
              onDefaultMaxExposure(
                Number(event.target.value) / 100
              )
            }
            className="w-full"
          />
        </label>
        <label className="block">
          <span
            className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Minimum Unique Players ({minUniquePlayers})
          </span>
          <input
            type="range"
            min={0}
            max={5}
            step={1}
            value={minUniquePlayers}
            onChange={(event) =>
              onMinUniquePlayers(Number(event.target.value))
            }
            className="w-full"
          />
          <span
            className="mt-1 block text-[11px]"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Each new lineup must differ by at least this many
            players — not “avoid used players.”
          </span>
        </label>
        {showCaptainLimits && onDefaultMaxCaptainExposure ? (
          <label className="block">
            <span
              className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              Default Max Captain Exposure (
              {Math.round(defaultMaxCaptainExposure * 100)}%)
            </span>
            <input
              type="range"
              min={10}
              max={100}
              step={5}
              value={Math.round(defaultMaxCaptainExposure * 100)}
              onChange={(event) =>
                onDefaultMaxCaptainExposure(
                  Number(event.target.value) / 100
                )
              }
              className="w-full"
            />
          </label>
        ) : null}
      </div>

      {showCaptainLimits && onGameScriptDiversification ? (
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={gameScriptDiversification}
            onChange={(event) =>
              onGameScriptDiversification(event.target.checked)
            }
          />
          <span style={{ color: snapshotTokens.textPrimary }}>
            Game Script Diversification
          </span>
        </label>
      ) : null}

      <button
        type="button"
        className="mt-3 text-xs font-semibold"
        style={{ color: snapshotTokens.blue }}
        onClick={() => setAdvancedOpen((open) => !open)}
      >
        {advancedOpen ? "Hide advanced" : "Advanced settings"}
      </button>
      {advancedOpen ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span
              className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              Max Lineup Similarity (
              {Math.round(maxSimilarity * 100)}%)
            </span>
            <input
              type="range"
              min={40}
              max={95}
              step={5}
              value={Math.round(maxSimilarity * 100)}
              onChange={(event) =>
                onMaxSimilarity(Number(event.target.value) / 100)
              }
              className="w-full"
            />
          </label>
        </div>
      ) : null}
    </section>
  );
}
