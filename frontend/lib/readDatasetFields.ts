import {
  DatasetField,
} from "@/types/dataset";

import {
  normalizeFieldName,
} from "@/lib/fieldMapping";

import {
  inferColumnDataType,
} from "@/lib/inferColumnDataType";


export async function readDatasetFields(
  file: File
): Promise<DatasetField[]> {

  const text =
    await file.text();


  const lines =
    text
      .split(/\r?\n/)
      .filter(
        line =>
          line.trim().length > 0
      );


  if (lines.length === 0) {
    return [];
  }


  const headers =
    parseCSVRow(
      lines[0]
    );

  const sampleValues =
    lines.length > 1
      ? parseCSVRow(
          lines[1]
        )
      : [];


  return headers
    .map(
      header =>
        header.trim()
    )
    .filter(
      header =>
        header.length > 0
    )
    .map(
      (header, index) => ({

        name: header,

        normalizedName:
          normalizeFieldName(
            header
          ),

        dataType:
          inferColumnDataType(
            header,
            sampleValues[index]
          ),

      })
    );

}


function parseCSVRow(
  line: string
): string[] {

  const result: string[] = [];

  let current = "";

  let insideQuotes = false;


  for (
    let i = 0;
    i < line.length;
    i++
  ) {

    const char =
      line[i];


    if (char === '"') {

      insideQuotes =
        !insideQuotes;

      continue;

    }


    if (
      char === "," &&
      !insideQuotes
    ) {

      result.push(
        current
      );

      current = "";

      continue;

    }


    current += char;

  }


  result.push(
    current
  );


  return result;

}
