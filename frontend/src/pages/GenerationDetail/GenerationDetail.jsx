import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { deleteGenerationRequest, getGenerationDetailRequest } from '../../api/profileApi';
import { copyTextToClipboard, downloadTextFile, stripFileExt } from '../../utils/fileCopyDownload';
import styles from './GenerationDetail.module.css';

export default function GenerationDetail() {
  const navigate = useNavigate();
  const { id } = useParams();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [detail, setDetail] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!id) return;
    (async () => {
      setLoading(true);
      setError('');
      setDeleteError('');
      try {
        const row = await getGenerationDetailRequest(id);
        setDetail(row);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  async function onCopy() {
    if (!detail?.generated_ts_code) return;
    await copyTextToClipboard(detail.generated_ts_code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  function onDownload() {
    const mainName = detail?.main_file_name || 'generated.ts';
    const base = stripFileExt(mainName) || 'generated';
    downloadTextFile(detail.generated_ts_code || '', `${base}.ts`, 'text/plain;charset=utf-8');
  }

  function onCheckTs() {
    navigate('/upload', {
      state: {
        mode: 'checkTs',
        initialTsCode: detail.generated_ts_code,
        generationId: id,
        checkInputFileName: detail.main_file_name,
      },
    });
  }

  async function onDelete() {
    if (!detail || !id) return;
    const ok = window.confirm('Удалить эту генерацию?');
    if (!ok) return;

    setDeleteBusy(true);
    setDeleteError('');
    try {
      await deleteGenerationRequest(id);
      navigate('/profile', { replace: true });
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : String(e));
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <section className={styles.page} aria-label="Детальная страница генерации">
      <div className={styles.card}>
        <h1 className={styles.title}>Сгенерированный TypeScript</h1>
        {detail ? (
          <p className={styles.meta}>
            Файл: <strong>{detail.main_file_name}</strong> · Дата:{' '}
            {new Date(detail.created_at).toLocaleString()}
          </p>
        ) : null}

        {loading ? <p className={styles.meta}>Загрузка…</p> : null}
        {error ? <p className={styles.error}>{error}</p> : null}

        {!loading && !error && detail ? (
          <>
            <div className={styles.actionsRow} aria-label="Действия">
              <button type="button" className={styles.btn} onClick={onCopy} disabled={!detail.generated_ts_code}>
                {copied ? 'Скопировано' : 'Копировать .ts'}
              </button>
              <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={onDownload} disabled={!detail.generated_ts_code}>
                Скачать .ts
              </button>
              <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={onCheckTs}>
                Проверить TS в Upload
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnDanger}`}
                onClick={onDelete}
                disabled={deleteBusy}
              >
                {deleteBusy ? 'Удаление…' : 'Удалить'}
              </button>
            </div>

            <div className={styles.codeWrap} style={{ marginTop: 12 }}>
              <pre className={styles.codePre}>{detail.generated_ts_code}</pre>
            </div>

            {deleteError ? <p className={styles.error} style={{ marginTop: 12 }}>{deleteError}</p> : null}
          </>
        ) : null}
      </div>
    </section>
  );
}

