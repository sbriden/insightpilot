"use client";

import { ReactNode } from "react";

import { DataProduct } from "@/types/report";

import {
  ProductGroup,
} from "@/lib/productLineage";


interface Props {
  group: ProductGroup;
  selectedVersionId?: string;
  onVersionChange: (
    versionId: string
  ) => void;
  children: (
    product: DataProduct
  ) => ReactNode;
}


export default function ProductVersionSection({
  group,
  selectedVersionId,
  onVersionChange,
  children,
}: Props) {

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
    <section className="rounded-xl border bg-white">

      <div className="border-b px-6 py-4">

        <div className="flex flex-wrap items-start justify-between gap-4">

          <div>

            <h2 className="text-lg font-semibold">
              {group.name}
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              {group.description}
            </p>

          </div>


          {group.versionCount > 1 && (

            <div className="min-w-[180px] space-y-2">

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
                className="w-full rounded-lg border bg-white px-3 py-2 text-sm"
              >
                {group.versions.map(
                  (version) => (

                    <option
                      key={version.id}
                      value={version.id}
                    >
                      v{version.version}
                      {version.id ===
                      group.latest.id
                        ? " (latest)"
                        : ""}
                    </option>

                  )
                )}
              </select>

            </div>

          )}

        </div>

        {group.versionCount === 1 && (

          <p className="mt-3 text-xs text-gray-400">
            Version {activeProduct.version}
          </p>

        )}

      </div>


      {children(activeProduct)}

    </section>
  );

}
