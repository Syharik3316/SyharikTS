import React, { useEffect, useState } from 'react';
import { getMyTokenUsageSummary } from '../../api/systemApi';
import styles from './TechInfo.module.css';

export default function TechInfo() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await getMyTokenUsageSummary();
        if (!cancelled) setSummary(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const maxTokens = Math.max(1, ...(summary?.requests || []).map((r) => r.total_tokens));

  return (
    <section className={styles.page} aria-label="Техническая информация">
      <div className={styles.card}>
        <h1 className={styles.title}>Техническая информация пользователя</h1>
        {loading ? <p className={styles.hint}>Загрузка…</p> : null}
        {error ? <p className={styles.error}>{error}</p> : null}
        {!loading && !error && summary ? (
          <>
            <div className={styles.kpiGrid}>
              <div className={styles.kpiCard}>
                <p className={styles.kpiLabel}>Всего токенов</p>
                <p className={styles.kpiValue}>{summary.total_tokens}</p>
              </div>
              <div className={styles.kpiCard}>
                <p className={styles.kpiLabel}>Prompt токены</p>
                <p className={styles.kpiValue}>{summary.total_prompt_tokens}</p>
              </div>
              <div className={styles.kpiCard}>
                <p className={styles.kpiLabel}>Completion токены</p>
                <p className={styles.kpiValue}>{summary.total_completion_tokens}</p>
              </div>
              <div className={styles.kpiCard}>
                <p className={styles.kpiLabel}>Запросов</p>
                <p className={styles.kpiValue}>{summary.requests_count}</p>
              </div>
            </div>

            <h2 className={styles.subtitle}>Токены по запросам (последние 50)</h2>
            {summary.requests.length === 0 ? (
              <p className={styles.hint}>Пока нет данных по токенам.</p>
            ) : (
              <ul className={styles.chartList}>
                {summary.requests.map((item) => (
                  <li key={item.id} className={styles.chartItem}>
                    <div className={styles.chartMeta}>
                      <span>{new Date(item.created_at).toLocaleString()}</span>
                      <span className={styles.fileName}>{item.main_file_name}</span>
                    </div>
                    <div className={styles.barWrap}>
                      <div
                        className={styles.bar}
                        style={{ width: `${Math.max(4, Math.round((item.total_tokens / maxTokens) * 100))}%` }}
                      />
                    </div>
                    <div className={styles.tokensLine}>
                      <span>Total: {item.total_tokens}</span>
                      <span>Prompt: {item.prompt_tokens}</span>
                      <span>Completion: {item.completion_tokens}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : null}
      </div>
    </section>
  );
}
