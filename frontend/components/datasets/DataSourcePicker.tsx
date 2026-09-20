"use client";

import {
  FileSpreadsheet,
  Database,
} from "lucide-react";

import {
  DataSourceKind,
} from "@/types/dataset";


interface DataSourcePickerProps {
  selected: DataSourceKind;
  disabled?: boolean;
  onSelect: (kind: DataSourceKind) => void;
}


const OPTIONS: Array<{
  id: DataSourceKind;
  title: string;
  description: string;
  icon: typeof FileSpreadsheet;
}> = [
  {
    id: "csv",
    title: "CSV upload",
    description:
      "Upload a spreadsheet from your computer.",
    icon: FileSpreadsheet,
  },
  {
    id: "nflverse",
    title: "nflverse",
    description:
      "Fantasy football foundation from nflverse — no CSV upload.",
    icon: Database,
  },
];


export default function DataSourcePicker({
  selected,
  disabled = false,
  onSelect,
}: DataSourcePickerProps) {

  return (
    <div className="grid gap-3 sm:grid-cols-2">

      {OPTIONS.map((option) => {

        const Icon = option.icon;
        const isSelected = selected === option.id;

        return (
          <button
            key={option.id}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(option.id)}
            className={[
              "rounded-lg border px-4 py-4 text-left transition",
              isSelected
                ? "border-gray-900 bg-gray-50 ring-1 ring-gray-900"
                : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50",
              disabled
                ? "cursor-not-allowed opacity-50"
                : "",
            ].join(" ")}
          >

            <div className="flex items-start gap-3">

              <Icon
                className="mt-0.5 size-5 text-gray-500"
                aria-hidden
              />

              <div>

                <p className="text-sm font-medium text-gray-900">
                  {option.title}
                </p>

                <p className="mt-1 text-xs text-gray-500">
                  {option.description}
                </p>

              </div>

            </div>

          </button>
        );

      })}

    </div>
  );

}
