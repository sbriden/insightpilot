"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";
import { ChevronDown } from "lucide-react";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";

/** Sentinel used when Clear deselects every option. */
export const MULTI_SELECT_NONE = "__none__";

interface Props {
  label: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
  emptyMeansAll?: boolean;
}

export default function MultiSelectFilter({
  label,
  options,
  selected,
  onChange,
  emptyMeansAll = true,
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

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

  const isCleared =
    selected.length === 1
    && selected[0] === MULTI_SELECT_NONE;
  const allSelected =
    options.length > 0
    && selected.length === options.length
    && !isCleared;
  const noneSelected = selected.length === 0;
  const treatAsAll =
    emptyMeansAll && noneSelected && !isCleared;

  const summary = (() => {
    if (isCleared) {
      return "None";
    }
    if (treatAsAll || allSelected) {
      return "All";
    }
    if (selected.length === 0) {
      return "None";
    }
    if (selected.length === 1) {
      return selected[0];
    }
    return `${selected.length} selected`;
  })();

  function toggle(option: string) {
    const base = isCleared
      ? []
      : selected.filter((value) => value !== MULTI_SELECT_NONE);
    if (base.includes(option)) {
      onChange(base.filter((value) => value !== option));
      return;
    }
    onChange([...base, option]);
  }

  function selectAll() {
    onChange(emptyMeansAll ? [] : [...options]);
  }

  function clear() {
    // Deselect every option (distinct from "All" / emptyMeansAll).
    onChange([MULTI_SELECT_NONE]);
  }

  return (
    <div ref={rootRef} className="relative block min-w-[8.5rem] text-sm">
      <span
        className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </span>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex w-full items-center justify-between gap-2 rounded-lg border bg-white px-2.5 py-2 text-sm"
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
          className="absolute z-30 mt-1 max-h-64 w-56 overflow-auto rounded-lg border bg-white py-1 shadow-lg"
          style={{ borderColor: snapshotTokens.border }}
          role="listbox"
          aria-multiselectable
        >
          <div
            className="flex gap-2 border-b px-2.5 py-1.5"
            style={{ borderColor: snapshotTokens.divider }}
          >
            <button
              type="button"
              className="text-xs font-medium"
              style={{ color: snapshotTokens.blue }}
              onClick={selectAll}
            >
              All
            </button>
            <button
              type="button"
              className="text-xs font-medium"
              style={{ color: snapshotTokens.textMuted }}
              onClick={clear}
            >
              Clear
            </button>
          </div>
          {options.length === 0 ? (
            <p
              className="px-3 py-2 text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              No options
            </p>
          ) : (
            options.map((option) => {
              const checked = treatAsAll
                ? true
                : !isCleared && selected.includes(option);
              return (
                <label
                  key={option}
                  className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-50"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      if (treatAsAll) {
                        onChange(
                          options.filter(
                            (value) => value !== option
                          )
                        );
                        return;
                      }
                      if (isCleared) {
                        onChange([option]);
                        return;
                      }
                      toggle(option);
                    }}
                    className="rounded border-gray-300"
                  />
                  <span
                    style={{
                      opacity: checked ? 1 : 0.55,
                    }}
                  >
                    {option}
                  </span>
                </label>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
