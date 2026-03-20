import React from "react";
import ReCAPTCHA from "react-google-recaptcha";
import { useAuth } from "../AuthContext";
import { ApiError } from "../../httpError";

const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? "";

export default function LoginModal(props: {
  open: boolean;
  onClose: () => void;
  onSwitchToForgot: () => void;
  onLoginSuccess: () => void;
}) {
  const { open, onClose, onSwitchToForgot, onLoginSuccess } = props;
  const { login } = useAuth();

  const [identifier, setIdentifier] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [recaptchaToken, setRecaptchaToken] = React.useState<string>("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string>("");

  React.useEffect(() => {
    if (!open) return;
    setIdentifier("");
    setPassword("");
    setRecaptchaToken("");
    setError("");
    setLoading(false);
  }, [open]);

  if (!open) return null;

  async function onSubmit() {
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
      await login({ identifier, password, recaptchaToken });
      onLoginSuccess();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.userMessage : e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modalOverlay">
      <div className="modal">
        <h2 style={{ marginTop: 0 }}>Вход</h2>

        <div style={{ marginTop: 10 }}>
          <label>Почта или логин</label>
          <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} type="text" />
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
          <button onClick={onSubmit} disabled={loading || !identifier.trim() || !password.trim()}>
            {loading ? "Входим..." : "Войти"}
          </button>
        </div>

        <div style={{ marginTop: 12, fontSize: 13, opacity: 0.85 }}>
          <button
            onClick={() => {
              onClose();
              onSwitchToForgot();
            }}
            disabled={loading}
            style={{ padding: 0, border: "none", background: "transparent", color: "#e7eaf0" }}
          >
            Забыли пароль?
          </button>
        </div>
      </div>
    </div>
  );
}

