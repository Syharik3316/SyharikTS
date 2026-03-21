import React from "react";
import { Link } from "react-router-dom";
import ReCAPTCHA from "react-google-recaptcha";
import * as authApi from "../api/authApi";

const SITE_KEY = (import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? "").trim();

export default function ResetPasswordPage() {
  const [step, setStep] = React.useState<1 | 2>(1);
  const [email, setEmail] = React.useState("");
  const [code, setCode] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [captchaToken, setCaptchaToken] = React.useState<string | null>(null);
  const captchaRef = React.useRef<ReCAPTCHA>(null);

  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  async function onRequest(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    if (!SITE_KEY) {
      setError("Сброс пароля недоступен: при сборке не задан VITE_RECAPTCHA_SITE_KEY.");
      return;
    }
    if (!captchaToken) {
      setError("Пройдите проверку reCAPTCHA.");
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

  async function onConfirm(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
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
    <div className="container" style={{ maxWidth: 440 }}>
      <h1 style={{ marginTop: 0 }}>Сброс пароля</h1>

      {step === 1 ? (
        <form className="card" onSubmit={onRequest}>
          <p className="hint">Укажите email аккаунта. Если он есть в системе, мы отправим код.</p>
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
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
              Сброс пароля недоступен: задайте VITE_RECAPTCHA_SITE_KEY при сборке frontend (см. .env.example).
            </div>
          )}
          <div style={{ marginTop: 16 }}>
            <button type="submit" disabled={busy || !SITE_KEY}>
              {busy ? "…" : "Отправить код"}
            </button>
          </div>
        </form>
      ) : (
        <form className="card" onSubmit={onConfirm}>
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <label style={{ marginTop: 12 }}>Код из письма</label>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            required
          />
          <label style={{ marginTop: 12 }}>Новый пароль</label>
          <input
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
          />
          <div style={{ marginTop: 16 }}>
            <button type="submit" disabled={busy}>
              {busy ? "…" : "Сменить пароль"}
            </button>
          </div>
          <p className="hint" style={{ marginTop: 12 }}>
            <button type="button" onClick={() => setStep(1)} style={{ background: "transparent", border: "none", padding: 0, color: "#9ab", cursor: "pointer", textDecoration: "underline" }}>
              Запросить код снова
            </button>
          </p>
        </form>
      )}

      {message ? <div style={{ marginTop: 12, color: "#8fd694" }}>{message}</div> : null}
      {error ? <div className="error" style={{ marginTop: 12 }}>{error}</div> : null}

      <p className="hint" style={{ marginTop: 16 }}>
        <Link to="/login">Назад к входу</Link>
      </p>
    </div>
  );
}
