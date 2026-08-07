import { useState } from "react";

import {
  uploadDataset,
} from "@/services/api";

import { DatasetAnalysis } from "@/types/report";

export function useAnalysis() {
  const [analysis, setAnalysis] =
    useState<DatasetAnalysis | null>(null);

  const [brief, setBrief] =
    useState<any>(null);

  const [analysisLoading, setAnalysisLoading] =
    useState(false);

  const [briefLoading, setBriefLoading] =
    useState(false);

  async function upload(file: File) {
    setAnalysisLoading(true);

    try {
      const result =
        await uploadDataset(file);

      setAnalysis(result);

    } finally {
      setAnalysisLoading(false);
    }
  }

  return {
    analysis,
    brief,

    upload,

    analysisLoading,
    briefLoading,
  };
}