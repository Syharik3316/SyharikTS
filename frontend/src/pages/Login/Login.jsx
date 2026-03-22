import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import styles from './Login.module.css';

export default function Login() {
  const { login } = useAuth();
  const location = useLocation();
  const [loginOrEmail, setLoginOrEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [registerOk, setRegisterOk] = useState(false);

  useEffect(() => {
    const st = location.state;
    if (st?.fromRegister) {
      setRegisterOk(true);
      if (typeof st.email === 'string' && st.email.trim()) {
        setLoginOrEmail(st.email.trim());
      }
    }
  }, [location.state]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(loginOrEmail.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.page} aria-label="Вход в аккаунт">
      <div className={styles.card}>
        <h1 className={styles.title}>Вход</h1>

        {registerOk ? (
          <p className={styles.successInline} role="status">
            Регистрация успешна. Войдите с указанными логином и паролем.
          </p>
        ) : null}

        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="login-email">
              Логин/E-mail
            </label>
            <input
              id="login-email"
              className={styles.input}
              type="text"
              name="login"
              autoComplete="username"
              value={loginOrEmail}
              onChange={(e) => setLoginOrEmail(e.target.value)}
              placeholder="Логин или syharik@example.ru"
              required
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label} htmlFor="login-password">
              Пароль
            </label>
            <input
              id="login-password"
              className={styles.input}
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="********"
              required
            />
          </div>

          {error ? (
            <p className={styles.formError} role="alert">
              {error}
            </p>
          ) : null}

          <button type="submit" className={styles.submit} disabled={busy}>
            {busy ? '…' : 'Войти'}
          </button>
        </form>

        <p className={styles.hint} style={{ marginTop: 16 }}>
          <Link to="/reset-password" className={styles.inlineLink}>
            Забыли пароль?
          </Link>
        </p>

        <div className={styles.footerDivider} role="separator" aria-hidden="true" />

        <p className={styles.hint}>Нет аккаунта?</p>

        <Link className={styles.registerLink} to="/register">
          Зарегистрироваться
        </Link>
      </div>
    </section>
  );
}
