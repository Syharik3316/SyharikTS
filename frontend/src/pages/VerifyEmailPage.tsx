import React from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ResendCooldownError, resendRegistrationCode, verifyEmailRequest } from "../api/authApi";
import { PENDING_VERIFY_EMAIL_KEY } from "../constants/authFlow";

const RESEND_COOLDOWN_SEC = 60;

function formatMmSs(total: number): string {
  const s = Math.max(0, Math.floor(total));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export default function VerifyEmailPage() {
  const navigate = useNavigate();
  const email = React.useMemo(() => {
    try {
      return sessionStorage.getItem(PENDING_VERIFY_EMAIL_KEY);
    } catch {
      return null;
    }
  }, []);

  const [code, setCode] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [resendBusy, setResendBusy] = React.useState(false);
  const [secondsLeft, setSecondsLeft] = React.useState(RESEND_COOLDOWN_SEC);
  const [verified, setVerified] = React.useState(false);

  React.useEffect(() => {
    if (secondsLeft <= 0) return;
    const id = window.setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => window.clearTimeout(id);
  }, [secondsLeft]);

  if (!email) {
    return <Navigate to="/login" replace />;
  }

  const pendingEmail = email;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
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
  }

  async function onResend() {
    if (secondsLeft > 0 || resendBusy || verified) return;
    setError("");
    setMessage("");
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
  }

  function onBackToLogin() {
    try {
      sessionStorage.removeItem(PENDING_VERIFY_EMAIL_KEY);
    } catch {
      /* ignore */
    }
    navigate("/login", { replace: true });
  }

  return (
    <div className="container" style={{ maxWidth: 440 }}>
      <h1 style={{ marginTop: 0 }}>Подтверждение email</h1>

      <div className="card" style={{ marginBottom: 12 }}>
        <p style={{ margin: 0, fontSize: 15 }}>
          Код отправлен на: <strong>{pendingEmail}</strong>
        </p>
        <p className="hint" style={{ marginTop: 8, marginBottom: 0 }}>
          Введите 6-значный код из письма. Повторная отправка — не чаще одного раза в минуту.
        </p>
      </div>

      <form className="card" onSubmit={onSubmit}>
        <label>Код из письма</label>
        <input
          type="text"
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          required
          disabled={verified}
        />
        <div style={{ marginTop: 16 }}>
          <button type="submit" disabled={busy || verified}>
            {busy ? "…" : "Подтвердить"}
          </button>
        </div>

        <div style={{ marginTop: 16 }}>
          <button
            type="button"
            onClick={onResend}
            disabled={secondsLeft > 0 || resendBusy || verified}
          >
            {secondsLeft > 0
              ? `Отправить код снова (${formatMmSs(secondsLeft)})`
              : resendBusy
                ? "…"
                : "Отправить код снова"}
          </button>
        </div>

        <p className="hint" style={{ marginTop: 16 }}>
          <button
            type="button"
            onClick={onBackToLogin}
            style={{ background: "transparent", border: "none", padding: 0, color: "#9ab", cursor: "pointer", textDecoration: "underline" }}
          >
            Назад к входу
          </button>
        </p>
      </form>

      {message ? <div style={{ marginTop: 12, color: "#8fd694" }}>{message}</div> : null}
      {error ? <div className="error" style={{ marginTop: 12 }}>{error}</div> : null}

      {verified ? (
        <p className="hint" style={{ marginTop: 16 }}>
          <Link to="/login">Перейти ко входу</Link>
        </p>
      ) : null}
    </div>
  );
}
