import Link from "next/link";

import PipelineDag from "@/components/refresh/PipelineDag";
import type { RefreshJob, RefreshPipeline } from "@/lib/refreshJobs";

interface RefreshJobCardProps {
  job: RefreshJob;
  pipeline: RefreshPipeline;
  lastRefreshed: string | null;
  lastStatus?: string | null;
  loading: boolean;
  disabled: boolean;
  onRun: () => void;
}

export default function RefreshJobCard({
  job,
  pipeline,
  lastRefreshed,
  lastStatus,
  loading,
  disabled,
  onRun,
}: RefreshJobCardProps) {
  return (
    <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-gray-900">
              {job.title}
            </h3>
            <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600">
              {job.cadence}
            </span>
          </div>
          <p className="mt-1.5 max-w-2xl text-sm text-gray-600">
            {job.summary}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <LastRefreshed
            value={lastRefreshed}
            status={lastStatus}
          />
          <button
            type="button"
            disabled={disabled}
            onClick={onRun}
            className="rounded-lg bg-gray-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {loading ? "Running…" : "Run refresh"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
            Tables updated
          </p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {job.tables.map((table) => (
              <li
                key={table}
                className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 font-mono text-[11px] text-gray-700"
              >
                {table}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
            Dependent products
          </p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {job.products.map((product) => (
              <li key={product.id}>
                <Link
                  href={product.href}
                  className="inline-flex rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-sm font-medium text-amber-950 hover:bg-amber-100"
                >
                  {product.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-4 border-t border-gray-100 pt-3">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
          Pipeline path
        </p>
        <PipelineDag
          pipeline={pipeline}
          activeStages={job.layers}
          compact
        />
      </div>
    </article>
  );
}

function LastRefreshed({
  value,
  status,
}: {
  value: string | null;
  status?: string | null;
}) {
  return (
    <div className="text-right">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
        Last refreshed
      </p>
      <p className="mt-0.5 text-sm font-medium text-gray-900">
        {value ? formatTimestamp(value) : "Never"}
      </p>
      {status ? (
        <p className="mt-0.5 text-[11px] capitalize text-gray-500">
          {status.replaceAll("_", " ")}
        </p>
      ) : null}
    </div>
  );
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
