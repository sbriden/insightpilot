"use client";

import {
  ReactNode,
  useState,
} from "react";

import PrioritySummaryBadges from "@/components/products/PrioritySummaryBadges";

import {
  ProductGroup,
} from "@/lib/productLineage";

import {
  PriorityCounts,
} from "@/lib/prioritySummary";

import {
  DataProduct,
} from "@/types/report";


interface Props {
  group: ProductGroup;
  selectedVersionId?: string;
  onVersionChange: (
    versionId: string
  ) => void;
  priorityCounts: PriorityCounts;
  emptyLabel?: string;
  defaultExpanded?: boolean;
  children: (
    product: DataProduct
  ) => ReactNode;
}


export default function CollapsibleProductGroup({
  group,
  selectedVersionId,
  onVersionChange,
  priorityCounts,
  emptyLabel,
  defaultExpanded = false,
  children,
}: Props) {

  const [
    expanded,
    setExpanded,
  ] = useState(defaultExpanded);

  const activeVersionId =
    selectedVersionId ??
    group.latest.id;

  const activeProduct =
    group.versions.find(
      version =>
        version.id ===
        activeVersionId
    ) ?? group.latest;


  return (
    <section className="overflow-hidden rounded-xl border bg-white">

      <div className="border-b">

        <button
          type="button"
          onClick={() =>
            setExpanded(
              current => !current
            )
          }
          aria-expanded={expanded}
          className="flex w-full items-start justify-between gap-4 px-6 py-4 text-left hover:bg-gray-50"
        >

          <div className="min-w-0 flex-1">

            <div className="flex flex-wrap items-center gap-3">

              <h2 className="text-lg font-semibold text-gray-950">
                {group.name}
              </h2>

              <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
                v{activeProduct.version}
                {activeProduct.id === group.latest.id
                  ? " · latest"
                  : ""}
              </span>

            </div>

            <p className="mt-1 text-sm text-gray-500">
              {group.description}
            </p>

            <div className="mt-3">

              <PrioritySummaryBadges
                counts={priorityCounts}
                emptyLabel={emptyLabel}
              />

            </div>

          </div>


          <span
            className={`mt-1 shrink-0 text-sm text-gray-400 transition-transform ${
              expanded
                ? "rotate-180"
                : ""
            }`}
            aria-hidden
          >
            ▼
          </span>

        </button>


        {expanded &&
          group.versionCount > 1 && (

            <div
              className="space-y-2 border-t px-6 py-4"
              onClick={(event) =>
                event.stopPropagation()
              }
            >

              <label
                htmlFor={`version-${group.definitionId}`}
                className="block text-xs font-semibold uppercase tracking-wide text-gray-400"
              >
                Version
              </label>

              <select
                id={`version-${group.definitionId}`}
                value={activeProduct.id}
                onChange={(event) =>
                  onVersionChange(
                    event.target.value
                  )
                }
                className="w-full max-w-xs rounded-lg border bg-white px-3 py-2 text-sm"
              >

                {group.versions.map(
                  (version) => (

                    <option
                      key={version.id}
                      value={version.id}
                    >
                      v{version.version}
                      {version.id === group.latest.id
                        ? " (latest)"
                        : ""}
                    </option>

                  )
                )}

              </select>

            </div>

          )}

      </div>


      {expanded && (

        <div>
          {children(activeProduct)}
        </div>

      )}

    </section>

  );

}
