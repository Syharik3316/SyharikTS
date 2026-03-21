import ts from "typescript";

export function stripInterfaceBlocks(source: string): string {
  return source.replace(/interface\s+[A-Za-z_$][\w$]*\s*\{[\s\S]*?\}\s*/g, "");
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

export async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  return bytesToBase64(new Uint8Array(buffer));
}

/**
 * Transpile TS, run default export on base64 file, return formatted JSON preview string.
 */
export async function runTsCheckOnFile(codeInput: string, inputFile: File): Promise<string> {
  const sourceForTranspile = stripInterfaceBlocks(codeInput);

  const transpiled = ts.transpileModule(sourceForTranspile, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
    },
    reportDiagnostics: true,
  });

  if (transpiled.diagnostics && transpiled.diagnostics.length > 0) {
    const first = transpiled.diagnostics[0];
    const msg = ts.flattenDiagnosticMessageText(first.messageText, "\n");
    throw new Error(`TypeScript diagnostics: ${msg}`);
  }

  const jsCode = transpiled.outputText;
  const blob = new Blob([jsCode], { type: "text/javascript" });
  const url = URL.createObjectURL(blob);

  try {
    // eslint-disable-next-line no-restricted-globals
    const mod: unknown = await import(/* @vite-ignore */ url);
    const fn = (mod as { default?: unknown })?.default;
    if (typeof fn !== "function") {
      throw new Error("Generated module does not export default function.");
    }

    const base64file = await fileToBase64(inputFile);
    const res = await (fn as (b: string) => unknown)(base64file);

    if (!Array.isArray(res)) {
      throw new Error("Function result is not an array.");
    }

    const firstItem = res[0] ?? {};
    const actualKeys = firstItem && typeof firstItem === "object" ? Object.keys(firstItem as object) : [];

    return JSON.stringify(
      {
        itemsCount: res.length,
        actualKeys,
        firstItem,
      },
      null,
      2,
    );
  } finally {
    URL.revokeObjectURL(url);
  }
}
