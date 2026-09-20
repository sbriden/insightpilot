"use client";

import {
  useState,
} from "react";

import {
  ChevronDown,
  GitBranch,
} from "lucide-react";

import {
  ProductChangeSummary,
} from "@/types/report";

import CollapsibleVersionComparison from "@/components/products/CollapsibleVersionComparison";

import {
  Button,
} from "@/components/ui/button";

import {
  cn,
} from "@/lib/utils";


interface ProductVersion {
  id: string;
  version: number;
  updated_at?: string;
  created_at?: string;
}


interface Props {
  versions?: ProductVersion[];
  selectedVersionId?: string;
  currentVersion: number;
  coverage: number;
  latestVersion: number;
  changeSummary?: ProductChangeSummary | null;
  onVersionChange: (
    versionId: string
  ) => void;
  formatVersionDate?: (
    version: ProductVersion
  ) => string;
}


export default function ProductVersionCoveragePanel({
  versions = [],
  selectedVersionId = "",
  currentVersion,
  coverage,
  latestVersion,
  changeSummary,
  onVersionChange,
  formatVersionDate,
}: Props) {

  const [
    expanded,
    setExpanded,
  ] = useState(false);

  const isLatest =
    currentVersion === latestVersion;

  const summaryText =
    `v${currentVersion}${
      isLatest ? " (latest)" : ""
    } · ${coverage}% field coverage`;

  const compactLabel =
    `v${currentVersion} · ${coverage}%`;


  return (
    <div className="relative">

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() =>
          setExpanded(
            current => !current
          )
        }
        aria-expanded={expanded}
        title={summaryText}
        aria-label={summaryText}
        className="h-7 gap-1 px-2 text-xs"
      >

        <GitBranch
          className="size-3.5 shrink-0"
          aria-hidden
        />

        <span className="max-w-[7rem] truncate sm:max-w-none">
          {compactLabel}
        </span>

        <ChevronDown
          className={cn(
            "size-3.5 shrink-0 text-muted-foreground transition-transform",
            expanded && "rotate-180"
          )}
          aria-hidden
        />

      </Button>


      {expanded && (

        <>
          <button
            type="button"
            aria-label="Close version and coverage panel"
            className="fixed inset-0 z-20 cursor-default"
            onClick={() =>
              setExpanded(false)
            }
          />


          <div className="absolute right-0 top-full z-30 mt-2 w-80 space-y-4 rounded-lg border bg-white p-4 shadow-lg">

            {versions.length > 0 && (

              <div className="space-y-2">

                <label
                  htmlFor="product-version"
                  className="block text-xs font-semibold uppercase tracking-wide text-gray-400"
                >
                  Version
                </label>


                <div className="flex flex-wrap items-center gap-3">

                  <select
                    id="product-version"
                    value={selectedVersionId}
                    onChange={(event) =>
                      onVersionChange(
                        event.target.value
                      )
                    }
                    className="min-w-0 flex-1 rounded-lg border bg-white px-3 py-2 text-sm"
                  >

                    {versions.map(
                      (version) => (

                        <option
                          key={version.id}
                          value={version.id}
                        >
                          v{version.version}
                          {version.version === latestVersion
                            ? " (latest)"
                            : ""}
                          {formatVersionDate?.(
                            version
                          ) ?? ""}
                        </option>

                      )
                    )}

                  </select>


                  <span className="text-sm text-gray-500">
                    {versions.length}{" "}
                    {versions.length === 1
                      ? "version"
                      : "versions"}
                  </span>

                </div>

              </div>

            )}


            <div>

              <div className="flex justify-between text-sm">

                <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Field coverage
                </span>


                <span className="font-medium">
                  {coverage}%
                </span>

              </div>


              <div className="mt-2 h-2 rounded-full bg-gray-200">

                <div
                  className="h-full rounded-full bg-gray-900"
                  style={{
                    width:
                      `${Math.min(
                        Math.max(
                          Number(
                            coverage ?? 0
                          ),
                          0
                        ),
                        100
                      )}%`,
                  }}
                />

              </div>

            </div>


            {changeSummary && (

              <CollapsibleVersionComparison
                variant="dropdown"
                changeSummary={changeSummary}
              />

            )}

          </div>

        </>

      )}

    </div>

  );

}
