import React from "react";
import ts from "typescript";

type CheckPageProps = {
  initialCode?: string;
  initialSchemaText: string;
};

function safeParseJson(text: string): any | null {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export default function CheckPage(props: CheckPageProps) {
  const { initialCode, initialSchemaText } = props;

  const [codeInput, setCodeInput] = React.useState<string>(initialCode ?? "");
  const [schemaInput, setSchemaInput] = React.useState<string>(initialSchemaText ?? "");

  React.useEffect(() => {
    setCodeInput(initialCode ?? "");
  }, [initialCode]);

  const [status, setStatus] = React.useState<string>("");
  const [resultPreview, setResultPreview] = React.useState<string>("");
  const [error, setError] = React.useState<string>("");
  const [loading, setLoading] = React.useState(false);

  async function onCheck() {
    setError("");
    setStatus("");
    setResultPreview("");
    if (!codeInput.trim()) {
      setError("No generated code to check.");
      return;
    }

    const schemaObj = safeParseJson(schemaInput);
    const expectedKeys = schemaObj && typeof schemaObj === "object" ? Object.keys(schemaObj) : [];

    setLoading(true);
    try {
      // 1) Transpile TS -> JS (types/interfaces are removed automatically).
      const transpiled = ts.transpileModule(codeInput, {
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

      // base64file in our MVP template is not required, but we pass dummy string anyway.
      const res = await fn("dummy_base64file");

      if (!Array.isArray(res)) {
        throw new Error("Function result is not an array.");
      }

      const firstItem = res[0] ?? {};
      const actualKeys = firstItem && typeof firstItem === "object" ? Object.keys(firstItem) : [];

      const missing = expectedKeys.filter((k) => !actualKeys.includes(k));
      const extra = actualKeys.filter((k) => !expectedKeys.includes(k));

      setStatus("Execution OK");
      setResultPreview(
        JSON.stringify(
          {
            itemsCount: res.length,
            expectedKeys,
            actualKeys,
            missing,
            extra,
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
              style={{ minHeight: 260 }}
            />

            <label style={{ marginTop: 14 }}>JSON schema (пример структуры результата)</label>
            <textarea
              value={schemaInput}
              onChange={(e) => setSchemaInput(e.target.value)}
              spellCheck={false}
              style={{ minHeight: 140 }}
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

