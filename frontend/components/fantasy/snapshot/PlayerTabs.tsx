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
      className="flex gap-1 overflow-x-auto border-b"
      style={{ borderColor: snapshotTokens.divider }}
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
            className="shrink-0 border-b-[2.5px] px-3 py-2.5 text-sm transition disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              borderColor: selected
                ? snapshotTokens.blue
                : "transparent",
              color: selected
                ? snapshotTokens.blue
                : snapshotTokens.textSecondary,
              fontWeight: selected ? 600 : 500,
            }}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
