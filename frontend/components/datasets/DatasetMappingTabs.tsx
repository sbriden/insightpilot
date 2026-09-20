"use client";

import {
  useMemo,
  useState,
} from "react";

import {
  DataProductRequirement,
  ConceptIdentificationResult,
  DatasetField,
  FieldMapping,
  SemanticField,
  GrainDeterminationResult,
} from "@/types/dataset";

import DatasetFieldMapper from "@/components/datasets/DatasetFieldMapper";
import IdentifiedConceptsPanel from "@/components/datasets/IdentifiedConceptsPanel";
import AnalyticalCapabilitiesPanel from "@/components/datasets/AnalyticalCapabilitiesPanel";
import DatasetGrainPanel from "@/components/datasets/DatasetGrainPanel";
import { detectAnalyticalCapabilities } from "@/lib/detectAnalyticalCapabilities";


type MappingTabId =
  | "mapping"
  | "concepts"
  | "capabilities"
  | "grain";


interface Props {
  product: DataProductRequirement;

  uploadedFields: DatasetField[];

  mappings: FieldMapping[];

  semanticFields: SemanticField[];

  availableProducts: DataProductRequirement[];

  identifiedConcepts: ConceptIdentificationResult | null;

  grainResult?: GrainDeterminationResult | null;

  grainLoading?: boolean;

  onChange: (
    requiredField: string,
    uploadedField: string | null
  ) => void;

  onContinue: (
    mappings: FieldMapping[]
  ) => void;

  onBack: () => void;
}


export default function DatasetMappingTabs({
  product,
  uploadedFields,
  mappings,
  semanticFields,
  availableProducts,
  identifiedConcepts,
  grainResult = null,
  grainLoading = false,
  onChange,
  onContinue,
  onBack,
}: Props) {

  const [
    activeTab,
    setActiveTab,
  ] = useState<MappingTabId>(
    "mapping"
  );

  const safeMappings =
    Array.isArray(mappings)
      ? mappings
      : [];

  const canContinue =
    safeMappings.length > 0;

  const analyticalCapabilities =
    useMemo(
      () =>
        identifiedConcepts
          ? detectAnalyticalCapabilities(
              identifiedConcepts.concepts
            )
          : null,
      [identifiedConcepts]
    );


  return (
    <div className="space-y-6">

      <div>

        <p className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          Field Mapping
        </p>

        <h2 className="mt-1 text-2xl font-semibold">
          Map your dataset
        </h2>

        <p className="mt-2 max-w-2xl text-sm text-gray-600">
          Review how your uploaded columns map to
          shared semantic fields, then inspect the
          business concepts inferred from those columns.
        </p>

      </div>


      <div className="rounded-xl border bg-white">

        <div
          className="flex gap-2 border-b bg-gray-50 px-4 py-3"
          role="tablist"
          aria-label="Dataset mapping views"
        >

          <TabButton
            id="mapping"
            label="Mapping"
            selected={
              activeTab === "mapping"
            }
            onClick={() =>
              setActiveTab("mapping")
            }
          />

          <TabButton
            id="concepts"
            label="Business Concepts"
            selected={
              activeTab === "concepts"
            }
            onClick={() =>
              setActiveTab("concepts")
            }
          />

          <TabButton
            id="capabilities"
            label="Capabilities"
            selected={
              activeTab === "capabilities"
            }
            onClick={() =>
              setActiveTab("capabilities")
            }
          />

          <TabButton
            id="grain"
            label="Grain"
            selected={
              activeTab === "grain"
            }
            onClick={() =>
              setActiveTab("grain")
            }
          />

        </div>


        <div
          className="p-4 sm:p-6"
          role="tabpanel"
        >

          {activeTab === "mapping" ? (

            <DatasetFieldMapper
              product={product}
              uploadedFields={
                uploadedFields
              }
              mappings={mappings}
              semanticFields={
                semanticFields
              }
              availableProducts={
                availableProducts
              }
              onChange={onChange}
              onContinue={onContinue}
              onBack={onBack}
              embedded
              hideActions
            />

          ) : activeTab === "concepts" ? (

            identifiedConcepts ? (

              <IdentifiedConceptsPanel
                result={
                  identifiedConcepts
                }
                embedded
              />

            ) : (

              <p className="text-sm text-gray-500">
                Upload a dataset to identify business
                concepts from its columns.
              </p>

            )

          ) : activeTab === "capabilities" ? (

            analyticalCapabilities ? (

              <AnalyticalCapabilitiesPanel
                result={
                  analyticalCapabilities
                }
                embedded
              />

            ) : (

              <p className="text-sm text-gray-500">
                Upload a dataset to detect analytical
                capabilities from its business concepts.
              </p>

            )

          ) : grainLoading || grainResult ? (

            <DatasetGrainPanel
              result={
                grainResult ?? {
                  grain: "unknown",
                  label: "Unknown",
                  confidence: 0,
                  supporting_evidence: [],
                  explanation: "",
                  alternative_grains: [],
                  all_scores: [],
                }
              }
              embedded
              loading={grainLoading}
            />

          ) : (

            <p className="text-sm text-gray-500">
              Upload a dataset to determine its
              likely row grain.
            </p>

          )}

        </div>

      </div>


      <div className="flex items-center justify-between">

        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50"
        >
          ← Back
        </button>

        <button
          type="button"
          onClick={() =>
            onContinue(
              safeMappings
            )
          }
          disabled={!canContinue}
          className="rounded-lg bg-gray-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Continue →
        </button>

      </div>

    </div>
  );

}


function TabButton({
  id,
  label,
  selected,
  onClick,
}: {
  id: string;
  label: string;
  selected: boolean;
  onClick: () => void;
}) {

  return (
    <button
      type="button"
      role="tab"
      id={`tab-${id}`}
      aria-selected={selected}
      aria-controls={`panel-${id}`}
      onClick={onClick}
      className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
        selected
          ? "bg-gray-900 text-white"
          : "bg-white text-gray-700 ring-1 ring-gray-200 hover:bg-gray-100"
      }`}
    >
      {label}
    </button>
  );

}
