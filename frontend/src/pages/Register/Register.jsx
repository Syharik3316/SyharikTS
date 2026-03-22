import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import ReCAPTCHA from 'react-google-recaptcha';
import * as authApi from '../../api/authApi';
import { PENDING_VERIFY_EMAIL_KEY } from '../../constants/authFlow';
import HoldToRevealPasswordField from '../../components/HoldToRevealPasswordField/HoldToRevealPasswordField.jsx';
import styles from './Register.module.css';

const SITE_KEY = (import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? '').trim();

const LOGIN_PATTERN = /^[a-zA-Z0-9_]{3,64}$/;

/**
 * @param {string} password
 * @param {string} passwordRepeat
 */
export function validatePasswordsMatch(password, passwordRepeat) {
  return password === passwordRepeat;
}

/**
 * @param {string} email
 */
export function validateEmailFormat(email) {
  const s = String(email).trim();
  if (!s) return false;
  if (s.includes(' ') || s.split('@').length !== 2) return false;
  const [local, domain] = s.split('@');
  if (!local || !domain) return false;
  if (domain.startsWith('.') || domain.endsWith('.')) return false;
  const lastDot = domain.lastIndexOf('.');
  if (lastDot <= 0 || lastDot >= domain.length - 1) return false;
  const tld = domain.slice(lastDot + 1);
  if (tld.length < 2) return false;
  if (!/^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$/.test(tld)) return false;
  if (!/^[\w!#$%&'*+/=?^`{|}~.-]+$/.test(local)) return false;
  const host = domain.slice(0, lastDot);
  if (!host || !/^[\w-]+(\.[\w-]+)*$/.test(host)) return false;
  return true;
}

export default function Register() {
  const navigate = useNavigate();
  const location = useLocation();
  const [login, setLogin] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordRepeat, setPasswordRepeat] = useState('');
  const [passwordMismatch, setPasswordMismatch] = useState(false);
  const [formError, setFormError] = useState('');
  const [emailInvalid, setEmailInvalid] = useState(false);
  const [captchaToken, setCaptchaToken] = useState(null);
  const captchaRef = useRef(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const r = location.state?.fromConfirm;
    if (r) {
      setLogin(r.login ?? '');
      setEmail(r.email ?? '');
      setPassword(r.password ?? '');
      setPasswordRepeat(r.passwordRepeat ?? '');
      setPasswordMismatch(false);
      setFormError('');
      setEmailInvalid(false);
      setCaptchaToken(null);
      captchaRef.current?.reset();
    }
  }, [location.key, location.state]);

  const clearPasswordErrors = () => {
    setPasswordMismatch(false);
    setFormError('');
  };

  const handlePasswordChange = (e) => {
    setPassword(e.target.value);
    clearPasswordErrors();
  };

  const handlePasswordRepeatChange = (e) => {
    setPasswordRepeat(e.target.value);
    clearPasswordErrors();
  };

  const handleEmailChange = (e) => {
    setEmail(e.target.value);
    setEmailInvalid(false);
    setFormError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setEmailInvalid(false);

    if (!SITE_KEY) {
      setFormError('Регистрация недоступна: не задан VITE_RECAPTCHA_SITE_KEY при сборке.');
      return;
    }

    if (!validateEmailFormat(email)) {
      setEmailInvalid(true);
      setFormError(
        'Укажите корректный e-mail в формате имя@домен.зона (например, user@mail.com).',
      );
      return;
    }

    const loginTrim = login.trim();
    if (!LOGIN_PATTERN.test(loginTrim)) {
      setFormError('Логин: 3–64 символа, только латиница, цифры и подчёркивание.');
      return;
    }

    if (password.length < 8) {
      setFormError('Пароль должен быть не короче 8 символов.');
      return;
    }

    if (!validatePasswordsMatch(password, passwordRepeat)) {
      setPasswordMismatch(true);
      return;
    }

    if (!captchaToken) {
      setFormError('Пройдите проверку reCAPTCHA.');
      return;
    }

    setBusy(true);
    try {
      await authApi.registerRequest(email.trim(), loginTrim, password, captchaToken);
      captchaRef.current?.reset();
      setCaptchaToken(null);
      try {
        sessionStorage.setItem(PENDING_VERIFY_EMAIL_KEY, email.trim());
      } catch {
        //Fuck PotJoke
      }
      navigate('/verify-email', { replace: true });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.page} aria-label="Регистрация аккаунта">
      <div className={styles.card}>
        <h1 className={styles.title}>Регистрация</h1>
        <p className={styles.intro}>
          После регистрации мы отправим код подтверждения на почту.
        </p>

        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="reg-login">
              Логин
            </label>
            <input
              id="reg-login"
              className={styles.input}
              type="text"
              name="login"
              autoComplete="username"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              placeholder="латиница, цифры, _ — 3–64 символа"
              maxLength={64}
              required
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label} htmlFor="reg-email">
              Email
            </label>
            <input
              id="reg-email"
              className={`${styles.input} ${emailInvalid ? styles.inputError : ''}`}
              type="email"
              name="email"
              autoComplete="email"
              value={email}
              onChange={handleEmailChange}
              placeholder="syharik@example.ru"
              required
            />
          </div>

          <HoldToRevealPasswordField
            id="reg-password"
            label="Пароль"
            name="password"
            autoComplete="new-password"
            value={password}
            onChange={handlePasswordChange}
            placeholder="мин. 8 символов"
          />

          <HoldToRevealPasswordField
            id="reg-password-repeat"
            label="Повторите пароль"
            name="passwordRepeat"
            autoComplete="new-password"
            value={passwordRepeat}
            onChange={handlePasswordRepeatChange}
            placeholder="Не жульничать!"
            hasError={passwordMismatch}
            errorText={
              passwordMismatch ? 'Пароли не совпадают. Проверьте ввод.' : ''
            }
          />

          {SITE_KEY ? (
            <div className={styles.captchaWrap}>
              <ReCAPTCHA
                ref={captchaRef}
                sitekey={SITE_KEY}
                onChange={(t) => setCaptchaToken(t)}
                onExpired={() => setCaptchaToken(null)}
              />
            </div>
          ) : (
            <p className={styles.formError} role="alert">
              Регистрация недоступна: задайте VITE_RECAPTCHA_SITE_KEY (см. .env.example).
            </p>
          )}

          {formError ? (
            <p className={styles.formError} role="alert">
              {formError}
            </p>
          ) : null}

          <div className={styles.actions}>
            <button type="submit" className={styles.submit} disabled={busy || !SITE_KEY}>
              {busy ? '…' : 'Создать аккаунт'}
            </button>
            <Link className={styles.backLink} to="/login">
              Назад
            </Link>
          </div>
        </form>
      </div>
    </section>
  );
}
