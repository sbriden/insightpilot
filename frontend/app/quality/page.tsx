"use client";

import {
  useEffect,
  useState,
} from "react";

import Link from "next/link";

import DatasetQualityCard from "@/components/datasets/DatasetQualityCard";
import DatasetQualityModal from "@/components/datasets/DatasetQualityModal";
import FantasyDataQualityCard from "@/components/datasets/FantasyDataQualityCard";
import FantasyDataQualityModal from "@/components/datasets/FantasyDataQualityModal";

import { useSavedProducts } from "@/hooks/useSavedProducts";

import {
  DatasetGroup,
  groupProductsByUploadBatch,
} from "@/lib/productLineage";

import {
  getNflverseDataQuality,
} from "@/services/api";

import {
  NflverseDataQualityResult,
} from "@/types/dataset";


export default function QualityPage() {

  const {
    products,
    loaded,
    error,
  } = useSavedProducts();

  const [
    selectedDataset,
    setSelectedDataset,
  ] = useState<DatasetGroup | null>(
    null
  );

  const [
    fantasyQuality,
    setFantasyQuality,
  ] = useState<
    NflverseDataQualityResult | null
  >(null);

  const [
    fantasyLoading,
    setFantasyLoading,
  ] = useState(true);

  const [
    fantasyError,
    setFantasyError,
  ] = useState<string | null>(null);

  const [
    selectedFantasy,
    setSelectedFantasy,
  ] = useState(false);

  const datasets =
    groupProductsByUploadBatch(
      products
    );

  useEffect(() => {

    let cancelled = false;

    async function loadFantasyQuality() {
      try {
        setFantasyLoading(true);
        setFantasyError(null);
        const result =
          await getNflverseDataQuality(true);
        if (!cancelled) {
          setFantasyQuality(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setFantasyError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load fantasy data quality."
          );
        }
      } finally {
        if (!cancelled) {
          setFantasyLoading(false);
        }
      }
    }

    void loadFantasyQuality();

    return () => {
      cancelled = true;
    };

  }, []);

  if (!loaded && fantasyLoading) {
    return null;
  }

  return (
    <div className="mx-auto max-w-7xl">

      <h1 className="text-3xl font-bold">
        Data Quality
      </h1>

      <p className="mt-2 text-gray-600">
        Ingestion validation for fantasy football and
        completeness for uploaded datasets. Click a
        card for details.
      </p>

      <div className="mt-8">

        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          Foundation sources
        </h2>

        <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">

          {fantasyLoading ? (

            <div className="rounded-xl border bg-white p-4 text-sm text-gray-500">
              Loading fantasy football checks…
            </div>

          ) : fantasyError ? (

            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {fantasyError}
            </div>

          ) : fantasyQuality ? (

            <FantasyDataQualityCard
              result={fantasyQuality}
              onClick={() =>
                setSelectedFantasy(true)
              }
            />

          ) : null}

        </div>

      </div>

      <div className="mt-10">

        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          Uploaded datasets
        </h2>

        {error ? (

          <div className="mt-3 rounded-xl border bg-white p-6 text-sm text-red-600">
            {error}
          </div>

        ) : datasets.length === 0 ? (

          <div className="mt-3 rounded-xl border bg-white p-6 text-sm text-gray-500">

            <p>
              No saved datasets yet. Create a data
              product to capture dataset quality.
            </p>

            <Link
              href="/create"
              className="mt-4 inline-block text-sm font-medium text-gray-900 underline underline-offset-4"
            >
              Create data product
            </Link>

          </div>

        ) : (

          <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">

            {datasets.map((dataset) => (

              <DatasetQualityCard
                key={dataset.uploadBatchId}
                dataset={dataset}
                onClick={() =>
                  setSelectedDataset(
                    dataset
                  )
                }
              />

            ))}

          </div>

        )}

      </div>


      {selectedDataset && (

        <DatasetQualityModal
          dataset={selectedDataset}
          onClose={() =>
            setSelectedDataset(null)
          }
        />

      )}


      {selectedFantasy && fantasyQuality && (

        <FantasyDataQualityModal
          result={fantasyQuality}
          onClose={() =>
            setSelectedFantasy(false)
          }
        />

      )}

    </div>

  );

}
