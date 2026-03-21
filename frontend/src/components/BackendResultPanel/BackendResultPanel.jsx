import React from 'react';
import styles from './BackendResultPanel.module.css';
import { copyTextToClipboard, downloadTextFile, stripFileExt } from '../../utils/fileCopyDownload';

/**
 * Панель вывода текста с backend (загрузка / ошибка / содержимое).
 */
export default function BackendResultPanel({
  title = 'Ответ сервера',
  text,
  loading,
  loadingHint = 'Загрузка ответа…',
  error,
  onClose,
  className = '',
  fileKind,
  fileBaseName,
}) {
  const [copied, setCopied] = React.useState(false);
  const canShowActions = Boolean(fileKind) && Boolean(text) && !loading && !error;

  async function onCopy() {
    if (!canShowActions) return;
    await copyTextToClipboard(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  function onDownload() {
    if (!canShowActions) return;
    const base = stripFileExt(fileBaseName || 'output') || 'output';
    const ext = fileKind === 'json' ? 'json' : 'ts';
    const mimeType = fileKind === 'json' ? 'application/json' : 'text/plain;charset=utf-8';
    downloadTextFile(text, `${base}.${ext}`, mimeType);
  }

  return (
    <aside
      className={`${styles.panel} ${className}`.trim()}
      role="region"
      aria-label={title}
      aria-busy={loading}
    >
      <div className={styles.head}>
        <div className={styles.headLeft}>
          <h2 className={styles.title}>{title}</h2>
          {canShowActions ? (
            <div className={styles.actions} aria-label="Копирование/скачивание результата">
              <button type="button" className={styles.actionBtn} onClick={onCopy}>
                {copied ? 'Скопировано' : 'Копировать'}
              </button>
              <button type="button" className={styles.actionBtn} onClick={onDownload}>
                Скачать
              </button>
            </div>
          ) : null}
        </div>
        {onClose ? (
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Свернуть панель и вернуть полный вид загрузки"
          >
            ←
          </button>
        ) : null}
      </div>
      <div className={styles.body}>
        {loading ? (
          <div className={styles.loadingBlock} role="status" aria-label={loadingHint}>
            <div className={styles.loadingSpinner} aria-hidden="true" />
            <p className={styles.status}>{loadingHint}</p>
            <div className={styles.skeleton} aria-hidden="true">
              <div className={styles.skeletonLine} />
              <div className={styles.skeletonLine} />
              <div className={styles.skeletonLineShort} />
            </div>
          </div>
        ) : null}
        {error && !loading ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
        {!loading && !error && text ? (
          <pre className={styles.pre} tabIndex={0}>
            {text}
          </pre>
        ) : null}
        {!loading && !error && !text ? (
          <p className={styles.placeholder}>Здесь появится текст от backend.</p>
        ) : null}
      </div>
    </aside>
  );
}
