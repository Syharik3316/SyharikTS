import React from "react";
import { useNavigate } from "react-router-dom";
import { generateTsCode, inferSchemaExample } from "../api";
import FileUpload from "../components/FileUpload";
import CodeDisplay from "../components/CodeDisplay";
import { ApiError } from "../httpError";
import { useAuth } from "../context/AuthContext";

export default function GeneratorPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [file, setFile] = React.useState<File | null>(null);
  const [schemaText, setSchemaText] = React.useState(
    JSON.stringify(
      {
        dateCreate: "2026-01-01",
        dateLastUpdate: "2026-01-02",
        product: "ABC",
      },
      null,
      2,
    ),
  );

  const [loading, setLoading] = React.useState(false);
  const [code, setCode] = React.useState<string>("");
  const [error, setError] = React.useState<string>("");
  const [inferLoading, setInferLoading] = React.useState(false);
  const [inferError, setInferError] = React.useState<string>("");

  async function onGenerate() {
    setError("");
    setLoading(true);
    setCode("");
    try {
      if (!file) throw new Error("Choose a file first.");
      setCode(await generateTsCode(file, schemaText));
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.userMessage);
        if (e.status === 401) logout();
        return;
      }
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function onInferSchema() {
    setInferError("");
    setInferLoading(true);
    try {
      if (!file) throw new Error("Choose a file first.");
      const schemaStr = await inferSchemaExample(file);
      const obj = (() => {
        try {
          return JSON.parse(schemaStr);
        } catch {
          return null;
        }
      })();
      setSchemaText(obj ? JSON.stringify(obj, null, 2) : schemaStr);
    } catch (e) {
      if (e instanceof ApiError) {
        setInferError(e.userMessage);
        if (e.status === 401) logout();
        return;
      }
      setInferError(e instanceof Error ? e.message : String(e));
    } finally {
      setInferLoading(false);
    }
  }

  function goCheck() {
    navigate("/check", { state: { initialCode: code, inputFile: file } });
  }

  return (
    <>
      <div className="container" style={{ paddingBottom: 0 }}>
        <div style={{ display: "flex", gap: 12, justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ opacity: 0.9, fontSize: 14 }}>
              {user?.login} ({user?.email})
            </span>
            <button type="button" onClick={() => navigate("/generator")}>
              Генерация
            </button>
            <button type="button" onClick={goCheck}>
              Проверка TS
            </button>
            <div style={{ opacity: 0.8, fontSize: 13 }}>Сначала сгенерируйте код, затем откройте проверку.</div>
          </div>
          <button type="button" onClick={logout}>
            Выйти
          </button>
        </div>
      </div>

      <div className="container" style={{ paddingTop: 16 }}>
        <h1 style={{ marginTop: 0 }}>TypeScript Code Generator</h1>

        <div className="row">
          <div className="card">
            <FileUpload file={file} onChange={setFile} />

            <div style={{ marginTop: 16 }}>
              <label>Пример JSON структуры выхода</label>
              <textarea
                value={schemaText}
                onChange={(e) => setSchemaText(e.target.value)}
                spellCheck={false}
              />
            </div>

            <div style={{ marginTop: 8 }}>
              <button onClick={onInferSchema} disabled={inferLoading || !file}>
                {inferLoading ? "Генерируем..." : "Сгенерировать схему из файла"}
              </button>
            </div>

            {inferError ? <div className="error">{inferError}</div> : null}

            <div style={{ marginTop: 12 }}>
              <button onClick={onGenerate} disabled={loading}>
                {loading ? "Генерируем..." : "Сгенерировать TS-код"}
              </button>
            </div>

            {error ? <div className="error">{error}</div> : null}
          </div>

          <div className="card">
            {code ? (
              <CodeDisplay code={code} />
            ) : (
              <div className="hint">Загрузка файла и генерация кода.</div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
