import { ApiError, mapStatusToUserMessage, parseBackendError } from "./httpError";
import { authorizedFetch } from "./api/httpClient";

export type GenerateResponse = {
  code: string;
};

export async function generateTsCode(file: File, schemaText: string): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("schema", schemaText);

  const res = await authorizedFetch("/generate", {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({
      status,
      code,
      detail,
      userMessage: mapStatusToUserMessage(status, detail, code),
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

  const res = await authorizedFetch("/infer-schema", {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({
      status,
      code,
      detail,
      userMessage: mapStatusToUserMessage(status, detail, code),
    });
  }

  const data = (await res.json()) as InferSchemaResponse;
  return data.schema;
}
