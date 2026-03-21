import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { listGenerationsRequest, updateProfileRequest } from '../../api/profileApi';
import styles from './Profile.module.css';

export default function Profile() {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();

  const [login, setLogin] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [savedMsg, setSavedMsg] = useState('');

  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [items, setItems] = useState([]);
  const historyScrollerRef = useRef(null);

  useEffect(() => {
    if (user) {
      setLogin(user.login || '');
    }
  }, [user?.id]);

  async function loadHistory() {
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const rows = await listGenerationsRequest();
      setItems(rows);
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : String(e));
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setSavedMsg('');
    try {
      const nextLogin = login.trim();
      await updateProfileRequest({
        login: nextLogin || null,
        current_password: currentPassword,
        new_password: newPassword.trim() || null,
      });

      setSavedMsg('Профиль обновлён.');
      setCurrentPassword('');
      setNewPassword('');
      await refreshUser();
      await loadHistory();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.page} aria-label="Профиль пользователя">
      <div className={styles.card}>
        <h1 className={styles.title}>Профиль</h1>
        <div className={styles.actionsRow}>
          <button
            type="button"
            className={styles.btn}
            onClick={() => navigate('/profile/tech')}
          >
            Техническая информация
          </button>
        </div>

        <div className={styles.grid}>
          <div>
            <h2 className={styles.sectionTitle}>Изменить данные</h2>
            <form className={styles.form} onSubmit={onSubmit} noValidate>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="profile-login">
                  Логин
                </label>
                <input
                  id="profile-login"
                  className={styles.input}
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  autoComplete="username"
                  required
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="profile-current-password">
                  Текущий пароль
                </label>
                <input
                  id="profile-current-password"
                  className={styles.input}
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="profile-new-password">
                  Новый пароль (необязательно)
                </label>
                <input
                  id="profile-new-password"
                  className={styles.input}
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  placeholder="Если нужно поменять пароль"
                />
              </div>

              {error ? (
                <p className={styles.formError} role="alert">
                  {error}
                </p>
              ) : null}
              {savedMsg ? (
                <p className={styles.formError} style={{ background: 'color-mix(in srgb, var(--accent) 14%, transparent)', color: 'var(--text)', borderColor: 'var(--accent-border)' }}>
                  {savedMsg}
                </p>
              ) : null}

              <div className={styles.actionsRow}>
                <button type="submit" className={`${styles.btn} ${styles.btnPrimary}`} disabled={busy}>
                  {busy ? '…' : 'Сохранить'}
                </button>
              </div>
            </form>
          </div>

          <div>
            <h2 className={styles.sectionTitle}>История генераций</h2>
            {historyError ? <p className={styles.formError}>{historyError}</p> : null}

            {historyLoading ? <p className={styles.emptyHint}>Загрузка…</p> : null}
            {!historyLoading && items.length === 0 ? (
              <p className={styles.emptyHint}>История пока пуста.</p>
            ) : null}

            {!historyLoading ? (
              <div className={styles.historyScrollerWrap}>
                <div className={styles.historyScrollButtons}>
                  <button
                    type="button"
                    className={styles.scrollBtn}
                    onClick={() => {
                      const el = historyScrollerRef.current;
                      if (!el) return;
                      el.scrollBy({ top: -Math.round(el.clientHeight * 0.8), behavior: 'smooth' });
                    }}
                    aria-label="Листать историю вверх"
                  >
                    ↑
                  </button>

                  <button
                    type="button"
                    className={styles.scrollBtn}
                    onClick={() => {
                      const el = historyScrollerRef.current;
                      if (!el) return;
                      el.scrollBy({ top: Math.round(el.clientHeight * 0.8), behavior: 'smooth' });
                    }}
                    aria-label="Листать историю вниз"
                  >
                    ↓
                  </button>
                </div>

                <div className={styles.historyScroller} ref={historyScrollerRef}>
                  <ul className={styles.historyList} aria-label="История генераций">
                    {items.map((it) => (
                      <li key={it.id}>
                        <button
                          type="button"
                          className={styles.historyItemBtn}
                          onClick={() => navigate(`/profile/generations/${it.id}`)}
                        >
                          <div className={styles.historyItemMeta}>
                            <span className={styles.historyDate}>
                              {new Date(it.created_at).toLocaleString()}
                            </span>
                            <span className={styles.historyFile}>{it.main_file_name}</span>
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

