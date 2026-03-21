import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import BackendResultPanel from '../../components/BackendResultPanel/BackendResultPanel.jsx';
import { generateTsCode, inferSchemaExample } from '../../api';
import { ApiError } from '../../httpError';
import { ACCEPT_ATTR, SUPPORTED_EXT_SET } from '../../constants/supportedFiles';
import { useAuth } from '../../context/AuthContext';
import { getGenerationCheckInputRequest } from '../../api/profileApi';
import { runTsCheckOnFile, runTsCheckWithBase64 } from '../../utils/checkTsClient';
import { copyTextToClipboard, downloadTextFile, stripFileExt } from '../../utils/fileCopyDownload';
import styles from './Upload.module.css';

const MODES = {
  generation: 'generation',
  checkTs: 'checkTs',
};

const MODE_BANNER_TEXT = {
  [MODES.generation]: 'TypeScript Code Generator',
  [MODES.checkTs]: 'Проверка TypeScript-кода',
};

const DEFAULT_SCHEMA = JSON.stringify(
  {
    dateCreate: '2026-01-01',
    dateLastUpdate: '2026-01-02',
    product: 'ABC',
  },
  null,
  2,
);

const SHRINK_PHASE_MS = 580;

function getExt(name) {
  const i = name.lastIndexOf('.');
  if (i < 0) return '';
  return name.slice(i + 1).toLowerCase();
}

function filterAllowedFiles(fileList) {
  const all = Array.from(fileList || []);
  const ok = [];
  const rejected = [];
  for (const f of all) {
    const ext = getExt(f.name);
    if (SUPPORTED_EXT_SET.has(ext)) ok.push(f);
    else rejected.push(f);
  }
  if (rejected.length) {
    console.warn('[upload] пропущены файлы с неподдерживаемым типом:', rejected.map((f) => f.name));
  }
  return ok;
}

/** Только один файл: берём первый подходящий. */
function pickSingleAllowedFile(fileList) {
  const ok = filterAllowedFiles(fileList);
  return ok.length ? [ok[0]] : [];
}

