"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ChevronDown, Search } from "lucide-react";

import {
  FantasyPlayerSearchHit,
} from "@/services/api";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";

interface Props {
  label: string;
  players: FantasyPlayerSearchHit[];
  value: string;
  excludeId?: string;
  onChange: (playerId: string) => void;
}

export default function SearchablePlayerSelect({
  label,
  players,
  value,
  excludeId,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const selected = players.find(
    (player) => player.player_id === value
  );

  const options = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return players
      .filter((player) => player.player_id !== excludeId)
      .filter((player) => {
        if (!needle) {
          return true;
        }
        const haystack = [
          player.name,
          player.position,
          player.team,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(needle);
      })
      .sort((left, right) =>
        left.name.localeCompare(right.name, undefined, {
          sensitivity: "base",
        })
      )
      .slice(0, 80);
  }, [players, query, excludeId]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (
        rootRef.current
        && !rootRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener(
        "mousedown",
        onPointerDown
      );
    };
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  return (
    <div ref={rootRef} className="relative block text-sm">
      <span
        className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </span>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-left"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textPrimary,
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate">
          {selected
            ? `${selected.name}${
                selected.position || selected.team
                  ? ` (${[selected.position, selected.team].filter(Boolean).join(" · ")})`
                  : ""
              }`
            : "Select a player…"}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0" />
      </button>

      {open && (
        <div
          className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border bg-white shadow-lg"
          style={{ borderColor: snapshotTokens.border }}
        >
          <div
            className="flex items-center gap-2 border-b px-3 py-2"
            style={{ borderColor: snapshotTokens.divider }}
          >
            <Search
              className="h-4 w-4 shrink-0"
              style={{ color: snapshotTokens.textMuted }}
            />
            <input
              ref={inputRef}
              type="search"
              value={query}
              onChange={(event) =>
                setQuery(event.target.value)
              }
              placeholder="Search name, position, team…"
              className="w-full bg-transparent text-sm outline-none"
              style={{ color: snapshotTokens.textPrimary }}
            />
          </div>
          <ul
            className="max-h-64 overflow-auto py-1"
            role="listbox"
          >
            {options.length === 0 ? (
              <li
                className="px-3 py-2 text-xs"
                style={{ color: snapshotTokens.textMuted }}
              >
                No players match “{query.trim() || "…"}”.
              </li>
            ) : (
              options.map((player) => (
                <li key={player.player_id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={
                      player.player_id === value
                    }
                    className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-gray-50"
                    style={{
                      background:
                        player.player_id === value
                          ? snapshotTokens.blueLight
                          : "transparent",
                      color: snapshotTokens.textPrimary,
                    }}
                    onClick={() => {
                      onChange(player.player_id);
                      setQuery("");
                      setOpen(false);
                    }}
                  >
                    <span className="truncate font-medium">
                      {player.name}
                    </span>
                    <span
                      className="shrink-0 text-xs"
                      style={{
                        color: snapshotTokens.textMuted,
                      }}
                    >
                      {[player.position, player.team]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

export interface PlayerMultiSelectOption {
  player_id: string;
  name: string;
  position?: string | null;
  team?: string | null;
}

interface MultiProps {
  label: string;
  players: PlayerMultiSelectOption[];
  selectedIds: string[];
  onChange: (playerIds: string[]) => void;
}

export function SearchablePlayerMultiSelect({
  label,
  players,
  selectedIds,
  onChange,
}: MultiProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const selectedSet = useMemo(
    () => new Set(selectedIds),
    [selectedIds]
  );

  const selectedPlayers = useMemo(
    () =>
      players.filter((player) =>
        selectedSet.has(player.player_id)
      ),
    [players, selectedSet]
  );

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return [];
    }
    return players
      .filter((player) => !selectedSet.has(player.player_id))
      .filter((player) => {
        const haystack = [
          player.name,
          player.position,
          player.team,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(needle);
      })
      .sort((left, right) =>
        left.name.localeCompare(right.name, undefined, {
          sensitivity: "base",
        })
      )
      .slice(0, 40);
  }, [players, query, selectedSet]);

  const summary = (() => {
    if (selectedIds.length === 0) {
      return "All players";
    }
    if (selectedIds.length === 1) {
      return selectedPlayers[0]?.name || "1 selected";
    }
    return `${selectedIds.length} selected`;
  })();

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (
        rootRef.current
        && !rootRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener(
        "mousedown",
        onPointerDown
      );
    };
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  function toggle(playerId: string) {
    if (selectedSet.has(playerId)) {
      onChange(
        selectedIds.filter((id) => id !== playerId)
      );
      return;
    }
    onChange([...selectedIds, playerId]);
  }

  return (
    <div
      ref={rootRef}
      className="relative block min-w-[14rem] flex-1 text-sm"
    >
      <span
        className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </span>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-left"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textPrimary,
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate">{summary}</span>
        <ChevronDown className="h-4 w-4 shrink-0" />
      </button>

      {open && (
        <div
          className="absolute z-30 mt-1 w-full min-w-[18rem] overflow-hidden rounded-lg border bg-white shadow-lg"
          style={{ borderColor: snapshotTokens.border }}
        >
          <div
            className="flex items-center gap-2 border-b px-3 py-2"
            style={{ borderColor: snapshotTokens.divider }}
          >
            <Search
              className="h-4 w-4 shrink-0"
              style={{ color: snapshotTokens.textMuted }}
            />
            <input
              ref={inputRef}
              type="search"
              value={query}
              onChange={(event) =>
                setQuery(event.target.value)
              }
              placeholder="Search name, position, team…"
              className="w-full bg-transparent text-sm outline-none"
              style={{ color: snapshotTokens.textPrimary }}
              aria-label="Search players"
            />
          </div>
          {selectedIds.length > 0 && (
            <div
              className="flex border-b px-3 py-1.5"
              style={{ borderColor: snapshotTokens.divider }}
            >
              <button
                type="button"
                className="text-xs font-medium"
                style={{ color: snapshotTokens.textMuted }}
                onClick={() => onChange([])}
              >
                Clear
              </button>
            </div>
          )}
          <ul
            className="max-h-64 overflow-auto py-1"
            role="listbox"
            aria-multiselectable
          >
            {selectedPlayers.map((player) => (
              <PlayerOption
                key={player.player_id}
                player={player}
                checked
                onToggle={() => toggle(player.player_id)}
              />
            ))}
            {matches.map((player) => (
              <PlayerOption
                key={player.player_id}
                player={player}
                checked={false}
                onToggle={() => toggle(player.player_id)}
              />
            ))}
            {selectedPlayers.length === 0
              && matches.length === 0 && (
              <li
                className="px-3 py-2 text-xs"
                style={{ color: snapshotTokens.textMuted }}
              >
                {query.trim()
                  ? `No players match “${query.trim()}”.`
                  : "Search to add players. Leave empty to show everyone."}
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function PlayerOption({
  player,
  checked,
  onToggle,
}: {
  player: PlayerMultiSelectOption;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <li>
      <label
        className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-50"
        style={{
          background: checked
            ? snapshotTokens.blueLight
            : "transparent",
          color: snapshotTokens.textPrimary,
        }}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="rounded border-gray-300"
        />
        <span className="min-w-0 flex-1 truncate font-medium">
          {player.name}
        </span>
        <span
          className="shrink-0 text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          {[player.position, player.team]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </label>
    </li>
  );
}
