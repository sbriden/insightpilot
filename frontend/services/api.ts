import { DatasetAnalysis } from "@/types/report";

const API_URL = "http://localhost:8000/api";

async function handleResponse<T>(
  response: Response
): Promise<T> {
  if (!response.ok) {
    let message = "An unexpected error occurred.";

    try {
      const error = await response.json();
      message =
        error.detail ??
        error.message ??
        message;
    } catch {}

    throw new Error(message);
  }

  return response.json();
}

export async function uploadDataset(
  file: File
): Promise<DatasetAnalysis> {
  const formData = new FormData();

  formData.append(
    "file",
    file
  );

  const response = await fetch(
    `${API_URL}/upload/`,
    {
      method: "POST",
      body: formData,
    }
  );

  return handleResponse(response);
}