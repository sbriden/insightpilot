"use client";

import {
  useState,
} from "react";

import {
  FileDown,
  Loader2,
} from "lucide-react";

import {
  DataProduct,
} from "@/types/report";

import {
  buildProductExecutiveReportData,
  buildReportFilename,
} from "@/lib/buildProductExecutiveReportData";

import {
  Button,
} from "@/components/ui/button";


interface Props {
  product: Pick<
    DataProduct,
    | "name"
    | "description"
    | "business_purpose"
    | "version"
    | "status"
    | "coverage"
    | "analyses"
    | "metrics"
    | "insights"
    | "dashboards"
    | "change_summary"
    | "executive_summary"
    | "health"
    | "metadata"
    | "updated_at"
  >;
}


export default function ExportReportButton({
  product,
}: Props) {

  const [
    exporting,
    setExporting,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );

  const label =
    exporting
      ? "Generating report..."
      : error
        ? `Export failed: ${error}`
        : "Export report";


  async function handleExport() {

    try {

      setExporting(true);
      setError(null);

      const reportData =
        buildProductExecutiveReportData(
          product
        );

      const [
        { pdf },
        { default: ProductExecutivePdfDocument },
      ] = await Promise.all([
        import("@react-pdf/renderer"),
        import("@/components/products/ProductExecutivePdfDocument"),
      ]);

      const blob =
        await pdf(
          <ProductExecutivePdfDocument
            data={reportData}
          />
        ).toBlob();

      const url =
        URL.createObjectURL(blob);

      const anchor =
        document.createElement("a");

      anchor.href = url;
      anchor.download =
        buildReportFilename(
          product.name,
          product.version
        );

      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      URL.revokeObjectURL(url);

    } catch (exportError) {

      console.error(
        "Failed to export report:",
        exportError
      );

      setError(
        exportError instanceof Error
          ? exportError.message
          : "Unable to generate the report."
      );

    } finally {

      setExporting(false);

    }

  }


  return (
    <Button
      type="button"
      variant="outline"
      size="icon-sm"
      title={label}
      aria-label={label}
      onClick={handleExport}
      disabled={exporting}
      className={
        error
          ? "border-red-300 text-red-600"
          : undefined
      }
    >

      {exporting ? (

        <Loader2
          className="animate-spin"
          aria-hidden
        />

      ) : (

        <FileDown aria-hidden />

      )}

    </Button>

  );

}
