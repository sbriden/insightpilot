"use client";

interface DatasetPreviewTableProps {
  rows: Record<string, unknown>[];
  totalRowCount?: number;
  emptyMessage?: string;
  title?: string;
  maxHeightClassName?: string;
}


function formatCellValue(
  value: unknown
): string {

  if (
    value === null ||
    value === undefined
  ) {
    return "";
  }

  if (
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }

  if (
    typeof value === "object"
  ) {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  return String(value);

}


export default function DatasetPreviewTable({
  rows,
  totalRowCount,
  emptyMessage = "No preview rows available.",
  title = "Data preview",
  maxHeightClassName = "max-h-[28rem]",
}: DatasetPreviewTableProps) {

  if (
    !rows ||
    rows.length === 0
  ) {

    return (
      <div className="rounded-lg border bg-white px-4 py-6 text-sm text-gray-500">
        {emptyMessage}
      </div>
    );

  }


  const columns =
    Object.keys(
      rows[0] ?? {}
    );


  return (
    <div className="space-y-2">

      <div className="flex flex-wrap items-center justify-between gap-2">

        <p className="text-sm font-medium text-gray-900">
          {title}
        </p>

        <p className="text-xs text-gray-500">
          Showing {rows.length.toLocaleString()}
          {typeof totalRowCount === "number"
            ? ` of ${totalRowCount.toLocaleString()} rows`
            : " sample rows"}
        </p>

      </div>

      <div className={`overflow-auto rounded-lg border bg-white ${maxHeightClassName}`}>

        <table className="min-w-full border-collapse text-left text-xs">

          <thead className="sticky top-0 bg-gray-50">

            <tr>

              {columns.map(
                (column) => (
                  <th
                    key={column}
                    className="whitespace-nowrap border-b px-3 py-2 font-medium text-gray-700"
                  >
                    {column}
                  </th>
                )
              )}

            </tr>

          </thead>

          <tbody>

            {rows.map(
              (row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="odd:bg-white even:bg-gray-50/60"
                >

                  {columns.map(
                    (column) => (
                      <td
                        key={`${rowIndex}-${column}`}
                        className="max-w-[14rem] truncate whitespace-nowrap border-b border-gray-100 px-3 py-2 text-gray-700"
                        title={formatCellValue(row[column])}
                      >
                        {formatCellValue(row[column])}
                      </td>
                    )
                  )}

                </tr>
              )
            )}

          </tbody>

        </table>

      </div>

    </div>
  );

}
