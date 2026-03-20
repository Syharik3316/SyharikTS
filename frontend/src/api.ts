export type GenerateResponse = {
  code: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function generateTsCode(file: File, schemaText: string): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("schema", schemaText);

  const token = (() => {
    try {
      return localStorage.getItem("accessToken");
    } catch {
      return null;
    }
  })();

  const res = await fetch(`${API_BASE_URL}/generate`, {
    method: "POST",
    body: form,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    if (res.status === 401) throw new Error("UNAUTHORIZED");
    throw new Error(`Backend error ${res.status}: ${text || res.statusText}`);
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

  const token = (() => {
    try {
      return localStorage.getItem("accessToken");
    } catch {
      return null;
    }
  })();

  const res = await fetch(`${API_BASE_URL}/infer-schema`, {
    method: "POST",
    body: form,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    if (res.status === 401) throw new Error("UNAUTHORIZED");
    throw new Error(`Backend error ${res.status}: ${text || res.statusText}`);
  }

  const data = (await res.json()) as InferSchemaResponse;
  // Backend returns compact JSON string; frontend can reformat if needed.
  return data.schema;
}

