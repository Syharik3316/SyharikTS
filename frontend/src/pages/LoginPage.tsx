import React from "react";
import { Link, useNavigate } from "react-router-dom";
import ReCAPTCHA from "react-google-recaptcha";
import * as authApi from "../api/authApi";
import { PENDING_VERIFY_EMAIL_KEY } from "../constants/authFlow";
import { useAuth } from "../context/AuthContext";

const SITE_KEY = (import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? "").trim();

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [mode, setMode] = React.useState<"login" | "register">("login");

  const [loginOrEmail, setLoginOrEmail] = React.useState("");
  const [password, setPassword] = React.useState("");

  const [regEmail, setRegEmail] = React.useState("");
  const [regLogin, setRegLogin] = React.useState("");
  const [regPassword, setRegPassword] = React.useState("");
  const [captchaToken, setCaptchaToken] = React.useState<string | null>(null);
  const captchaRef = React.useRef<ReCAPTCHA>(null);

  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  async function onLoginSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(loginOrEmail.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRegisterSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!SITE_KEY) {
      setError("Регистрация недоступна: при сборке не задан VITE_RECAPTCHA_SITE_KEY.");
      return;
    }
    if (!captchaToken) {
      setError("Пройдите проверку reCAPTCHA.");
      return;
    }
    setBusy(true);
    try {
      await authApi.registerRequest(regEmail.trim(), regLogin.trim(), regPassword, captchaToken);
      captchaRef.current?.reset();
      setCaptchaToken(null);
      try {
        sessionStorage.setItem(PENDING_VERIFY_EMAIL_KEY, regEmail.trim());
      } catch {
        /* ignore */
      }
      navigate("/verify-email", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const disabled = busy;

  return (
    <div className="container" style={{ maxWidth: 440 }}>
      <h1 style={{ marginTop: 0 }}>SyharikTS</h1>
      <p className="hint">Вход или регистрация для доступа к генератору.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button type="button" onClick={() => setMode("login")} disabled={mode === "login"}>
          Вход
        </button>
        <button type="button" onClick={() => setMode("register")} disabled={mode === "register"}>
          Регистрация
        </button>
      </div>

      {mode === "login" ? (
        <form className="card" onSubmit={onLoginSubmit}>
          <label>Логин или email</label>
          <input
            type="text"
            autoComplete="username"
            value={loginOrEmail}
            onChange={(e) => setLoginOrEmail(e.target.value)}
            required
          />
          <label style={{ marginTop: 12 }}>Пароль</label>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <div style={{ marginTop: 16 }}>
            <button type="submit" disabled={disabled}>
              {disabled ? "…" : "Войти"}
            </button>
          </div>
          <p className="hint" style={{ marginTop: 12 }}>
            <Link to="/reset-password">Забыли пароль?</Link>
          </p>
        </form>
      ) : (
        <form className="card" onSubmit={onRegisterSubmit}>
          <label>Email</label>
          <input type="email" value={regEmail} onChange={(e) => setRegEmail(e.target.value)} required />
          <label style={{ marginTop: 12 }}>Логин</label>
          <input
            type="text"
            autoComplete="username"
            value={regLogin}
            onChange={(e) => setRegLogin(e.target.value)}
            required
            minLength={3}
            maxLength={64}
            pattern="[a-zA-Z0-9_]{3,64}"
            title="Буквы, цифры, подчёркивание, 3–64 символа"
          />
          <label style={{ marginTop: 12 }}>Пароль (мин. 8 символов)</label>
          <input
            type="password"
            autoComplete="new-password"
            value={regPassword}
            onChange={(e) => setRegPassword(e.target.value)}
            required
            minLength={8}
          />
          {SITE_KEY ? (
            <div style={{ marginTop: 12 }}>
              <ReCAPTCHA
                ref={captchaRef}
                sitekey={SITE_KEY}
                onChange={(t: string | null) => setCaptchaToken(t)}
                onExpired={() => setCaptchaToken(null)}
              />
            </div>
          ) : (
            <div className="error" style={{ marginTop: 12 }}>
              Регистрация недоступна: задайте VITE_RECAPTCHA_SITE_KEY при сборке frontend (см. .env.example).
            </div>
          )}
          <div style={{ marginTop: 16 }}>
            <button type="submit" disabled={disabled || !SITE_KEY}>
              {disabled ? "…" : "Зарегистрироваться"}
            </button>
          </div>
        </form>
      )}

      {error ? <div className="error" style={{ marginTop: 12 }}>{error}</div> : null}
    </div>
  );
}
