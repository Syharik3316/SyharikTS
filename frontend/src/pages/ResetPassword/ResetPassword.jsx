import React, { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import ReCAPTCHA from 'react-google-recaptcha';
import * as authApi from '../../api/authApi';
import HoldToRevealPasswordField from '../../components/HoldToRevealPasswordField/HoldToRevealPasswordField.jsx';
import styles from '../Login/Login.module.css';

const SITE_KEY = (import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? '').trim();

export default function ResetPassword() {
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [captchaToken, setCaptchaToken] = useState(null);
  const captchaRef = useRef(null);

  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function onRequest(e) {
    e.preventDefault();
    setError('');
    setMessage('');
    if (!SITE_KEY) {
      setError('Сброс пароля недоступен: не задан VITE_RECAPTCHA_SITE_KEY при сборке.');
      return;
    }
    if (!captchaToken) {
      setError('Пройдите проверку reCAPTCHA.');
      return;
    }
    setBusy(true);
    try {
      const res = await authApi.resetRequest(email.trim(), captchaToken);
      setMessage(res.message);
      captchaRef.current?.reset();
      setCaptchaToken(null);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm(e) {
    e.preventDefault();
    setError('');
    setMessage('');
    if (newPassword.length < 8) {
      setError('Новый пароль должен быть не короче 8 символов.');
      return;
    }
    setBusy(true);
    try {
      const res = await authApi.resetConfirm(email.trim(), code.trim(), newPassword);
      setMessage(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.page} aria-label="Сброс пароля">
      <div className={styles.card}>
        <h1 className={styles.title}>Сброс пароля</h1>

        {step === 1 ? (
          <form className={styles.form} onSubmit={onRequest} noValidate>
            <p className={styles.hint} style={{ marginBottom: 20 }}>
              Укажите email аккаунта. Если он есть в системе, мы отправим код.
            </p>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="reset-email">
                Email
              </label>
              <input
                id="reset-email"
                className={styles.input}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            {SITE_KEY ? (
              <div style={{ display: 'flex', justifyContent: 'center', marginTop: 8 }}>
                <ReCAPTCHA
                  ref={captchaRef}
                  sitekey={SITE_KEY}
                  onChange={(t) => setCaptchaToken(t)}
                  onExpired={() => setCaptchaToken(null)}
                />
              </div>
            ) : (
              <p className={styles.formError} role="alert">
                Задайте VITE_RECAPTCHA_SITE_KEY (см. .env.example).
              </p>
            )}
            {error ? (
              <p className={styles.formError} role="alert">
                {error}
              </p>
            ) : null}
            {message ? (
              <p className={styles.successInline} role="status">
                {message}
              </p>
            ) : null}
            <button type="submit" className={styles.submit} disabled={busy || !SITE_KEY}>
              {busy ? '…' : 'Отправить код'}
            </button>
          </form>
        ) : (
          <form className={styles.form} onSubmit={onConfirm} noValidate>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="reset-email-2">
                Email
              </label>
              <input
                id="reset-email-2"
                className={styles.input}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="reset-code">
                Код из письма
              </label>
              <input
                id="reset-code"
                className={styles.input}
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                required
                autoComplete="one-time-code"
              />
            </div>
            <HoldToRevealPasswordField
              id="reset-new-password"
              label="Новый пароль"
              name="newPassword"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="мин. 8 символов"
            />
            {error ? (
              <p className={styles.formError} role="alert">
                {error}
              </p>
            ) : null}
            {message ? (
              <p className={styles.successInline} role="status">
                {message}
              </p>
            ) : null}
            <button type="submit" className={styles.submit} disabled={busy}>
              {busy ? '…' : 'Сменить пароль'}
            </button>
            <button
              type="button"
              className={styles.registerLink}
              style={{ marginTop: 12 }}
              onClick={() => {
                setStep(1);
                setError('');
                setMessage('');
              }}
            >
              Запросить код снова
            </button>
          </form>
        )}

        <div className={styles.footerDivider} role="separator" aria-hidden="true" />
        <p className={styles.hint}>
          <Link to="/login" className={styles.inlineLink}>
            Назад к входу
          </Link>
        </p>
      </div>
    </section>
  );
}
