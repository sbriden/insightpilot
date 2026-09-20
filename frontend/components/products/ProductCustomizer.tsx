"use client";

import { useState } from "react";

import {
  DataProductConfiguration,
} from "@/types/report";


interface Dashboard {
  id: string;
  title?: string;
}


interface ProductCustomizerProps {
  configuration: DataProductConfiguration;

  dashboards: Dashboard[];

  onSave: (
    configuration: DataProductConfiguration
  ) => void;

  onClose: () => void;
}


export default function ProductCustomizer({
  configuration,
  dashboards,
  onSave,
  onClose,
}: ProductCustomizerProps) {

  const [draft, setDraft] =
    useState<DataProductConfiguration>(
      configuration
    );


  function toggleAnalysis(
    id: string
  ) {

    setDraft(current => {

      const exists =
        current.selectedAnalyses.includes(
          id
        );

      return {
        ...current,

        selectedAnalyses: exists
          ? current.selectedAnalyses.filter(
              analysisId =>
                analysisId !== id
            )
          : [
              ...current.selectedAnalyses,
              id,
            ],
      };

    });
  }


  function save() {

    onSave({
      ...draft,
      updatedAt:
        new Date().toISOString(),
    });

  }


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6">

      <div className="w-full max-w-2xl rounded-xl border bg-white p-6 shadow-xl">

        <div className="flex items-start justify-between">

          <div>

            <h2 className="text-xl font-semibold">
              Customize Data Product
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              Configure how this data product appears
              to users.
            </p>

          </div>

          <button
            onClick={onClose}
            className="text-sm text-gray-500"
          >
            Close
          </button>

        </div>


        {/* NAME */}

        <div className="mt-6">

          <label className="text-sm font-medium">
            Product Name
          </label>

          <input
            value={draft.name}
            onChange={event =>
              setDraft({
                ...draft,
                name:
                  event.target.value,
              })
            }
            className="mt-2 w-full rounded-lg border px-3 py-2 text-sm"
          />

        </div>


        {/* DESCRIPTION */}

        <div className="mt-5">

          <label className="text-sm font-medium">
            Description
          </label>

          <textarea
            value={draft.description}
            onChange={event =>
              setDraft({
                ...draft,
                description:
                  event.target.value,
              })
            }
            rows={3}
            className="mt-2 w-full rounded-lg border px-3 py-2 text-sm"
          />

        </div>


        {/* ANALYSES */}

        <div className="mt-6">

          <h3 className="text-sm font-semibold">
            Included Analyses
          </h3>

          <p className="mt-1 text-xs text-gray-500">
            Choose which analytical views appear
            in this product.
          </p>


          <div className="mt-3 space-y-2">

            {dashboards.map(
              dashboard => {

                const selected =
                  draft.selectedAnalyses.includes(
                    dashboard.id
                  );

                return (

                  <label
                    key={dashboard.id}
                    className="flex cursor-pointer items-center gap-3 rounded-lg border p-3"
                  >

                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() =>
                        toggleAnalysis(
                          dashboard.id
                        )
                      }
                    />

                    <span className="text-sm">
                      {dashboard.title ??
                        dashboard.id}
                    </span>

                  </label>

                );

              }
            )}

          </div>

        </div>


        {/* FOOTER */}

        <div className="mt-8 flex justify-end gap-3">

          <button
            onClick={onClose}
            className="rounded-lg border px-4 py-2 text-sm"
          >
            Cancel
          </button>

          <button
            onClick={save}
            className="rounded-lg bg-black px-4 py-2 text-sm text-white"
          >
            Save Changes
          </button>

        </div>

      </div>

    </div>
  );
}