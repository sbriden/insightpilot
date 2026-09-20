"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import AnalysisResults from "@/components/report/AnalysisResults";
import { useAnalysis } from "@/hooks/useAnalysis";

import DatasetTypeSelector from "@/components/datasets/DatasetTypeSelector";

import {
  getDatasetTypes,
  getDatasetTypeDataProducts,
  classifyDataset,
  determineDatasetGrain,
} from "@/services/api";

import {
  DatasetType,
  DataProductRequirement,
  DatasetField,
  FieldMapping,
  DatasetMappingResult,
  DataCoverageResult,
  SemanticField,
  ConceptIdentificationResult,
  DatasetTypeRecommendation,
  GrainDeterminationResult,
  DataSourceKind,
  FieldMapping,
  NflverseSelection,
  NflversePreviewResult,
} from "@/types/dataset";

import DataProductRequirements from "@/components/datasets/DataProductRequirements";
import DatasetMappingTabs from "@/components/datasets/DatasetMappingTabs";

import { readDatasetFields } from "@/lib/readDatasetFields";
import { mapDatasetFields } from "@/lib/fieldMapping";
import { identifyBusinessConcepts } from "@/lib/identifyBusinessConcepts";
import { buildSemanticFields } from "@/lib/semanticFields";
import { buildDatasetTypeRecommendation } from "@/lib/datasetTypeRecommendation";
import {
  loadFieldMappingsAsync,
  reuseFieldMappings,
  saveFieldMappingsAsync,
} from "@/lib/mappingMemory";

import UploadCard from "@/components/upload/UploadCard";
import DataSourcePicker from "@/components/datasets/DataSourcePicker";
import NflverseSourcePanel from "@/components/datasets/NflverseSourcePanel";

import CreateProductFlowProgress from "@/components/products/CreateProductFlowProgress";

import {
  CreateFlowStepId,
  getCreateFlowStepIndex,
  getCreateFlowSteps,
} from "@/lib/createProductFlow";