function formatSupportedFormatsShort() {
  return 'CSV, XLS, XLSX, PDF, DOCX, DOC, PNG, JPG, JPEG, TIFF, TXT, MD, RTF, ODT, XML, EPUB, FB2';
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function Upload() {
  const { logout } = useAuth();
  const location = useLocation();
  const [mode, setMode] = useState(MODES.generation);
  const [files, setFiles] = useState([]);
  const [noteText, setNoteText] = useState(DEFAULT_SCHEMA);
  const [tsCodeText, setTsCodeText] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [viewState, setViewState] = useState('input');
  const [backendText, setBackendText] = useState('');
  const [resultTitle, setResultTitle] = useState('Результат');
  const [backendLoading, setBackendLoading] = useState(false);
  const [backendError, setBackendError] = useState('');
  const [inferLoading, setInferLoading] = useState(false);
  const [inferError, setInferError] = useState('');
  const [jsonImportError, setJsonImportError] = useState('');
  const [tsCopied, setTsCopied] = useState(false);
  const [checkInputBase64, setCheckInputBase64] = useState(null);
  const [checkInputLoading, setCheckInputLoading] = useState(false);
  const [checkInputError, setCheckInputError] = useState('');
  const [checkInputFileLabel, setCheckInputFileLabel] = useState('');
  const fileInputRef = useRef(null);
  const jsonImportInputRef = useRef(null);
  const shrinkTimerRef = useRef(null);

  const splitLayout = viewState === 'shrinking' || viewState === 'split';
  const showRightPanel = viewState === 'split';

  const primaryFile = files.length > 0 ? files[0] : null;
  const generationBusy = mode === MODES.generation && (inferLoading || backendLoading);

  const clearShrinkTimer = useCallback(() => {
    if (shrinkTimerRef.current != null) {
      window.clearTimeout(shrinkTimerRef.current);
      shrinkTimerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearShrinkTimer(), [clearShrinkTimer]);

  // Prefill for navigation from generation detail page + load saved upload for TS check.
  useEffect(() => {
    const st = location.state || {};
    if (st && st.mode === MODES.checkTs && typeof st.initialTsCode === 'string') {
      if (st.initialTsCode.trim()) {
        setMode(MODES.checkTs);
        setTsCodeText(st.initialTsCode);
        setViewState('input');
        setBackendText('');
        setBackendError('');
      }
    }

    const gid = typeof st.generationId === 'string' && st.generationId.trim() ? st.generationId.trim() : null;
    const label = typeof st.checkInputFileName === 'string' ? st.checkInputFileName : '';
    setCheckInputFileLabel(label);

    if (!gid) {
      setCheckInputBase64(null);
      setCheckInputError('');
      setCheckInputLoading(false);
      return undefined;
    }

    let cancelled = false;
    setCheckInputBase64(null);
    setCheckInputError('');
    setCheckInputLoading(true);
    getGenerationCheckInputRequest(gid)
      .then((r) => {
        if (cancelled) return;
        const b64 = r?.input_base64 && String(r.input_base64).trim() ? String(r.input_base64).trim() : null;
        setCheckInputBase64(b64);
      })
      .catch((e) => {
        if (cancelled) return;
        setCheckInputError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setCheckInputLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [location.key]);

  const addFiles = useCallback((fileList) => {
    const next = pickSingleAllowedFile(fileList);
    if (!next.length) return;
    setFiles(next);
  }, []);

  const handleFileInputChange = (e) => {
    addFiles(e.target.files);
    e.target.value = '';
  };

  const removeFile = (targetFile) => {
    setFiles((prev) =>
      prev.filter(
        (f) =>
          !(
            f.name === targetFile.name &&
            f.size === targetFile.size &&
            f.lastModified === targetFile.lastModified
          ),
      ),
    );
  };

  const handleJsonImport = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setJsonImportError('');
    try {
      const text = await file.text();
      setNoteText(text);
    } catch {
      setJsonImportError('Не удалось прочитать .json файл.');
    }
  };

  const handleModeChange = (next) => {
    setMode(next);
    setInferError('');
    setBackendError('');
    setViewState('input');
    setBackendText('');
    setBackendLoading(false);
    setTsCopied(false);
    clearShrinkTimer();
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const { relatedTarget } = e;
    if (relatedTarget instanceof Node && e.currentTarget.contains(relatedTarget)) {
      return;
    }
    setIsDragOver(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes('Files')) {
      e.dataTransfer.dropEffect = 'copy';
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (mode === MODES.generation && (inferLoading || backendLoading)) return;
    addFiles(e.dataTransfer.files);
  };

  // Ctrl+V: если в буфере есть файлы, добавляем их как будто это drop.
  useEffect(() => {
    const onPaste = (e) => {
      if (mode !== MODES.generation) return;
      if (inferLoading || backendLoading) return;
      const clipboardData = e.clipboardData;
      if (!clipboardData || !clipboardData.items) return;

      const nextFiles = [];
      for (const item of Array.from(clipboardData.items || [])) {
        if (item && item.kind === 'file') {
          const f = item.getAsFile();
          if (f) nextFiles.push(f);
        }
      }

      if (!nextFiles.length) return;
      e.preventDefault();
      addFiles([nextFiles[0]]);
      setIsDragOver(false);
    };

    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [mode, addFiles, inferLoading, backendLoading]);

  function handleApiError(err) {
    if (err instanceof ApiError) {
      if (err.status === 401) logout();
      return err.userMessage;
    }
    return err instanceof Error ? err.message : String(err);
  }

  function startResultPanel() {
    if (viewState !== 'input') return;
    clearShrinkTimer();
    setViewState('shrinking');
    shrinkTimerRef.current = window.setTimeout(() => {
      shrinkTimerRef.current = null;
      setViewState('split');
    }, SHRINK_PHASE_MS);
  }

  const handleInferSchema = async () => {
    setInferError('');
    if (!primaryFile) {
      setInferError('Выберите файл.');
      return;
    }
    setInferLoading(true);
    try {
      const schemaStr = await inferSchemaExample(primaryFile);
      let obj = null;
      try {
        obj = JSON.parse(schemaStr);
      } catch {
        obj = null;
      }
      setNoteText(obj ? JSON.stringify(obj, null, 2) : schemaStr);
    } catch (err) {
      setInferError(handleApiError(err));
    } finally {
      setInferLoading(false);
    }
  };

  const handleGenerateTs = async () => {
    setBackendError('');
    setBackendText('');
    setResultTitle('Сгенерированный TypeScript');
    if (!primaryFile) {
      setBackendError('Выберите файл.');
      startResultPanel();
      setBackendLoading(false);
      return;
    }
    startResultPanel();
    setBackendLoading(true);
    try {
      const code = await generateTsCode(primaryFile, noteText);
      setBackendText(code);
      // For requirement: after generation, switching to "Проверка TS"
      // must auto-populate the textarea with the generated code.
      setTsCodeText(code);
    } catch (err) {
      setBackendError(handleApiError(err));
    } finally {
      setBackendLoading(false);
    }
  };

  const handleCheckTs = async () => {
    setBackendError('');
    setBackendText('');
    setResultTitle('Результат проверки');
    if (!tsCodeText.trim()) {
      setBackendError('Вставьте TS-код.');
      startResultPanel();
      setBackendLoading(false);
      return;
    }
    if (checkInputLoading && !primaryFile) {
      setBackendError('Подождите: загружается сохранённый файл с сервера…');
      startResultPanel();
      setBackendLoading(false);
      return;
    }
    const savedB64 = checkInputBase64 && String(checkInputBase64).trim() ? String(checkInputBase64).trim() : '';
    if (!primaryFile && !savedB64) {
      setBackendError(
        checkInputError ||
          'Нет входного файла: для этой записи он не сохранён (слишком большой или старая генерация), либо откройте «Проверить TS» из истории. Выберите файл на вкладке «Генерация».',
      );
      startResultPanel();
      setBackendLoading(false);
      return;
    }
    startResultPanel();
    setBackendLoading(true);
    try {
      const preview = primaryFile
        ? await runTsCheckOnFile(tsCodeText, primaryFile)
        : await runTsCheckWithBase64(tsCodeText, savedB64);
      setBackendText(preview);
    } catch (err) {
      setBackendError(err instanceof Error ? err.message : String(err));
    } finally {
      setBackendLoading(false);
    }
  };

  const handleCloseResultPanel = () => {
    clearShrinkTimer();
    setViewState('input');
  };

  const onCopyTs = async () => {
    if (!tsCodeText) return;
    await copyTextToClipboard(tsCodeText);
    setTsCopied(true);
    window.setTimeout(() => setTsCopied(false), 1200);
  };

  const onDownloadTs = () => {
    const base = stripFileExt(primaryFile?.name || 'generated') || 'generated';
    downloadTextFile(tsCodeText, `${base}.ts`, 'text/plain;charset=utf-8');
  };

  return (
    <section className={styles.page} aria-label="Загрузка">
      <div
        className={`${styles.workspace} ${splitLayout ? styles.workspaceSplit : ''}`}
      >
        <div
          className={`${styles.glassPanel} ${splitLayout ? styles.glassPanelCompact : ''}`}
          role="region"
          aria-label="Область загрузки"
        >
          <div className={styles.modeBlock}>
            <div className={styles.modeRow}>
              <div className={styles.modeLeft}>
                <span className={styles.modeLabel} id="upload-mode-label">
                  Режим:
                </span>
                <div
                  className={styles.modeButtons}
                  role="group"
                  aria-labelledby="upload-mode-label"
                >
                  <button
                    type="button"
                    className={`${styles.modeButton} ${
                      mode === MODES.generation ? styles.modeButtonActive : ''
                    }`}
                    onClick={() => handleModeChange(MODES.generation)}
                  >
                    Генерация
                  </button>
                  <button
                    type="button"
                    className={`${styles.modeButton} ${
                      mode === MODES.checkTs ? styles.modeButtonActive : ''
                    }`}
                    onClick={() => handleModeChange(MODES.checkTs)}
                  >
                    Проверка TS
                  </button>
                </div>
              </div>
              <span className={styles.modeBanner} aria-live="polite">
                {MODE_BANNER_TEXT[mode]}
              </span>
            </div>
          </div>

          <div className={styles.divider} role="separator" aria-hidden="true" />

          {mode === MODES.generation ? (
            <>
              <div
                className={`${styles.dropAreaWrap} ${isDragOver ? styles.dropAreaWrapActive : ''} ${
                  generationBusy ? styles.dropAreaWrapBusy : ''
                }`}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
              >
                <input
                  ref={fileInputRef}
                  id="upload-files-input"
                  className={styles.hiddenFileInput}
                  type="file"
                  accept={ACCEPT_ATTR}
                  onChange={handleFileInputChange}
                  aria-label="Выбор одного файла"
                  disabled={generationBusy}
                />
                <label
                  className={`${styles.dropZone} ${
                    files.length > 0 ? styles.dropZoneWithFile : ''
                  } ${generationBusy ? styles.dropZoneDisabled : ''}`}
                  htmlFor="upload-files-input"
                  tabIndex={generationBusy ? -1 : 0}
                  onKeyDown={(e) => {
                    if (generationBusy) return;
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                >
                  <span className={styles.dropTitle}>Файл</span>
                  <span className={styles.dropHint}>
                    Перетащите сюда один файл или нажмите, чтобы выбрать
                  </span>
                  <span className={styles.dropFormats}>
                    Поддерживаются: {formatSupportedFormatsShort()}
                  </span>

                  {files.length > 0 ? (
                    <span className={styles.fileReadyBadge} role="status" aria-live="polite">
                      Готово: файл загружен
                    </span>
                  ) : null}
                </label>

                {files.length > 0 ? (
                  <ul className={styles.fileList} aria-label="Выбранный файл">
                    {files.map((f) => (
                      <li key={`${f.name}-${f.size}-${f.lastModified}`} className={styles.fileItem}>
                        <div className={styles.fileMeta}>
                          <span className={styles.fileName}>{f.name}</span>
                          <span className={styles.fileSize}>{formatFileSize(f.size)}</span>
                        </div>
                        <button
                          type="button"
                          className={styles.fileRemoveBtn}
                          onClick={() => removeFile(f)}
                          disabled={generationBusy}
                          aria-label={`Удалить файл ${f.name}`}
                          title="Удалить файл"
                        >
                          Удалить
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {generationBusy ? (
                  <div className={styles.busyOverlay} aria-live="polite" aria-busy="true">
                    <div className={styles.busySpinner} aria-hidden="true" />
                    <p className={styles.busyText}>
                      {inferLoading
                        ? 'Анализируем файл и строим пример схемы…'
                        : 'Генерируем TypeScript на сервере…'}
                    </p>
                    <div className={styles.busyShimmer} aria-hidden="true" />
                  </div>
                ) : null}
              </div>

              <div className={styles.noteBlock}>
                <label className={styles.noteLabel} htmlFor="upload-note-text">
                  Пример JSON структуры выхода
                </label>
                <div className={styles.noteTools}>
                  <button
                    type="button"
                    className={styles.actionBtn}
                    onClick={() => jsonImportInputRef.current?.click()}
                    disabled={inferLoading || backendLoading}
                  >
                    Импорт
                  </button>
                  <input
                    ref={jsonImportInputRef}
                    className={styles.hiddenFileInput}
                    type="file"
                    accept=".json,application/json,text/json"
                    onChange={handleJsonImport}
                    aria-label="Импорт JSON в поле примера"
                  />
                </div>
                <div className={styles.noteRow}>
                  <textarea
                    id="upload-note-text"
                    className={styles.noteTextarea}
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    spellCheck={false}
                    maxLength={200000}
                  />
                </div>
                {inferError ? (
                  <p className={styles.inlineError} role="alert">
                    {inferError}
                  </p>
                ) : null}
                {jsonImportError ? (
                  <p className={styles.inlineError} role="alert">
                    {jsonImportError}
                  </p>
                ) : null}
                <div className={styles.uploadActions}>
                  <button
                    type="button"
                    className={styles.actionBtn}
                    onClick={handleInferSchema}
                    disabled={inferLoading || !primaryFile || backendLoading}
                  >
                    {inferLoading ? (
                      <span className={styles.btnWithSpinner}>
                        <span className={styles.inlineSpinner} aria-hidden="true" />
                        Схема…
                      </span>
                    ) : (
                      'Сгенерировать схему из файла'
                    )}
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}
                    onClick={handleGenerateTs}
                    disabled={backendLoading || viewState === 'shrinking' || inferLoading}
                  >
                    {backendLoading ? (
                      <span className={styles.btnWithSpinner}>
                        <span className={styles.inlineSpinner} aria-hidden="true" />
                        Генерация…
                      </span>
                    ) : (
                      'Сгенерировать TS-код'
                    )}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className={`${styles.noteBlock} ${styles.noteBlockTsOnly}`}>
              <label className={styles.noteLabel} htmlFor="upload-ts-code-text">
                TS-код (вставьте сюда export default function …)
              </label>
              <div className={styles.noteRow}>
                <textarea
                  id="upload-ts-code-text"
                  className={`${styles.noteTextarea} ${styles.noteTextareaTs}`}
                  value={tsCodeText}
                  onChange={(e) => setTsCodeText(e.target.value)}
                  placeholder="export default function ..."
                  spellCheck={false}
                  maxLength={200000}
                />
              </div>
              <div className={styles.tsActionsRow}>
                <button
                  type="button"
                  className={styles.actionBtn}
                  onClick={onCopyTs}
                  disabled={!tsCodeText.trim()}
                >
                  {tsCopied ? 'Скопировано' : 'Копировать .ts'}
                </button>
                <button
                  type="button"
                  className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}
                  onClick={onDownloadTs}
                  disabled={!tsCodeText.trim()}
                >
                  Скачать .ts
                </button>
              </div>
              <p className={styles.fileHint}>
                {checkInputLoading
                  ? 'Загружаем исходный файл, сохранённый при генерации…'
                  : checkInputBase64
                    ? `Используется сохранённый файл${checkInputFileLabel ? ` (${checkInputFileLabel})` : ''}. При необходимости выберите другой файл на вкладке «Генерация» — он будет иметь приоритет.`
                    : 'Исходный файл для проверки — выбранный файл на вкладке «Генерация» или сохранённая копия при переходе из истории.'}
                {!primaryFile && !checkInputBase64 && !checkInputLoading ? ' Сейчас входного файла нет.' : ''}
              </p>
              <div className={styles.uploadActions}>
                <button
                  type="button"
                  className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}
                  onClick={handleCheckTs}
                  disabled={backendLoading || viewState === 'shrinking' || (checkInputLoading && !primaryFile)}
                >
                  {backendLoading ? (
                    <span className={styles.btnWithSpinner}>
                      <span className={styles.inlineSpinner} aria-hidden="true" />
                      Проверка…
                    </span>
                  ) : (
                    'Проверить код'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {showRightPanel ? (
          <BackendResultPanel
            title={resultTitle}
            text={backendText}
            loading={backendLoading}
            loadingHint={
              mode === MODES.checkTs
                ? 'Выполняем проверку в браузере…'
                : 'Генерируем код на сервере…'
            }
            error={backendError}
            onClose={handleCloseResultPanel}
            className={styles.resultPanel}
            fileKind={mode === MODES.checkTs ? 'json' : 'ts'}
            fileBaseName={primaryFile?.name || checkInputFileLabel || 'result'}
          />
        ) : null}
      </div>
    </section>
  );
}
