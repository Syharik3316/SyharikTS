import { ApiError, mapStatusToUserMessage, parseBackendError } from "./httpError";

export type GenerateResponse = {
  code: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function generateTsCode(file: File, schemaText: string): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("schema", schemaText);

  const res = await fetch(`${API_BASE_URL}/generate`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const { status, detail } = await parseBackendError(res);
    throw new ApiError({
      status,
      detail,
      userMessage: mapStatusToUserMessage(status, detail),
    });
  }

  const data = (await res.json()) as GenerateResponse;
  return data.code;
}

export type InferSchemaResponse = {
  schema: string;
};

export async function inferSchemaExample(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE_URL}/infer-schema`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const { status, detail } = await parseBackendError(res);
    throw new ApiError({
      status,
      detail,
      userMessage: mapStatusToUserMessage(status, detail),
    });
  }

  const data = (await res.json()) as InferSchemaResponse;
  // Backend returns compact JSON string; frontend can reformat if needed.
  return data.schema;
}

