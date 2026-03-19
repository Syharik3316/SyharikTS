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
        onChange={(e) => {
          const f = e.target.files?.[0] ?? null;
          onChange(f);
        }}
      />
      <div className="hint">
        Поддерживаются: CSV/XLS/XLSX/PDF/DOCX/PNG/JPG
      </div>
      {file ? <div style={{ marginTop: 8 }}>Выбрано: {file.name}</div> : null}
    </div>
  );
}

