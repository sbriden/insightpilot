"use client";

import { snapshotTokens } from "./tokens";

export type SnapshotTabId =
  | "snapshot"
  | "stats"
  | "usage"
  | "matchups"
  | "news";

const TABS: Array<{
  id: SnapshotTabId;
  label: string;
  enabled: boolean;
}> = [
  { id: "snapshot", label: "Snapshot", enabled: true },
  { id: "stats", label: "Stats", enabled: true },
  { id: "usage", label: "Usage & Trends", enabled: true },
  { id: "matchups", label: "Matchups", enabled: true },
  { id: "news", label: "News", enabled: true },
];

interface Props {
  active: SnapshotTabId;
  onChange: (tab: SnapshotTabId) => void;
}

export default function PlayerTabs({
  active,
  onChange,
}: Props) {
  return (
    <div
      className="flex flex-wrap gap-1 border-b pb-2"
      style={{ borderColor: snapshotTokens.border }}
      role="tablist"
      aria-label="Player sections"
    >
      {TABS.map((tab) => {
        const selected = active === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            disabled={!tab.enabled}
            onClick={() => {
              if (tab.enabled) {
                onChange(tab.id);
              }
            }}
            className="rounded-md px-3 py-1.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: selected
                ? snapshotTokens.blueLight
                : "transparent",
              color: selected
                ? snapshotTokens.blue
                : snapshotTokens.textSecondary,
            }}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
