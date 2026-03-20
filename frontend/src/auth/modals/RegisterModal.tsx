import React from "react";
import ReCAPTCHA from "react-google-recaptcha";
import { useAuth } from "../AuthContext";
import { ApiError } from "../../httpError";

const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? "";

export default function RegisterModal(props: {
  open: boolean;
  onClose: () => void;
  onSwitchToLogin: () => void;
}) {
  const { open, onClose, onSwitchToLogin } = props;
  const { register, verifyEmail } = useAuth();

  const [email, setEmail] = React.useState("");
  const [login, setLogin] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [recaptchaToken, setRecaptchaToken] = React.useState("");
  const [code, setCode] = React.useState("");

  const [step, setStep] = React.useState<"form" | "verify">("form");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!open) return;
    setEmail("");
    setLogin("");
    setPassword("");
    setRecaptchaToken("");
    setCode("");
    setStep("form");
    setLoading(false);
    setError("");
  }, [open]);

  if (!open) return null;

  async function onRegister() {
    setError("");
    if (!RECAPTCHA_SITE_KEY) {
      setError("ReCaptcha site key is not configured");
      return;
    }
    if (!recaptchaToken) {
      setError("Please confirm ReCaptcha");
      return;
    }
    try {
      setLoading(true);
      await register({ email, login, password, recaptchaToken });
      setStep("verify");
    } catch (e) {
      setError(e instanceof ApiError ? e.userMessage : e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function onVerify() {
    setError("");
    if (!code.trim()) {
      setError("Enter code");
      return;
    }
    try {
      setLoading(true);
      await verifyEmail({ email, code });
      onClose();
      onSwitchToLogin();
    } catch (e) {
      setError(e instanceof ApiError ? e.userMessage : e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modalOverlay">
      <div className="modal">
        <h2 style={{ marginTop: 0 }}>{step === "form" ? "Регистрация" : "Подтверждение email"}</h2>

        {step === "form" ? (
          <>
            <div style={{ marginTop: 10 }}>
              <label>Почта</label>
              <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
            </div>

            <div style={{ marginTop: 10 }}>
              <label>Логин</label>
              <input value={login} onChange={(e) => setLogin(e.target.value)} type="text" />
            </div>

            <div style={{ marginTop: 10 }}>
              <label>Пароль</label>
              <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" />
            </div>

            <div style={{ marginTop: 14 }}>
              <ReCAPTCHA
                sitekey={RECAPTCHA_SITE_KEY}
                onChange={(t: string | null) => setRecaptchaToken(t ? String(t) : "")}
              />
            </div>

            {error ? <div className="error">{error}</div> : null}

            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              <button onClick={onClose} disabled={loading}>
                Закрыть
              </button>
              <button onClick={onRegister} disabled={loading || !email.trim() || !login.trim() || !password.trim()}>
                {loading ? "Отправляем..." : "Зарегистрироваться"}
              </button>
            </div>
          </>
        ) : (
          <>
            <div style={{ marginTop: 10 }}>
              <label>Код подтверждения</label>
              <input value={code} onChange={(e) => setCode(e.target.value)} type="text" inputMode="numeric" />
            </div>

            {error ? <div className="error">{error}</div> : null}

            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              <button onClick={onClose} disabled={loading}>
                Закрыть
              </button>
              <button onClick={onVerify} disabled={loading || !code.trim()}>
                {loading ? "Проверяем..." : "Подтвердить"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

