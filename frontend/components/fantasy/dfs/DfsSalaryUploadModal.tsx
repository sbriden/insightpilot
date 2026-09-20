"use client";

import { useRef, useState } from "react";

import {
  DfsContestType,
  DfsSalaryUploadResult,
  DfsSiteId,
  uploadDfsSalaries,
} from "@/services/api";

interface Props {
  open: boolean;
  defaultSeason?: number | null;
  onClose: () => void;
  onUploaded?: (result: DfsSalaryUploadResult) => void;
}

export default function DfsSalaryUploadModal({
  open,
  defaultSeason,
  onClose,
  onUploaded,
}: Props) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [site, setSite] = useState<DfsSiteId>("draftkings");
  const [contestType, setContestType] =
    useState<DfsContestType>("classic");
  const [season, setSeason] = useState(
    defaultSeason != null ? String(defaultSeason) : ""
  );
  const [week, setWeek] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] =
    useState<DfsSalaryUploadResult | null>(null);

  if (!open) {
    return null;
  }

  async function handleUpload() {
    if (!file) {
      setError("Choose a DK or FD salary CSV first.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setResult(null);
      const uploaded = await uploadDfsSalaries({
        file,
        site,
        contestType,
        season: season.trim()
          ? Number(season)
          : null,
        week: week.trim() ? Number(week) : null,
      });
      setResult(uploaded);
      onUploaded?.(uploaded);
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload salary CSV."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Upload DFS salaries
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Import a DraftKings or FanDuel player-pool CSV.
              Salaries are matched on team/position with a fuzzy
              name match and saved for reuse.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-gray-500 hover:bg-gray-100"
          >
            Close
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-gray-700">
                Site
              </span>
              <select
                value={site}
                onChange={(event) =>
                  setSite(event.target.value as DfsSiteId)
                }
                className="w-full rounded-lg border border-gray-200 px-3 py-2"
              >
                <option value="draftkings">DraftKings</option>
                <option value="fanduel">FanDuel</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-gray-700">
                Contest
              </span>
              <select
                value={contestType}
                onChange={(event) =>
                  setContestType(
                    event.target.value as DfsContestType
                  )
                }
                className="w-full rounded-lg border border-gray-200 px-3 py-2"
              >
                <option value="classic">Classic</option>
                <option value="showdown">Showdown</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-gray-700">
                Season
              </span>
              <input
                type="number"
                value={season}
                onChange={(event) =>
                  setSeason(event.target.value)
                }
                placeholder="Current"
                className="w-full rounded-lg border border-gray-200 px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-gray-700">
                Week
              </span>
              <input
                type="number"
                value={week}
                onChange={(event) =>
                  setWeek(event.target.value)
                }
                placeholder="Current"
                className="w-full rounded-lg border border-gray-200 px-3 py-2"
              />
            </label>
          </div>

          <div>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(event) => {
                const next = event.target.files?.[0] ?? null;
                setFile(next);
                setResult(null);
                setError(null);
              }}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="w-full rounded-lg border border-dashed border-gray-300 px-4 py-6 text-sm text-gray-600 hover:border-gray-400 hover:bg-gray-50"
            >
              {file
                ? file.name
                : "Choose salary CSV…"}
            </button>
          </div>

          {error && (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          {result && (
            <div className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-900">
              <p>
                Matched {result.matched} of{" "}
                {result.rows_parsed} rows
                ({result.persisted} saved) for{" "}
                {result.site} {result.contest_type} ·{" "}
                {result.season} week {result.week}.
              </p>
              {result.unmatched > 0 && (
                <p className="mt-1 text-teal-800">
                  {result.unmatched} unmatched
                  {result.unmatched_samples?.[0]?.name
                    ? ` (e.g. ${result.unmatched_samples[0].name})`
                    : ""}
                  .
                </p>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            {result ? "Done" : "Cancel"}
          </button>
          <button
            type="button"
            disabled={loading || !file}
            onClick={() => void handleUpload()}
            className="rounded-lg bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {loading ? "Uploading…" : "Upload & save"}
          </button>
        </div>
      </div>
    </div>
  );
}
