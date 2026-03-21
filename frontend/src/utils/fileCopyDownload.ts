export function stripFileExt(filename: string): string {
  const s = String(filename ?? "").trim();
  if (!s) return "";
  return s.replace(/\.[^/.]+$/, "");
}

export async function copyTextToClipboard(text: string): Promise<void> {
  const t = String(text ?? "");
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    await navigator.clipboard.writeText(t);
    return;
  }

  // Fallback: copy via hidden textarea.
  const ta = document.createElement("textarea");
  ta.value = t;
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  ta.style.top = "-9999px";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
}

export function downloadTextFile(text: string, fileName: string, mimeType = "text/plain"): void {
  const blob = new Blob([String(text ?? "")], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

