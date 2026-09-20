"use client";

import {
  useEffect,
  useState,
} from "react";

import {
  Button,
} from "@/components/ui/button";

import DatasetPreviewTable from "@/components/datasets/DatasetPreviewTable";

import {
  getNflverseCatalog,
  previewNflverseDataset,
  refreshNflverseData,
} from "@/services/api";

import {
  DatasetField,
  FieldMapping,
  NflverseCatalog,
  NflversePreviewResult,
  NflverseSelection,
} from "@/types/dataset";


interface NflverseSourcePanelProps {
  loading: boolean;
  selection: NflverseSelection | null;
  sampleRows: Record<string, unknown>[];
  onLoaded: (
    selection: NflverseSelection,
    fields: DatasetField[],
    prebuiltMappings: FieldMapping[],
    sampleRows: Record<string, unknown>[],
    preview: NflversePreviewResult
  ) => void;
  onClear: () => void;
}


export default function NflverseSourcePanel({
  loading,
  selection,
  sampleRows,
  onLoaded,
  onClear,
}: NflverseSourcePanelProps) {

  const [
    catalog,
    setCatalog,
  ] =
    useState<NflverseCatalog | null>(
      null
    );

  const [
    catalogLoading,
    setCatalogLoading,
  ] =
    useState(true);

  const [
    catalogError,
    setCatalogError,
  ] =
    useState<string | null>(
      null
    );

  const [
    datasetId,
    setDatasetId,
  ] =
    useState("fantasy_signal");

  const [
    season,
    setSeason,
  ] =
    useState<number | null>(
      null
    );

  const [
    seasonMode,
    setSeasonMode,
  ] =
    useState<
      "historical" | "current" | "single"
    >(
      "historical"
    );

  const [
    refreshLoading,
    setRefreshLoading,
  ] =
    useState(false);

  const [
    previewLoading,
    setPreviewLoading,
  ] =
    useState(false);

  const [
    previewError,
    setPreviewError,
  ] =
    useState<string | null>(
      null
    );

  const [
    refreshMessage,
    setRefreshMessage,
  ] =
    useState<string | null>(
      null
    );

  const [
    refreshStatus,
    setRefreshStatus,
  ] =
    useState<string | null>(
      null
    );


  useEffect(() => {

    async function loadCatalog() {

      try {

        setCatalogLoading(true);
        setCatalogError(null);

        const result =
          await getNflverseCatalog();

        setCatalog(result);

        setSeason(
          result.current_season
        );

        if (
          result.datasets.length > 0
        ) {

          setDatasetId(
            result.datasets[0].id
          );

        }

      } catch (error) {

        console.error(
          "Failed to load nflverse catalog:",
          error
        );

        setCatalogError(
          error instanceof Error
            ? error.message
            : "Unable to load nflverse datasets."
        );

      } finally {

        setCatalogLoading(false);

      }

    }

    loadCatalog();

  }, []);


  async function handleLoad() {

    if (!datasetId || season == null) {
      return;
    }

    const seasons =
      seasonMode === "historical"
        ? (catalog?.historical_seasons ?? [])
        : seasonMode === "current"
          ? [catalog?.current_season ?? season]
          : [season];

    if (seasons.length === 0) {
      return;
    }

    try {

      setPreviewLoading(true);
      setPreviewError(null);

      const preview =
        await previewNflverseDataset(
          datasetId,
          seasons
        );

      onLoaded(
        {
          datasetId:
            preview.dataset_id,
          datasetName:
            preview.dataset_name,
          seasons:
            preview.seasons,
          label:
            preview.label,
          preMapped:
            preview.pre_mapped,
          rowCount:
            preview.row_count,
        },
        preview.fields,
        preview.prebuilt_mappings ?? [],
        preview.sample_rows ?? [],
        preview
      );

    } catch (error) {

      console.error(
        "Failed to preview nflverse dataset:",
        error
      );

      setPreviewError(
        error instanceof Error
          ? error.message
          : "Unable to load the selected nflverse dataset."
      );

    } finally {

      setPreviewLoading(false);

    }

  }


  async function handleRefresh(
    scope: "historical" | "current" | "reprocess"
  ) {

    try {

      setRefreshLoading(true);
      setPreviewError(null);
      setRefreshMessage(null);
      setRefreshStatus(null);

      const mode =
        scope === "current"
          ? "incremental"
          : scope;

      const result =
        await refreshNflverseData(mode);

      const message =
        result.message
        ?? result.validation?.message
        ?? "The data loaded successfully and passed validation.";

      setRefreshMessage(message);
      setRefreshStatus(
        result.status
        ?? result.validation?.status
        ?? "succeeded"
      );

      if (
        result.status !== "failed_validation"
        && result.validation?.passed !== false
      ) {
        // Reload the selected dataset after a valid refresh.
        await handleLoad();
      }

    } catch (error) {

      console.error(
        "Failed to refresh nflverse data:",
        error
      );

      setRefreshMessage(null);
      setRefreshStatus(null);
      setPreviewError(
        error instanceof Error
          ? error.message
          : "Unable to refresh nflverse data."
      );

    } finally {

      setRefreshLoading(false);

    }

  }


  const selectedDataset =
    catalog?.datasets.find(
      dataset =>
        dataset.id === datasetId
    );


  if (catalogLoading) {

    return (
      <div className="mt-6 rounded-lg border bg-white px-4 py-6 text-sm text-gray-500">
        Loading nflverse datasets...
      </div>
    );

  }


  if (catalogError || !catalog) {

    return (
      <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
        {catalogError ??
          "nflverse catalog unavailable."}
      </div>
    );

  }


  if (selection) {

    return (
      <div className="mt-6 space-y-4">

        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-gray-50 px-4 py-3">

          <div className="min-w-0">

            <p className="truncate text-sm font-medium text-gray-900">
              {selection.label}
            </p>

            <p className="mt-1 text-xs text-gray-500">
              Pre-mapped curated source
              {typeof selection.rowCount === "number"
                ? ` · ${selection.rowCount.toLocaleString()} rows`
                : ""}
            </p>

          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading || previewLoading}
            onClick={onClear}
          >
            Change dataset
          </Button>

        </div>

        <DatasetPreviewTable
          rows={sampleRows}
          totalRowCount={selection.rowCount}
        />

      </div>
    );

  }


  return (
    <div className="mt-6 space-y-4 rounded-lg border bg-white p-5">

      <div>

        {selectedDataset?.domain_label && (
          <p className="mb-3 text-xs font-medium uppercase tracking-wide text-gray-500">
            {selectedDataset.domain_label}
          </p>
        )}

        <label className="text-sm font-medium text-gray-900">
          Dataset
        </label>

        <select
          className="mt-2 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
          value={datasetId}
          disabled={loading || previewLoading}
          onChange={(event) =>
            setDatasetId(
              event.target.value
            )
          }
        >

          {catalog.datasets.map(
            (dataset) => (
              <option
                key={dataset.id}
                value={dataset.id}
              >
                {dataset.name}
              </option>
            )
          )}

        </select>

        {selectedDataset && (
          <p className="mt-2 text-xs text-gray-500">
            {selectedDataset.description}
            {selectedDataset.notes
              ? ` ${selectedDataset.notes}`
              : ""}
          </p>
        )}

      </div>


      {selectedDataset?.supports_seasons !== false && (

        <div className="space-y-3">

          <div>

            <label className="text-sm font-medium text-gray-900">
              Season scope
            </label>

            <select
              className="mt-2 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
              value={seasonMode}
              disabled={
                loading ||
                previewLoading ||
                refreshLoading
              }
              onChange={(event) =>
                setSeasonMode(
                  event.target.value as
                    | "historical"
                    | "current"
                    | "single"
                )
              }
            >
              <option value="historical">
                Historical (
                {catalog.historical_season_count
                  ?? 4}{" "}
                seasons)
              </option>
              <option value="current">
                Current season (
                {catalog.current_season})
              </option>
              <option value="single">
                Single season
              </option>
            </select>

            <p className="mt-2 text-xs text-gray-500">
              Historical load seeds several seasons.
              Incremental updates the live season only.
              Reprocess rebuilds derived metrics from
              stored facts when logic changes.
            </p>

          </div>

          {seasonMode === "single" && (

            <div>

              <label className="text-sm font-medium text-gray-900">
                Season
              </label>

              <select
                className="mt-2 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
                value={season ?? ""}
                disabled={
                  loading ||
                  previewLoading ||
                  refreshLoading
                }
                onChange={(event) =>
                  setSeason(
                    Number(
                      event.target.value
                    )
                  )
                }
              >

                {[...catalog.available_seasons]
                  .reverse()
                  .slice(0, 20)
                  .map(
                    (value) => (
                      <option
                        key={value}
                        value={value}
                      >
                        {value}
                      </option>
                    )
                  )}

              </select>

            </div>

          )}

        </div>

      )}


      {previewError && (
        <p className="text-sm text-red-600">
          {previewError}
        </p>
      )}

      {refreshMessage && (
        <p
          className={
            refreshStatus === "failed_validation"
              || refreshStatus === "failed"
              ? "text-sm text-red-700"
              : refreshStatus === "succeeded_with_warnings"
                || refreshStatus === "passed_with_warnings"
                ? "text-sm text-amber-700"
                : "text-sm text-teal-800"
          }
        >
          {refreshMessage}
        </p>
      )}


      <div className="flex flex-wrap justify-end gap-2">

        <Button
          type="button"
          variant="outline"
          disabled={
            loading ||
            previewLoading ||
            refreshLoading
          }
          onClick={() =>
            void handleRefresh("historical")
          }
        >
          {refreshLoading
            ? "Running…"
            : "Historical load"}
        </Button>

        <Button
          type="button"
          variant="outline"
          disabled={
            loading ||
            previewLoading ||
            refreshLoading
          }
          onClick={() =>
            void handleRefresh("current")
          }
        >
          Incremental update
        </Button>

        <Button
          type="button"
          variant="outline"
          disabled={
            loading ||
            previewLoading ||
            refreshLoading
          }
          onClick={() =>
            void handleRefresh("reprocess")
          }
        >
          Reprocess derived
        </Button>

        <Button
          type="button"
          disabled={
            loading ||
            previewLoading ||
            refreshLoading ||
            season == null
          }
          onClick={handleLoad}
        >
          {previewLoading
            ? "Loading dataset..."
            : "Load dataset"}
        </Button>

      </div>

      <p className="text-xs text-gray-500">
        Fantasy football foundation from{" "}
        <a
          href="https://nflverse.nflverse.com/"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          nflverse
        </a>
        . Fields arrive pre-mapped with a universal{" "}
        <span className="font-medium text-gray-700">
          player_id
        </span>{" "}
        (gsis_id).
      </p>

    </div>
  );

}
