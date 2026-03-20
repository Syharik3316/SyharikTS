import React from "react";
import ReCAPTCHA from "react-google-recaptcha";
import { useAuth } from "../AuthContext";
import { ApiError } from "../../httpError";

const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? "";

export default function ForgotPasswordModal(props: {
  open: boolean;
  onClose: () => void;
  onResetCodeSent: (identifier: string) => void;
}) {
  const { open, onClose, onResetCodeSent } = props;
  const { requestPasswordReset } = useAuth();

  const [identifier, setIdentifier] = React.useState("");
  const [recaptchaToken, setRecaptchaToken] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!open) return;
    setIdentifier("");
    setRecaptchaToken("");
    setLoading(false);
    setError("");
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
      await requestPasswordReset({ identifier, recaptchaToken });
      onResetCodeSent(identifier);
    } catch (e) {
      setError(e instanceof ApiError ? e.userMessage : e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modalOverlay">
      <div className="modal">
        <h2 style={{ marginTop: 0 }}>Восстановление пароля</h2>

        <div style={{ marginTop: 10 }}>
          <label>Почта или логин</label>
          <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} type="text" />
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
          <button onClick={onSubmit} disabled={loading || !identifier.trim()}>
            {loading ? "Отправляем..." : "Отправить код"}
          </button>
        </div>
      </div>
    </div>
  );
}

