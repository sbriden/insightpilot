import { useState } from "react";

import {
  uploadDataset,
  analyzeNflverseDataset,
} from "@/services/api";

import {
  DatasetAnalysis,
} from "@/types/report";

import {
  FieldMapping,
  NflverseSelection,
} from "@/types/dataset";


export function useAnalysis() {

  const [
    analysis,
    setAnalysis,
  ] =
    useState<DatasetAnalysis | null>(
      null
    );


  const [
    brief,
    setBrief,
  ] =
    useState<any>(null);


  const [
    analysisLoading,
    setAnalysisLoading,
  ] =
    useState(false);


  const [
    briefLoading,
    setBriefLoading,
  ] =
    useState(false);


  async function runAnalysis(
    result: DatasetAnalysis
  ) {

    console.log(
      "FULL ANALYSIS:",
      result
    );


    console.log(
      "DATA PRODUCTS:",
      result.data_products
    );


    setAnalysis(
      result
    );


    /*
     * Clear any previous executive brief.
     *
     * A new analysis should not accidentally
     * display a brief generated from the
     * previous dataset/product selection.
     */

    setBrief(
      null
    );


    return result;

  }


  async function upload(
    file: File,
    mappings: FieldMapping[] = [],
    productIds: string[] = []
  ) {

    setAnalysisLoading(true);

    try {

      console.log(
        "Starting analysis with mappings:",
        mappings
      );

      console.log(
        "Selected product IDs:",
        productIds
      );


      if (
        productIds.length === 0
      ) {

        throw new Error(
          "At least one data product must be selected."
        );

      }


      /*
       * Send the complete list of selected
       * products to the API.
       *
       * Results are persisted server-side.
       * Do not store the full analysis payload
       * in sessionStorage — dashboards exceed
       * browser storage quotas.
       */

      const result =
        await uploadDataset(
          file,
          mappings,
          productIds
        );


      return await runAnalysis(
        result
      );

    } catch (error) {

      console.error(
        "Analysis failed:",
        error
      );

      throw error;

    } finally {

      setAnalysisLoading(
        false
      );

    }

  }


  async function analyzeFromNflverse(
    selection: NflverseSelection,
    mappings: FieldMapping[] = [],
    productIds: string[] = []
  ) {

    setAnalysisLoading(true);

    try {

      if (
        productIds.length === 0
      ) {

        throw new Error(
          "At least one data product must be selected."
        );

      }

      const result =
        await analyzeNflverseDataset(
          selection.datasetId,
          selection.seasons,
          mappings,
          productIds
        );

      return await runAnalysis(
        result
      );

    } catch (error) {

      console.error(
        "nflverse analysis failed:",
        error
      );

      throw error;

    } finally {

      setAnalysisLoading(
        false
      );

    }

  }


  return {

    analysis,

    brief,

    upload,

    analyzeFromNflverse,

    analysisLoading,

    briefLoading,

  };

}
