"use client";

import {
  useRef,
} from "react";

import {
  Upload,
} from "lucide-react";

import {
  Card,
  CardContent,
} from "@/components/ui/card";

import {
  Button,
} from "@/components/ui/button";


interface UploadCardProps {
  file: File | null;
  loading: boolean;
  onFileChange: (
    file: File | null
  ) => void;
}


export default function UploadCard({
  file,
  loading,
  onFileChange,
}: UploadCardProps) {

  const inputRef =
    useRef<HTMLInputElement>(
      null
    );


  function openFilePicker() {

    inputRef.current?.click();

  }


  return (
    <Card className="mt-8">

      <CardContent className="space-y-4 p-6">

        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          disabled={loading}
          className="hidden"
          onChange={(event) =>
            onFileChange(
              event.target.files?.[0] ??
                null
            )
          }
        />


        {file ? (

          <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-gray-50 px-4 py-3">

            <div className="min-w-0">

              <p className="truncate text-sm font-medium text-gray-900">
                {file.name}
              </p>

              <p className="mt-1 text-xs text-gray-500">
                Dataset uploaded and ready for classification
              </p>

            </div>


            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={loading}
              onClick={openFilePicker}
            >
              Change file
            </Button>

          </div>

        ) : (

          <button
            type="button"
            disabled={loading}
            onClick={openFilePicker}
            className="flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-200 bg-white px-6 py-10 text-center transition hover:border-gray-300 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >

            <Upload
              className="size-8 text-gray-400"
              aria-hidden
            />

            <p className="mt-3 text-sm font-medium text-gray-900">
              Choose a CSV file
            </p>

            <p className="mt-1 text-xs text-gray-500">
              or click to browse
            </p>

          </button>

        )}


        {loading && (

          <p className="text-sm text-gray-500">
            Reading dataset fields...
          </p>

        )}

      </CardContent>

    </Card>

  );

}
