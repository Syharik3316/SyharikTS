import React from "react";
import ts from "typescript";

type CheckPageProps = {
  initialCode?: string;
  inputFile?: File | null;
};

function stripInterfaceBlocks(source: string): string {
  // Make checker tolerant to invalid interface keys in previously generated code.
  // It removes top-level `interface X { ... }` declarations before transpile.
  return source.replace(/interface\s+[A-Za-z_$][\w$]*\s*\{[\s\S]*?\}\s*/g, "");
}

export default function CheckPage(props: CheckPageProps) {
  const { initialCode, inputFile } = props;

  const [codeInput, setCodeInput] = React.useState<string>(initialCode ?? "");

  React.useEffect(() => {
    setCodeInput(initialCode ?? "");
  }, [initialCode]);

  const [status, setStatus] = React.useState<string>("");
  const [resultPreview, setResultPreview] = React.useState<string>("");
  const [error, setError] = React.useState<string>("");
  const [loading, setLoading] = React.useState(false);

  function bytesToBase64(bytes: Uint8Array): string {
    let binary = "";
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const chunk = bytes.subarray(i, i + chunkSize);
      binary += String.fromCharCode(...chunk);
    }
    return btoa(binary);
  }

  async function fileToBase64(file: File): Promise<string> {
    const buffer = await file.arrayBuffer();
    return bytesToBase64(new Uint8Array(buffer));
  }

  async function onCheck() {
    setError("");
    setStatus("");
    setResultPreview("");
    if (!codeInput.trim()) {
      setError("No generated code to check.");
      return;
    }

    setLoading(true);
    try {
      const sourceForTranspile = stripInterfaceBlocks(codeInput);

      // 1) Transpile TS -> JS (types/interfaces are removed automatically).
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

      // 2) Execute default export.
      // eslint-disable-next-line no-restricted-globals
      const mod: any = await import(/* @vite-ignore */ url);
      URL.revokeObjectURL(url);

      const fn = mod?.default;
      if (typeof fn !== "function") {
        throw new Error("Generated module does not export default function.");
      }

      if (!inputFile) {
        throw new Error("Сначала выберите файл на вкладке Генерация.");
      }
      const base64file = await fileToBase64(inputFile);
      const res = await fn(base64file);

      if (!Array.isArray(res)) {
        throw new Error("Function result is not an array.");
      }

      const firstItem = res[0] ?? {};
      const actualKeys = firstItem && typeof firstItem === "object" ? Object.keys(firstItem) : [];

      setStatus("Execution OK");
      setResultPreview(
        JSON.stringify(
          {
            itemsCount: res.length,
            actualKeys,
            firstItem,
          },
          null,
          2
        )
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <h1 style={{ marginTop: 0 }}>Проверка TypeScript-кода</h1>

      <div className="row">
        <div className="card">
          <div style={{ marginTop: 0 }}>
            <label>TS-код (вставьте сюда export default function ...)</label>
            <textarea
              value={codeInput}
              onChange={(e) => setCodeInput(e.target.value)}
              spellCheck={false}
              style={{ minHeight: 320 }}
            />
          </div>

          <div style={{ marginTop: 12 }}>
            <button onClick={onCheck} disabled={loading || !codeInput.trim()}>
              {loading ? "Проверяем..." : "Проверить код"}
            </button>
          </div>

          {status ? <div style={{ marginTop: 12 }}>Статус: {status}</div> : null}
          {error ? <div className="error">{error}</div> : null}
        </div>

        <div className="card">
          {resultPreview ? <pre>{resultPreview}</pre> : <div className="hint">Нажмите “Проверить код”.</div>}
        </div>
      </div>
    </div>
  );
}

