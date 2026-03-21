import React, { useMemo, useState, useEffect } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import {
  ResendCooldownError,
  resendRegistrationCode,
  verifyEmailRequest,
} from '../../api/authApi';
import { PENDING_VERIFY_EMAIL_KEY } from '../../constants/authFlow';
import styles from './RegisterConfirm.module.css';

const RESEND_COOLDOWN_SEC = 60;

function formatMmSs(total) {
  const s = Math.max(0, Math.floor(total));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, '0')}`;
}

export default function RegisterConfirm() {
  const navigate = useNavigate();
  const email = useMemo(() => {
    try {
      return sessionStorage.getItem(PENDING_VERIFY_EMAIL_KEY);
    } catch {
      return null;
    }
  }, []);

  const [code, setCode] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [resendBusy, setResendBusy] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(RESEND_COOLDOWN_SEC);
  const [verified, setVerified] = useState(false);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const id = window.setTimeout(() => setSecondsLeft((x) => x - 1), 1000);
    return () => window.clearTimeout(id);
  }, [secondsLeft]);

  if (!email) {
    return <Navigate to="/login" replace />;
  }

  const pendingEmail = email;

  const handleBack = () => {
    try {
      sessionStorage.removeItem(PENDING_VERIFY_EMAIL_KEY);
    } catch {
      /* ignore */
    }
    navigate('/register', { replace: true });
  };

  const handleConfirm = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const res = await verifyEmailRequest(pendingEmail, code.trim());
      setMessage(res.message);
      setVerified(true);
      try {
        sessionStorage.removeItem(PENDING_VERIFY_EMAIL_KEY);
      } catch {
        /* ignore */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    if (secondsLeft > 0 || resendBusy || verified) return;
    setError('');
    setMessage('');
    setResendBusy(true);
    try {
      const res = await resendRegistrationCode(pendingEmail);
      setMessage(res.message);
      setSecondsLeft(RESEND_COOLDOWN_SEC);
    } catch (err) {
      if (err instanceof ResendCooldownError) {
        setError(err.message);
        setSecondsLeft(err.retryAfterSeconds);
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setResendBusy(false);
    }
  };

  return (
    <section className={styles.page} aria-label="Подтверждение электронной почты">
      <div className={styles.card}>
        <h1 className={styles.title}>Подтверждение почты</h1>
        <p className={styles.subtitle}>
          Введи 6-значный код, который пришёл на почту{' '}
          <span className={styles.email}>{pendingEmail}</span>.
        </p>
        <p className={styles.hintMuted}>
          Повторная отправка кода — не чаще одного раза в минуту.
        </p>

        <form className={styles.form} onSubmit={handleConfirm} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="confirm-code">
              Код подтверждения
            </label>
            <input
              id="confirm-code"
              className={styles.input}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="123456"
              required
              disabled={verified}
            />
          </div>

          <p className={styles.spamHint}>
            Не пришел код? Проверьте папку <strong className={styles.spamBold}>Спам</strong>
          </p>

          {message ? (
            <p className={styles.successMsg} role="status">
              {message}
            </p>
          ) : null}
          {error ? (
            <p className={styles.errorMsg} role="alert">
              {error}
            </p>
          ) : null}

          <div className={styles.actions}>
            <button type="submit" className={styles.btnConfirm} disabled={busy || verified}>
              {busy ? '…' : 'Подтвердить'}
            </button>
            <button
              type="button"
              className={styles.btnGhost}
              onClick={handleResend}
              disabled={secondsLeft > 0 || resendBusy || verified}
            >
              {secondsLeft > 0
                ? `Отправить ещё раз (${formatMmSs(secondsLeft)})`
                : resendBusy
                  ? '…'
                  : 'Отправить ещё раз'}
            </button>
            <button type="button" className={styles.btnGhost} onClick={handleBack}>
              Назад к регистрации
            </button>
          </div>
        </form>

        {verified ? (
          <p className={styles.afterVerify}>
            <Link className={styles.loginLink} to="/login">
              Перейти ко входу
            </Link>
          </p>
        ) : null}
      </div>
    </section>
  );
}
