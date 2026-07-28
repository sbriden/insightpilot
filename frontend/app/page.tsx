"use client";

import { useState } from "react";
import { DatasetAnalysis } from "@/types/report";
import UploadCard from "@/components/upload/UploadCard";
import SummaryCards from "@/components/report/SummaryCards";
import ExecutiveSummary from "@/components/report/ExecutiveSummary";
import DatasetClassification from "@/components/report/DatasetClassification";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<DatasetAnalysis | null>(null);
  const [loading, setLoading] = useState(false);


  async function uploadFile() {

    if (!file) return;

    setLoading(true);

    const formData = new FormData();
    formData.append("file", file);


    const response = await fetch(
      "http://localhost:8000/api/upload/",
      {
        method: "POST",
        body: formData,
      }
    );


    const data = await response.json();

    setResult(data);

    setLoading(false);
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
        loading={loading}
        onFileChange={setFile}
        onAnalyze={uploadFile}
      />


      {loading && (
        <p className="mt-6">
          Analyzing...
        </p>
      )}


      {result && (
        <div className="mt-8 rounded border p-6">

          <h2 className="text-2xl font-semibold">
            Data Profile
          </h2>

          <SummaryCards summary={result.profile.summary} />

          <ExecutiveSummary profile={result.profile} />

          <DatasetClassification classification={result.classification} />

          <h3 className="mt-4 font-semibold">
            Columns
          </h3>

          <ul>
            {(result.profile.columns?.names || []).map(
              (col: string) => (
                <li key={col}>
                  {col}
                </li>
              )
            )}
          </ul>

        </div>
      )}

    </main>
  );
}