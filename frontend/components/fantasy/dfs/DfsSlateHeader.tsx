"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type {
  DfsContestType,
  DfsRisk,
  DfsSiteId,
} from "@/services/api";

interface Props {
  site: DfsSiteId;
  sites: Array<{ id: string; name: string }>;
  slateId: string;
  slates: Array<{ slate_id: string; label: string }>;
  contestType: DfsContestType;
  risk: DfsRisk;
  optimizing: boolean;
  onSite: (site: DfsSiteId) => void;
  onSlate: (slateId: string) => void;
  onContest: (contest: DfsContestType) => void;
  onRisk: (risk: DfsRisk) => void;
  onOptimize: () => void;
  freshness?: string | null;
}

const CONTESTS: Array<{ id: DfsContestType; label: string }> = [
  { id: "classic", label: "Classic" },
  { id: "showdown", label: "Showdown" },
];

export default function DfsSlateHeader({
  site,
  sites,
  slateId,
  slates,
  contestType,
  risk,
  optimizing,
  onSite,
  onSlate,
  onContest,
  onRisk,
  onOptimize,
  freshness,
}: Props) {
  return (
    <header className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span
            className="inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
            style={{
              background: snapshotTokens.blueLight,
              color: snapshotTokens.blue,
            }}
          >
            Daily Fantasy
          </span>
          <h2
            className="mt-2 text-xl font-semibold tracking-tight sm:text-2xl"
            style={{ color: snapshotTokens.navy }}
          >
            Daily Fantasy Analyzer / Optimizer
          </h2>
          <p
            className="mt-1 max-w-2xl text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Analyze today&apos;s slate, identify the strongest DFS
            opportunities, and build optimized lineups using
            InsightPilot projections and matchup analysis.
          </p>
        </div>
        <button
          type="button"
          onClick={onOptimize}
          disabled={optimizing}
          className="rounded-lg px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          style={{ background: snapshotTokens.blue }}
        >
          {optimizing ? "Optimizing…" : "Optimize Lineup"}
        </button>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <Select
          label="Sport"
          value="NFL"
          options={[{ value: "NFL", label: "NFL" }]}
          onChange={() => undefined}
          disabled
        />
        <Select
          label="DFS Site"
          value={String(site)}
          options={sites.map((item) => ({
            value: item.id,
            label: item.name,
          }))}
          onChange={(value) => onSite(value)}
        />
        <Select
          label="Contest"
          value={contestType}
          options={CONTESTS.map((item) => ({
            value: item.id,
            label: item.label,
          }))}
          onChange={(value) =>
            onContest(value as DfsContestType)
          }
        />
        <Select
          label="Slate"
          value={slateId}
          options={slates.map((item) => ({
            value: item.slate_id,
            label: item.label,
          }))}
          onChange={onSlate}
        />
        <div className="min-w-[10rem]">
          <p
            className="mb-1 text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Risk
          </p>
          <input
            type="range"
            min={0}
            max={2}
            step={1}
            value={
              risk === "conservative"
                ? 0
                : risk === "aggressive"
                  ? 2
                  : 1
            }
            onChange={(event) => {
              const next = Number(event.target.value);
              onRisk(
                next === 0
                  ? "conservative"
                  : next === 2
                    ? "aggressive"
                    : "balanced"
              );
            }}
            className="w-full"
            aria-label="Risk tolerance"
          />
          <p
            className="mt-0.5 text-[11px] capitalize"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {risk}
          </p>
        </div>
      </div>

      {freshness && (
        <p
          className="text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          {freshness}
        </p>
      )}
    </header>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="block min-w-[8.5rem]">
      <span
        className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </span>
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border bg-white px-2.5 py-2 text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textPrimary,
        }}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
