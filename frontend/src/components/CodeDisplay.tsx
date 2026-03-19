import React from "react";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css";
import typescript from "highlight.js/lib/languages/typescript";

hljs.registerLanguage("typescript", typescript);

export default function CodeDisplay(props: { code: string }) {
  const { code } = props;
  const [copied, setCopied] = React.useState(false);
  const [copyError, setCopyError] = React.useState<string>("");

  async function onCopy() {
    setCopyError("");
    setCopied(false);
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(code);
      } else {
        // Fallback: copy via a temporary textarea.
        const ta = document.createElement("textarea");
        ta.value = code;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        ta.style.top = "-9999px";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch (e) {
      setCopyError(e instanceof Error ? e.message : String(e));
    }
  }

  const highlighted = React.useMemo(() => {
    try {
      return hljs.highlight(code, { language: "typescript" }).value;
    } catch {
      return hljs.highlightAuto(code).value;
    }
  }, [code]);

  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "space-between" }}>
        <label>Сгенерированный TypeScript-код</label>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button onClick={onCopy} disabled={!code.trim()}>
            {copied ? "Скопировано" : "Копировать"}
          </button>
        </div>
      </div>
      <pre>
        <code dangerouslySetInnerHTML={{ __html: highlighted }} />
      </pre>
      {copyError ? <div className="error">{copyError}</div> : null}
    </div>
  );
}