export default function CreateDataProductPage() {

  const [file, setFile] =
    useState<File | null>(null);

  const [
    sourceKind,
    setSourceKind,
  ] =
    useState<DataSourceKind>(
      "csv"
    );

  const [
    nflverseSelection,
    setNflverseSelection,
  ] =
    useState<NflverseSelection | null>(
      null
    );

  const [
    nflverseSampleRows,
    setNflverseSampleRows,
  ] =
    useState<Record<string, unknown>[]>(
      []
    );

  const [
    prebuiltMappings,
    setPrebuiltMappings,
  ] =
    useState<FieldMapping[]>(
      []
    );


  /* ------------------------------------------------------------------------
   * Dataset Type
   * ---------------------------------------------------------------------- */

  const [datasetTypes, setDatasetTypes] =
    useState<DatasetType[]>([]);

  const [
    selectedDatasetType,
    setSelectedDatasetType,
  ] =
    useState<DatasetType | null>(null);

  const [
    datasetTypesLoading,
    setDatasetTypesLoading,
  ] =
    useState(true);

  const [
    typeRecommendation,
    setTypeRecommendation,
  ] =
    useState<DatasetTypeRecommendation | null>(
      null
    );

  const [
    classificationLoading,
    setClassificationLoading,
  ] =
    useState(false);

  const [
    grainResult,
    setGrainResult,
  ] =
    useState<GrainDeterminationResult | null>(
      null
    );

  const [
    grainLoading,
    setGrainLoading,
  ] =
    useState(false);


  /* ------------------------------------------------------------------------
   * Data Products
   * ---------------------------------------------------------------------- */

  const [
    availableProducts,
    setAvailableProducts,
  ] =
    useState<DataProductRequirement[]>([]);

  const [
    selectedProductIds,
    setSelectedProductIds,
  ] =
    useState<string[]>([]);

  const [
    productsLoading,
    setProductsLoading,
  ] =
    useState(false);

  const [
    productCoverage,
    setProductCoverage,
  ] =
    useState<
      Record<string, DataCoverageResult>
    >({});


  /* ------------------------------------------------------------------------
   * Uploaded Dataset
   * ---------------------------------------------------------------------- */

  const [
    uploadedFields,
    setUploadedFields,
  ] =
    useState<DatasetField[]>([]);


  /* ------------------------------------------------------------------------
   * Shared Semantic Fields
   * ---------------------------------------------------------------------- */

  const [
    semanticFields,
    setSemanticFields,
  ] =
    useState<SemanticField[]>([]);


  /* ------------------------------------------------------------------------
   * Shared Field Mappings
   * ---------------------------------------------------------------------- */

  const [
    fieldMappings,
    setFieldMappings,
  ] =
    useState<FieldMapping[]>([]);

  const [
    showFieldMapper,
    setShowFieldMapper,
  ] =
    useState(false);

  const [
    mappingResult,
    setMappingResult,
  ] =
    useState<DatasetMappingResult | null>(null);

  const [
    mappingLoading,
    setMappingLoading,
  ] =
    useState(false);

  const [
    mappingComplete,
    setMappingComplete,
  ] =
    useState(false);

  const [
    mappingsReused,
    setMappingsReused,
  ] =
    useState(false);

  const [
    identifiedConcepts,
    setIdentifiedConcepts,
  ] =
    useState<ConceptIdentificationResult | null>(
      null
    );


  const [
    currentStepId,
    setCurrentStepId,
  ] =
    useState<CreateFlowStepId>(
      "upload"
    );

  const [
    maxReachableIndex,
    setMaxReachableIndex,
  ] =
    useState(0);


  const {
    analysis,
    brief,
    upload,
    analyzeFromNflverse,
    analysisLoading,
    briefLoading,
  } = useAnalysis();

  const hasActiveSource =
    Boolean(
      file ||
      nflverseSelection
    );

  const activeSourceLabel =
    file?.name ??
    nflverseSelection?.label ??
    null;

  const skipMappingStep =
    sourceKind === "nflverse" &&
    Boolean(
      nflverseSelection?.preMapped ??
      true
    ) &&
    Boolean(nflverseSelection);

  const flowSteps =
    getCreateFlowSteps({
      skipMapping:
        skipMappingStep,
    });


  /* ------------------------------------------------------------------------
   * Load Dataset Types
   * ---------------------------------------------------------------------- */

  useEffect(() => {

    async function loadDatasetTypes() {

      try {

        setDatasetTypesLoading(true);

        const result =
          await getDatasetTypes();

        setDatasetTypes(
          Array.isArray(result)
            ? result
            : []
        );

      } catch (error) {

        console.error(
          "Failed to load dataset types:",
          error
        );

        setDatasetTypes([]);

      } finally {

        setDatasetTypesLoading(false);

      }

    }

    loadDatasetTypes();

  }, []);


  /* ------------------------------------------------------------------------
   * Apply pending classification recommendation once catalog types load
   * ---------------------------------------------------------------------- */

  useEffect(() => {

    if (
      !typeRecommendation?.datasetTypeId ||
      selectedDatasetType ||
      datasetTypes.length === 0
    ) {
      return;
    }

    const recommendedType =
      datasetTypes.find(
        type =>
          type.id ===
          typeRecommendation.datasetTypeId
      );

    if (recommendedType) {

      setSelectedDatasetType(
        recommendedType
      );

    }

  }, [
    typeRecommendation,
    selectedDatasetType,
    datasetTypes,
  ]);


  /* ------------------------------------------------------------------------
   * Load Products
   * ---------------------------------------------------------------------- */

  useEffect(() => {

    async function loadProducts() {

      if (!selectedDatasetType) {

        setAvailableProducts([]);
        setSelectedProductIds([]);
        setSemanticFields([]);
        setProductCoverage({});

        return;

      }

      try {

        setProductsLoading(true);

        setSelectedProductIds([]);
        setSemanticFields([]);
        setProductCoverage({});

        const result =
          await getDatasetTypeDataProducts(
            selectedDatasetType.id
          );

        let products: any[] = [];

        if (Array.isArray(result)) {

          products = result;

        } else if (
          result &&
          Array.isArray(result.products)
        ) {

          products =
            result.products;

        } else if (
          result &&
          Array.isArray(result.data_products)
        ) {

          products =
            result.data_products;

        }

        const normalizedProducts =
          normalizeProducts(products);

        setAvailableProducts(
          normalizedProducts
        );

        // Curated nflverse path: default to Fantasy Football product.
        if (
          sourceKind === "nflverse"
          || selectedDatasetType.id === "fantasy_football"
        ) {
          const fantasyProduct =
            normalizedProducts.find(
              (product) =>
                product.id === "fantasy_football"
            );
          if (fantasyProduct) {
            setSelectedProductIds([
              fantasyProduct.id,
            ]);
          }
        }

        const sharedSemanticFields =
          buildSemanticFields(
            normalizedProducts
          );

        setSemanticFields(
          sharedSemanticFields
        );

      } catch (error) {

        console.error(
          "Failed to load data products:",
          error
        );

        setAvailableProducts([]);
        setSemanticFields([]);

      } finally {

        setProductsLoading(false);

      }

    }

    loadProducts();

  }, [selectedDatasetType, sourceKind]);


  function advanceToStep(
    stepId: CreateFlowStepId
  ) {

    const index =
      getCreateFlowStepIndex(
        stepId,
        flowSteps
      );

    if (index < 0) {
      return;
    }

    setCurrentStepId(stepId);
    setMaxReachableIndex(
      current =>
        Math.max(
          current,
          index
        )
    );

  }


  function goToStep(
    stepId: CreateFlowStepId,
    index: number
  ) {

    if (
      index >
      maxReachableIndex
    ) {
      return;
    }

    /*
     * Navigating to Products via the progress bar should behave like
     * Continue on the mapping step: accept the current mappings and
     * mark mapping complete so product selection is available.
     */
    if (
      stepId === "products" &&
      hasActiveSource &&
      uploadedFields.length > 0 &&
      fieldMappings.length > 0
    ) {

      applyCompletedMappings(
        fieldMappings,
        uploadedFields,
        {
          reused: mappingsReused,
        }
      );

      return;

    }

    setCurrentStepId(stepId);

    if (
      stepId === "mapping" &&
      hasActiveSource &&
      uploadedFields.length > 0 &&
      semanticFields.length > 0
    ) {

      setShowFieldMapper(true);

    } else if (
      stepId !== "mapping"
    ) {

      setShowFieldMapper(false);

    }

  }


  useEffect(() => {

    if (
      analysis &&
      !analysisLoading
    ) {

      advanceToStep("results");

    }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    analysis,
    analysisLoading,
  ]);


  /* ------------------------------------------------------------------------
   * Normalize Products
   * ---------------------------------------------------------------------- */

  function normalizeProducts(
    products: any[]
  ): DataProductRequirement[] {

    if (!Array.isArray(products)) {
      return [];
    }

    return products.map(
      (product) => ({

        id:
          String(
            product?.id ?? ""
          ),

        name:
          String(
            product?.name ??
            "Unnamed Data Product"
          ),

        description:
          String(
            product?.description ??
            ""
          ),

        business_purpose:
          product?.business_purpose,

        dataset_types:
          Array.isArray(
            product?.dataset_types
          )
            ? product.dataset_types
            : [],

        grain:
          String(
            product?.grain ??
            "Not specified"
          ),

        required_fields:
          Array.isArray(
            product?.required_fields
          )
            ? product.required_fields
            : [],

        optional_fields:
          Array.isArray(
            product?.optional_fields
          )
            ? product.optional_fields
            : [],

        analyses:
          Array.isArray(
            product?.analyses
          )
            ? product.analyses
            : [],

        field_opportunities:
          Array.isArray(
            product?.field_opportunities
          )
            ? product.field_opportunities
            : [],

      })
    );

  }


  /* ------------------------------------------------------------------------
   * Dataset Type Selection
   * ---------------------------------------------------------------------- */

  function handleDatasetTypeSelect(
    datasetType: DatasetType
  ) {

    setSelectedDatasetType(
      datasetType
    );

    setSelectedProductIds([]);

    setFieldMappings([]);

    setMappingResult(null);

    setMappingComplete(false);

    setShowFieldMapper(false);

    setProductCoverage({});

    setMappingsReused(false);

  }


  async function prepareMappingsForDatasetType(
    datasetType: DatasetType,
    fields: DatasetField[],
    nextSemanticFields: SemanticField[]
  ) {

    /*
     * Curated connectors (nflverse) ship with canonical
     * column names and prebuilt identity mappings.
     */
    if (
      nflverseSelection?.preMapped &&
      prebuiltMappings.length > 0
    ) {

      applyCompletedMappings(
        prebuiltMappings,
        fields,
        {
          reused: false,
          prebuilt: true,
        }
      );

      return true;

    }

    if (
      nextSemanticFields.length === 0
    ) {

      alert(
        "No semantic fields are available for this dataset type."
      );

      return false;

    }

    const saved =
      await loadFieldMappingsAsync(
        datasetType.id
      );

    const reused =
      saved
        ? reuseFieldMappings(
            saved,
            fields,
            nextSemanticFields
          )
        : null;

    if (
      reused &&
      reused.some(
        mapping =>
          !!mapping.uploadedField
      )
    ) {

      applyCompletedMappings(
        reused,
        fields,
        {
          reused: true,
        }
      );

      return true;

    }

    const mappings =
      mapDatasetFields(
        fields,
        nextSemanticFields
      );

    const normalizedMappings =
      Array.isArray(mappings)
        ? mappings
        : [];

    setFieldMappings(
      normalizedMappings
    );

    updateIdentifiedConcepts(
      fields,
      normalizedMappings
    );

    setShowFieldMapper(
      true
    );

    advanceToStep("mapping");

    return true;

  }


  async function handleDatasetTypeContinue() {

    if (
      !selectedDatasetType ||
      !hasActiveSource ||
      uploadedFields.length === 0
    ) {
      return;
    }

    if (productsLoading) {
      return;
    }

    try {

      setMappingLoading(true);

      await prepareMappingsForDatasetType(
        selectedDatasetType,
        uploadedFields,
        semanticFields
      );

    } catch (error) {

      console.error(
        "Failed to map dataset fields:",
        error
      );

      alert(
        "Unable to prepare field mappings for this dataset type."
      );

    } finally {

      setMappingLoading(false);

    }

  }


  function updateIdentifiedConcepts(
    fields: DatasetField[],
    mappings: FieldMapping[] = []
  ) {

    setIdentifiedConcepts(
      identifyBusinessConcepts(
        fields,
        undefined,
        mappings
      )
    );

  }


  /* ------------------------------------------------------------------------
   * Product Selection
   * ---------------------------------------------------------------------- */

  function handleProductSelect(
    product: DataProductRequirement
  ) {

    setSelectedProductIds(
      current => {

        if (
          current.includes(
            product.id
          )
        ) {

          return current.filter(
            id =>
              id !== product.id
          );

        }

        return [
          ...current,
          product.id,
        ];

      }
    );

  }


  /* ------------------------------------------------------------------------
   * Calculate Product Coverage
   *
   * IMPORTANT:
   *
   * Coverage is calculated independently for each product.
   *
   * A field being required by Product A does NOT make it globally required.
   * ---------------------------------------------------------------------- */

  function calculateProductCoverage(
    product: DataProductRequirement,
    mappings: FieldMapping[]
  ): DataCoverageResult {

    const safeMappings =
      Array.isArray(mappings)
        ? mappings
        : [];


    const requiredFields =
      Array.isArray(
        product.required_fields
      )
        ? product.required_fields
        : [];


    const optionalFields =
      Array.isArray(
        product.optional_fields
      )
        ? product.optional_fields
        : [];


    const mappedRequiredFields =
      requiredFields.filter(
        field =>
          safeMappings.some(
            mapping =>
              mapping.requiredField === field &&
              !!mapping.uploadedField
          )
      );


    const missingRequiredFields =
      requiredFields.filter(
        field =>
          !mappedRequiredFields.includes(
            field
          )
      );


    const availableOptionalFields =
      optionalFields.filter(
        field =>
          safeMappings.some(
            mapping =>
              mapping.requiredField === field &&
              !!mapping.uploadedField
          )
      );


    const missingOptionalFields =
      optionalFields.filter(
        field =>
          !availableOptionalFields.includes(
            field
          )
      );


    const requiredFieldCount =
      requiredFields.length;


    const mappedRequiredCount =
      mappedRequiredFields.length;


    const optionalFieldCount =
      optionalFields.length;


    const availableOptionalCount =
      availableOptionalFields.length;


    const requiredCoveragePercent =
      requiredFieldCount === 0
        ? 100
        : Math.round(
            (
              mappedRequiredCount /
              requiredFieldCount
            ) *
            100
          );


    /*
     * Product coverage = share of this product's
     * field contract the dataset satisfies.
     * Required fields gate analysis; optional
     * fields deepen support.
     */

    const totalFields =
      requiredFieldCount +
      optionalFieldCount;


    const availableFields =
      mappedRequiredCount +
      availableOptionalCount;


    const coveragePercent =
      totalFields === 0
        ? 100
        : Math.round(
            (
              availableFields /
              totalFields
            ) *
            100
          );


    const missingFields = [
      ...missingRequiredFields,
      ...missingOptionalFields,
    ];


    const opportunityDefinitions =
      product.field_opportunities ?? [];


    const opportunities =
      missingFields.map(
        field => {

          const definition =
            opportunityDefinitions.find(
              opportunity =>
                opportunity.field === field
            );

          if (definition) {
            return definition;
          }

          return {
            field,

            description:
              "Adding this field improves support for this data product.",

            analyses: [] as string[],

            metrics: [] as string[],

            priority: "medium" as const,

            required:
              missingRequiredFields.includes(
                field
              ),
          };

        }
      );


    return {

      product_id:
        product.id,

      product_name:
        product.name,

      coverage_percent:
        coveragePercent,

      required_coverage_percent:
        requiredCoveragePercent,

      required_fields:
        requiredFields,

      mapped_required_fields:
        mappedRequiredFields,

      missing_required_fields:
        missingRequiredFields,

      available_optional_fields:
        availableOptionalFields,

      missing_optional_fields:
        missingOptionalFields,

      opportunities,

      can_analyze:
        missingRequiredFields.length === 0,

      metadata: {

        required_field_count:
          requiredFieldCount,

        mapped_required_count:
          mappedRequiredCount,

        optional_field_count:
          optionalFieldCount,

        available_optional_count:
          availableOptionalCount,

        opportunity_count:
          opportunities.length,

        total_field_count:
          totalFields,

        available_field_count:
          availableFields,

      },

    };

  }


  /* ------------------------------------------------------------------------
   * Build Product Coverage Map
   * ---------------------------------------------------------------------- */

  function buildProductCoverageMap(
    mappings: FieldMapping[]
  ) {

    const coverageMap:
      Record<
        string,
        DataCoverageResult
      > = {};


    const safeMappings =
      Array.isArray(mappings)
        ? mappings
        : [];


    for (
      const product
      of availableProducts
    ) {

      coverageMap[
        product.id
      ] =
        calculateProductCoverage(
          product,
          safeMappings
        );

    }


    return coverageMap;

  }


  /* ------------------------------------------------------------------------
   * Apply Completed Mappings
   * ---------------------------------------------------------------------- */

  function applyCompletedMappings(
    normalizedMappings: FieldMapping[],
    fields: DatasetField[],
    options: {
      reused?: boolean;
      prebuilt?: boolean;
    } = {}
  ) {

    if (
      normalizedMappings.length === 0
    ) {

      alert(
        "No field mappings were received. Please review the field mappings and try again."
      );

      return false;

    }

    const mappedFields =
      normalizedMappings.filter(
        mapping =>
          !!mapping.uploadedField
      );

    const overallCoverage =
      normalizedMappings.length === 0
        ? 0
        : Math.round(
            (
              mappedFields.length /
              normalizedMappings.length
            ) *
            100
          );

    const coverageMap =
      buildProductCoverageMap(
        normalizedMappings
      );

    setFieldMappings(
      normalizedMappings
    );

    updateIdentifiedConcepts(
      fields,
      normalizedMappings
    );

    setProductCoverage(
      coverageMap
    );

    setMappingResult({
      datasetType:
        selectedDatasetType?.id ?? "",

      mappings:
        normalizedMappings,

      requiredFields: [],

      optionalFields:
        normalizedMappings.map(
          mapping =>
            mapping.requiredField
        ),

      matchedRequiredFields: [],

      matchedOptionalFields:
        mappedFields.map(
          mapping =>
            mapping.requiredField
        ),

      missingRequiredFields: [],

      availableOptionalFields:
        mappedFields.map(
          mapping =>
            mapping.requiredField
        ),

      requiredCoverage: 100,

      overallCoverage,

      canAnalyze: true,
    });

    setMappingComplete(true);

    setShowFieldMapper(false);

    setMappingsReused(
      !!options.reused
    );

    if (
      selectedDatasetType?.id &&
      !options.prebuilt
    ) {

      void saveFieldMappingsAsync(
        selectedDatasetType.id,
        fields,
        normalizedMappings
      );

    }

    advanceToStep("products");

    return true;

  }


  /* ------------------------------------------------------------------------
   * Mapping Continue
   *
   * IMPORTANT:
   *
   * We no longer validate "required" fields here.
   *
   * Required status belongs to individual products, not the shared dataset
   * mapping.
   * ---------------------------------------------------------------------- */

  function handleMappingContinue(
    mappings:
      | FieldMapping[]
      | {
          mappings?: FieldMapping[];
        }
  ) {

    const normalizedMappings:
      FieldMapping[] =
      Array.isArray(mappings)
        ? mappings
        : Array.isArray(
            mappings?.mappings
          )
          ? mappings.mappings
          : [];

    applyCompletedMappings(
      normalizedMappings,
      uploadedFields,
      {
        reused: false,
      }
    );

  }



  /* ------------------------------------------------------------------------
   * Shared source → fields pipeline
   * ---------------------------------------------------------------------- */

  async function applySourceFields(
    fields: DatasetField[],
    options: {
      advanceToDatasetType?: boolean;
    } = {}
  ) {

    const shouldAdvance =
      options.advanceToDatasetType !== false;

    setUploadedFields(
      fields
    );

    setFieldMappings([]);

    setMappingResult(null);

    setMappingComplete(false);

    setShowFieldMapper(false);

    setProductCoverage({});

    setSelectedProductIds([]);

    setMappingsReused(false);

    setIdentifiedConcepts(null);

    setTypeRecommendation(null);

    setGrainResult(null);

    setSelectedDatasetType(null);

    try {

      setMappingLoading(true);

      setClassificationLoading(true);

      setGrainLoading(true);

      const conceptsResult =
        identifyBusinessConcepts(
          fields
        );

      setIdentifiedConcepts(
        conceptsResult
      );


      try {

        const [
          classificationOutcome,
          grainOutcome,
        ] = await Promise.allSettled([
          classifyDataset(
            conceptsResult.concepts
          ),
          determineDatasetGrain(
            conceptsResult.concepts
          ),
        ]);

        if (
          grainOutcome.status ===
          "fulfilled"
        ) {

          setGrainResult(
            grainOutcome.value
          );

        } else {

          console.error(
            "Failed to determine dataset grain:",
            grainOutcome.reason
          );

          setGrainResult(null);

        }

        if (
          classificationOutcome.status ===
          "fulfilled"
        ) {

          const recommendation =
            buildDatasetTypeRecommendation(
              classificationOutcome.value
            );

          setTypeRecommendation(
            recommendation
          );

          if (
            recommendation.datasetTypeId
          ) {

            const recommendedType =
              datasetTypes.find(
                type =>
                  type.id ===
                  recommendation.datasetTypeId
              );

            if (recommendedType) {

              setSelectedDatasetType(
                recommendedType
              );

            }

          }

        } else {

          console.error(
            "Failed to classify dataset:",
            classificationOutcome.reason
          );

          setTypeRecommendation(null);

        }

      } finally {

        setClassificationLoading(
          false
        );

        setGrainLoading(false);

      }

      if (shouldAdvance) {
        advanceToStep("dataset-type");
      }

    } catch (error) {

      console.error(
        "Failed to prepare dataset fields:",
        error
      );

      alert(
        "Unable to prepare the dataset fields."
      );

      setClassificationLoading(false);

      throw error;

    } finally {

      setMappingLoading(false);

    }

  }


  /* ------------------------------------------------------------------------
   * File Upload
   * ---------------------------------------------------------------------- */

  async function handleFileChange(
    nextFile: File | null
  ) {

    setFile(nextFile);
    setNflverseSelection(null);


    if (!nextFile) {

      setUploadedFields([]);
      return;

    }


    try {

      const fields =
        await readDatasetFields(
          nextFile
        );

      await applySourceFields(
        fields
      );

    } catch (error) {

      console.error(
        "Failed to read dataset fields:",
        error
      );

      alert(
        "Unable to read the dataset fields."
      );

      setFile(null);

    }

  }


  async function handleNflverseLoaded(
    selection: NflverseSelection,
    fields: DatasetField[],
    nextPrebuiltMappings: FieldMapping[] = [],
    nextSampleRows: Record<string, unknown>[] = [],
    _preview?: NflversePreviewResult
  ) {

    setFile(null);
    setNflverseSelection({
      ...selection,
      preMapped:
        selection.preMapped ?? true,
    });
    setPrebuiltMappings(
      nextPrebuiltMappings
    );
    setNflverseSampleRows(
      nextSampleRows
    );

    // Prefer Fantasy Football for curated nflverse sources.
    const fantasyType =
      datasetTypes.find(
        (type) => type.id === "fantasy_football"
      );
    if (fantasyType) {
      setTypeRecommendation({
        datasetTypeId: "fantasy_football",
        confidence: 0.9,
        label: "Fantasy Football",
        explanation:
          "Curated nflverse fantasy football source.",
        confidenceByTypeId: {
          fantasy_football: 0.9,
        },
      });
      setSelectedDatasetType(fantasyType);
    }

    try {

      await applySourceFields(
        fields,
        {
          advanceToDatasetType: false,
        }
      );

      setFieldMappings(
        nextPrebuiltMappings
      );
      setMappingComplete(
        nextPrebuiltMappings.length > 0
      );

    } catch (error) {

      setNflverseSelection(null);
      setPrebuiltMappings([]);
      setNflverseSampleRows([]);
      setMappingComplete(false);

    }

  }


  function handleNflverseClear() {

    setNflverseSelection(null);
    setNflverseSampleRows([]);
    setPrebuiltMappings([]);
    setUploadedFields([]);
    setFieldMappings([]);
    setMappingResult(null);
    setMappingComplete(false);
    setShowFieldMapper(false);
    setProductCoverage({});
    setSelectedProductIds([]);
    setMappingsReused(false);
    setIdentifiedConcepts(null);
    setTypeRecommendation(null);
    setGrainResult(null);
    setSelectedDatasetType(null);

  }


  function handleSourceKindChange(
    kind: DataSourceKind
  ) {

    setSourceKind(kind);
    setFile(null);
    setNflverseSelection(null);
    setNflverseSampleRows([]);
    setPrebuiltMappings([]);
    setUploadedFields([]);
    setFieldMappings([]);
    setMappingResult(null);
    setMappingComplete(false);
    setShowFieldMapper(false);
    setProductCoverage({});
    setSelectedProductIds([]);
    setMappingsReused(false);
    setIdentifiedConcepts(null);
    setTypeRecommendation(null);
    setGrainResult(null);
    setSelectedDatasetType(null);

  }


  /* ------------------------------------------------------------------------
   * Analyze
   * ---------------------------------------------------------------------- */

  async function analyze() {

    if (!hasActiveSource) {

      alert(
        "Please select a dataset first."
      );

      return;

    }


    if (!selectedDatasetType) {

      alert(
        "Please select a dataset type first."
      );

      return;

    }


    if (
      selectedProductIds.length === 0
    ) {

      alert(
        "Please select at least one data product."
      );

      return;

    }


    if (!mappingComplete) {

      alert(
        "Please complete field mapping before analyzing."
      );

      return;

    }


    const unavailableProducts =
      selectedProductIds.filter(
        productId =>
          !productCoverage[
            productId
          ]?.can_analyze
      );


    if (
      unavailableProducts.length > 0
    ) {

      const productNames =
        unavailableProducts
          .map(
            productId =>
              availableProducts.find(
                product =>
                  product.id ===
                  productId
              )?.name
          )
          .filter(Boolean);


      alert(
        `The following selected products are missing required fields:\n\n${productNames.join(
          "\n"
        )}`
      );

      return;

    }


    console.log(
      "Starting dataset analysis:",
      {
        source:
          activeSourceLabel,

        datasetType:
          selectedDatasetType.id,

        products:
          selectedProductIds,

        mappings:
          fieldMappings,

      }
    );


    advanceToStep("results");

    if (nflverseSelection) {

      await analyzeFromNflverse(
        nflverseSelection,
        fieldMappings,
        selectedProductIds
      );

    } else if (file) {

      await upload(
        file,
        fieldMappings,
        selectedProductIds
      );

    }

  }


  /* ------------------------------------------------------------------------
   * Render
   * ---------------------------------------------------------------------- */

  const stepDescriptions: Record<
    CreateFlowStepId,
    {
      title: string;
      description: string;
    }
  > = {
    upload: {
      title: "Choose a data source",
      description:
        "Upload a CSV or connect to nflverse. Curated sources include a data preview and arrive with fields already mapped.",
    },
    "dataset-type": {
      title: "Confirm dataset type",
      description:
        "Review InsightPilot’s recommendation, then confirm or choose a different dataset type.",
    },
    mapping: {
      title: "Map your fields",
      description:
        "Confirm how your dataset columns map to the shared semantic fields used by your data products.",
    },
    products: {
      title: "Select your data products",
      description:
        "Choose one or more analytical products to generate from your dataset.",
    },
    results: {
      title: "Your data products",
      description:
        "Review each product below. Results are saved under Data Products for later.",
    },
  };

  const activeStepMeta =
    stepDescriptions[currentStepId];


  return (

    <main className="min-h-screen p-10">

      <div className="mx-auto max-w-6xl">

        <div>

          <Link
            href="/"
            className="text-sm text-gray-500 hover:underline"
          >
            ← Data Products
          </Link>

          <h1 className="mt-4 text-3xl font-bold">
            Create data product
          </h1>

          <p className="mt-2 max-w-2xl text-gray-600">
            Choose a data source, map your fields, and
            generate new analytical products.
          </p>

        </div>


        <div className="mt-8">

          <CreateProductFlowProgress
            steps={flowSteps}
            currentStepId={currentStepId}
            maxReachableIndex={
              maxReachableIndex
            }
            onStepClick={goToStep}
          />

        </div>


        <section className="mt-8">

          <div className="mb-6">

            <h2 className="text-2xl font-semibold">
              {activeStepMeta.title}
            </h2>

            <p className="mt-2 max-w-2xl text-sm text-gray-600">
              {activeStepMeta.description}
            </p>

          </div>


          {currentStepId === "upload" && (

            <>

              <DataSourcePicker
                selected={sourceKind}
                disabled={
                  mappingLoading ||
                  classificationLoading ||
                  analysisLoading
                }
                onSelect={
                  handleSourceKindChange
                }
              />

              {sourceKind === "csv" ? (

                <UploadCard
                  file={file}
                  loading={
                    mappingLoading ||
                    classificationLoading ||
                    analysisLoading
                  }
                  onFileChange={
                    handleFileChange
                  }
                />

              ) : (

                <NflverseSourcePanel
                  loading={
                    mappingLoading ||
                    classificationLoading ||
                    analysisLoading
                  }
                  selection={
                    nflverseSelection
                  }
                  sampleRows={
                    nflverseSampleRows
                  }
                  onLoaded={
                    handleNflverseLoaded
                  }
                  onClear={
                    handleNflverseClear
                  }
                />

              )}

              {hasActiveSource &&
                uploadedFields.length > 0 && (
                <div className="mt-8 flex justify-end">

                  <button
                    type="button"
                    disabled={
                      classificationLoading
                    }
                    onClick={() =>
                      advanceToStep(
                        "dataset-type"
                      )
                    }
                    className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Continue
                  </button>

                </div>
              )}

            </>

          )}


          {currentStepId ===
            "dataset-type" && (

            <>

              {!hasActiveSource ||
              uploadedFields.length === 0 ? (

                <div className="rounded-xl border bg-white p-6 text-sm text-gray-500">
                  Choose a data source first so InsightPilot can recommend a type.
                </div>

              ) : datasetTypesLoading ? (

                <div className="rounded-xl border bg-white p-6">

                  <p className="text-sm text-gray-500">
                    Loading dataset types...
                  </p>

                </div>

              ) : (

                <DatasetTypeSelector
                  datasetTypes={
                    datasetTypes
                  }
                  selectedType={
                    selectedDatasetType?.id ??
                    null
                  }
                  onSelect={
                    handleDatasetTypeSelect
                  }
                  recommendedTypeId={
                    typeRecommendation?.datasetTypeId ??
                    null
                  }
                  confidenceByTypeId={
                    typeRecommendation?.confidenceByTypeId ??
                    {}
                  }
                  recommendationExplanation={
                    typeRecommendation?.explanation ??
                    null
                  }
                  recommendationLoading={
                    classificationLoading
                  }
                />

              )}


              <div className="mt-8 flex justify-between gap-3">

                <button
                  type="button"
                  onClick={() =>
                    goToStep(
                      "upload",
                      getCreateFlowStepIndex(
                        "upload",
                        flowSteps
                      )
                    )
                  }
                  className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Back
                </button>

                <button
                  type="button"
                  disabled={
                    !selectedDatasetType ||
                    productsLoading ||
                    mappingLoading ||
                    classificationLoading ||
                    !hasActiveSource ||
                    uploadedFields.length === 0
                  }
                  onClick={
                    handleDatasetTypeContinue
                  }
                  className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {productsLoading ||
                  mappingLoading
                    ? "Preparing…"
                    : "Continue"}
                </button>

              </div>

            </>

          )}


          {currentStepId === "mapping" &&
            !skipMappingStep &&
            hasActiveSource &&
            uploadedFields.length > 0 &&
            semanticFields.length > 0 && (

            <DatasetMappingTabs
              product={{
                id: "dataset_type_mapping",
                name:
                  selectedDatasetType?.name ??
                  "Dataset",
                description:
                  "Shared dataset field mapping",
                dataset_types:
                  selectedDatasetType
                    ? [
                        selectedDatasetType.id,
                      ]
                    : [],
                grain: "Dataset",
                required_fields: [],
                optional_fields:
                  semanticFields.map(
                    field =>
                      field.field
                  ),
                analyses: [],
              }}
              uploadedFields={
                uploadedFields
              }
              mappings={fieldMappings}
              semanticFields={
                semanticFields
              }
              availableProducts={
                availableProducts
              }
              identifiedConcepts={
                identifiedConcepts
              }
              grainResult={
                grainResult
              }
              grainLoading={
                grainLoading
              }
              onChange={(
                requiredField,
                uploadedField
              ) => {
                setFieldMappings(
                  current => {

                    const next =
                      current.map(
                        mapping => {
                          if (
                            mapping.requiredField !==
                            requiredField
                          ) {
                            return mapping;
                          }
                          return {
                            ...mapping,
                            uploadedField,
                            matchType:
                              uploadedField
                                ? "manual"
                                : "missing",
                            confidence:
                              uploadedField
                                ? 1
                                : 0,
                            valid:
                              !!uploadedField,
                          };
                        }
                      );

                    updateIdentifiedConcepts(
                      uploadedFields,
                      next
                    );

                    return next;

                  }
                );
              }}
              onContinue={
                handleMappingContinue
              }
              onBack={() => {
                setShowFieldMapper(false);
                goToStep(
                  "dataset-type",
                  getCreateFlowStepIndex(
                    "dataset-type",
                    flowSteps
                  )
                );
              }}
            />

          )}


          {currentStepId === "mapping" &&
            skipMappingStep && (

            <div className="rounded-xl border bg-white p-6 text-sm text-gray-500">
              This curated data source ships with fields already mapped.
              Continue to products.
            </div>

          )}

          {currentStepId === "mapping" &&
            !skipMappingStep &&
            (!hasActiveSource ||
              uploadedFields.length === 0 ||
              semanticFields.length === 0) && (

            <div className="rounded-xl border bg-white p-6 text-sm text-gray-500">
              Choose a data source and confirm its type to map fields.
            </div>

          )}


          {currentStepId === "products" &&
            mappingComplete &&
            selectedDatasetType && (

            <>

              {mappingsReused && (

                <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white px-5 py-4">

                  <div>

                    <p className="text-sm font-medium">
                      Field mappings reused
                    </p>

                    <p className="mt-1 text-sm text-gray-500">
                      Your previous {selectedDatasetType.name} mappings
                      were applied because this file’s columns are
                      compatible.
                    </p>

                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      setShowFieldMapper(true);
                      advanceToStep("mapping");
                    }}
                    className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50"
                  >
                    Review mappings
                  </button>

                </div>

              )}


              {productsLoading ? (

                <div className="rounded-xl border bg-white p-6">

                  <p className="text-sm text-gray-500">
                    Loading available data products...
                  </p>

                </div>

              ) : (

                <DataProductRequirements
                  products={
                    availableProducts
                  }
                  selectedProductIds={
                    selectedProductIds
                  }
                  onSelect={
                    handleProductSelect
                  }
                  productCoverage={
                    productCoverage
                  }
                />

              )}


              <div className="mt-8 flex items-center justify-between rounded-xl border bg-white p-6">

                <div>

                  <p className="font-medium">

                    {selectedProductIds.length === 0

                      ? "No products selected"

                      : `${selectedProductIds.length} product${
                          selectedProductIds.length === 1
                            ? ""
                            : "s"
                        } selected`}

                  </p>

                  <p className="mt-1 text-sm text-gray-500">
                    Select the products you want
                    InsightPilot to analyze.
                  </p>

                </div>


                <button
                  type="button"
                  onClick={analyze}
                  disabled={
                    analysisLoading ||
                    selectedProductIds.length === 0 ||
                    selectedProductIds.some(
                      productId =>
                        !productCoverage[
                          productId
                        ]?.can_analyze
                    )
                  }
                  className="rounded-lg bg-gray-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {analysisLoading
                    ? "Analyzing..."
                    : "Analyze selected products"}
                </button>

              </div>

            </>

          )}


          {currentStepId === "products" &&
            (!mappingComplete ||
              !selectedDatasetType) && (

            <div className="rounded-xl border bg-white p-6 text-sm text-gray-500">
              Complete field mapping before selecting products.
            </div>

          )}


          {currentStepId === "results" &&
            analysisLoading && (

            <div className="rounded-xl border bg-white p-6">

              <div className="flex items-center gap-3">

                <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-gray-900" />

                <div>

                  <p className="font-medium">
                    Analyzing your dataset...
                  </p>

                  <p className="mt-1 text-sm text-gray-500">
                    Running semantic profiling, fantasy
                    signal findings, and AI explanations.
                    This can take a moment on first run.
                  </p>

                </div>

              </div>

            </div>

          )}


          {currentStepId === "results" &&
            analysis &&
            !analysisLoading && (

            <AnalysisResults
              result={analysis}
            />

          )}


          {currentStepId === "results" &&
            !analysis &&
            !analysisLoading && (

            <div className="rounded-xl border bg-white p-6 text-sm text-gray-500">
              Run an analysis to see your generated data products.
            </div>

          )}

        </section>

      </div>

    </main>

  );

}