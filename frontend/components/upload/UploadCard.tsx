"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface UploadCardProps {
  file: File | null;
  loading: boolean;
  onFileChange: (file: File | null) => void;
  onAnalyze: () => void;
}

export default function UploadCard({
  file,
  loading,
  onFileChange,
  onAnalyze,
}: UploadCardProps) {
  return (
    <Card className="mt-8">
      <CardContent className="space-y-4 p-6">
        <input
          type="file"
          accept=".csv"
          onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
        />

        <Button
          onClick={onAnalyze}
          disabled={!file || loading}
        >
          {loading ? "Analyzing..." : "Analyze Dataset"}
        </Button>
      </CardContent>
    </Card>
  );
}