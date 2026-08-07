"use client";

import { useState } from "react";

import UploadCard from "@/components/upload/UploadCard";
import AnalysisResults from "@/components/report/AnalysisResults";

import { useAnalysis } from "@/hooks/useAnalysis";

export default function Home() {
  const [file, setFile] =
    useState<File | null>(null);

  const {
    analysis,
    brief,

    upload,

    analysisLoading,
    briefLoading,
  } = useAnalysis();

  async function analyze() {
    if (!file) return;

    await upload(file);
  }

  return (
    <main className="min-h-screen p-10">

      <h1 className="text-4xl font-bold">
        InsightPilot
      </h1>

      <p className="mt-4 text-gray-600">
        Upload your data and generate AI-powered insights.
      </p>

      <UploadCard
        file={file}
        loading={analysisLoading}
        onFileChange={setFile}
        onAnalyze={analyze}
      />

      {analysisLoading && (
        <p className="mt-6">
          Analyzing...
        </p>
      )}

      {analysis && (
        <div className="mt-8 rounded border p-6">

          <AnalysisResults
            result={analysis}
            executiveBrief={brief}
            briefLoading={briefLoading}
          />

        </div>
      )}

    </main>
  );
}