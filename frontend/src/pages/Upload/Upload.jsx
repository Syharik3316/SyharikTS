import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import BackendResultPanel from '../../components/BackendResultPanel/BackendResultPanel.jsx';
import { generateTsCode, inferSchemaExample } from '../../api';
import { ApiError } from '../../httpError';
import { ACCEPT_ATTR, SUPPORTED_EXT_SET } from '../../constants/supportedFiles';
import { useAuth } from '../../context/AuthContext';
import { runTsCheckOnFile } from '../../utils/checkTsClient';
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

function formatSupportedFormatsShort() {
  return 'CSV, XLS, XLSX, PDF, DOCX, DOC, PNG, JPG, TIFF, TXT, MD, RTF, ODT, XML, EPUB, FB2';
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
  const [tsCopied, setTsCopied] = useState(false);
  const fileInputRef = useRef(null);
  const shrinkTimerRef = useRef(null);

  const splitLayout = viewState === 'shrinking' || viewState === 'split';
  const showRightPanel = viewState === 'split';

  const primaryFile = files.length > 0 ? files[0] : null;

  const clearShrinkTimer = useCallback(() => {
    if (shrinkTimerRef.current != null) {
      window.clearTimeout(shrinkTimerRef.current);
      shrinkTimerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearShrinkTimer(), [clearShrinkTimer]);

  // Prefill for navigation from generation detail page.
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
  }, [location.key]);

  const addFiles = useCallback((fileList) => {
    const next = filterAllowedFiles(fileList);
    if (!next.length) return;
    setFiles((prev) => [...prev, ...next]);
  }, []);

  const handleFileInputChange = (e) => {
    addFiles(e.target.files);
    e.target.value = '';
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
    addFiles(e.dataTransfer.files);
  };

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
    if (!primaryFile) {
      setBackendError('Выберите файл на вкладке «Генерация» (первый в списке используется для проверки).');
      startResultPanel();
      setBackendLoading(false);
      return;
    }
    startResultPanel();
    setBackendLoading(true);
    try {
      const preview = await runTsCheckOnFile(tsCodeText, primaryFile);
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
                className={`${styles.dropAreaWrap} ${isDragOver ? styles.dropAreaWrapActive : ''}`}
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
                  multiple
                  accept={ACCEPT_ATTR}
                  onChange={handleFileInputChange}
                  aria-label="Выбор файлов"
                />
                <label
                  className={styles.dropZone}
                  htmlFor="upload-files-input"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                >
                  <span className={styles.dropTitle}>Файлы</span>
                  <span className={styles.dropHint}>
                    Перетащите сюда или нажмите, чтобы выбрать на компьютере
                  </span>
                  <span className={styles.dropFormats}>
                    Поддерживаются: {formatSupportedFormatsShort()}
                  </span>
                </label>

                {files.length > 0 ? (
                  <ul className={styles.fileList} aria-label="Выбранные файлы">
                    {files.map((f) => (
                      <li key={`${f.name}-${f.size}-${f.lastModified}`} className={styles.fileItem}>
                        {f.name}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {files.length > 1 ? (
                  <p className={styles.fileHint}>
                    Для запросов к серверу используется первый файл в списке.
                  </p>
                ) : null}
              </div>

              <div className={styles.noteBlock}>
                <label className={styles.noteLabel} htmlFor="upload-note-text">
                  Пример JSON структуры выхода
                </label>
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
                <div className={styles.uploadActions}>
                  <button
                    type="button"
                    className={styles.actionBtn}
                    onClick={handleInferSchema}
                    disabled={inferLoading || !primaryFile || backendLoading}
                  >
                    {inferLoading ? '…' : 'Сгенерировать схему из файла'}
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}
                    onClick={handleGenerateTs}
                    disabled={backendLoading || viewState === 'shrinking' || inferLoading}
                  >
                    Сгенерировать TS-код
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
                Исходный файл для проверки — первый из списка на вкладке «Генерация».
                {!primaryFile ? ' Сейчас файл не выбран.' : ''}
              </p>
              <div className={styles.uploadActions}>
                <button
                  type="button"
                  className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}
                  onClick={handleCheckTs}
                  disabled={backendLoading || viewState === 'shrinking'}
                >
                  {backendLoading ? '…' : 'Проверить код'}
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
            error={backendError}
            onClose={handleCloseResultPanel}
            className={styles.resultPanel}
            fileKind={mode === MODES.checkTs ? 'json' : 'ts'}
            fileBaseName={primaryFile?.name || 'result'}
          />
        ) : null}
      </div>
    </section>
  );
}
