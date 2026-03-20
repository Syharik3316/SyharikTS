import React from "react";

export default function FileUpload(props: {
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  const { file, onChange } = props;

  return (
    <div>
      <label>Файл</label>
      <input
        type="file"
        accept=".csv,.xls,.xlsx,.pdf,.docx,.doc,.png,.jpg,.jpeg,.tif,.tiff,.txt,.md,.rtf,.odt,.xml,.epub,.fb2,text/plain,text/markdown,text/rtf,text/xml,application/xml,application/rtf,application/msword,application/epub+zip,application/vnd.oasis.opendocument.text,application/x-fictionbook+xml,image/png,image/jpeg,image/tiff,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        onChange={(e) => {
          const f = e.target.files?.[0] ?? null;
          onChange(f);
        }}
      />
      <div className="hint">
        Поддерживаются: CSV/XLS/XLSX/PDF/DOCX/DOC/PNG/JPG/TIFF/TXT/MD/RTF/ODT/XML/EPUB/FB2
      </div>
      {file ? <div style={{ marginTop: 8 }}>Выбрано: {file.name}</div> : null}
    </div>
  );
}

