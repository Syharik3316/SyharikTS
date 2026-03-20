import React from "react";
import { useAuth } from "../AuthContext";
import { ApiError } from "../../httpError";

export default function ResetPasswordModal(props: {
  open: boolean;
  onClose: () => void;
  identifier: string;
  onResetSuccess: () => void;
}) {
  const { open, onClose, identifier, onResetSuccess } = props;
  const { resetPassword } = useAuth();

  const [code, setCode] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!open) return;
    setCode("");
    setNewPassword("");
    setLoading(false);
    setError("");
  }, [open, identifier]);

  if (!open) return null;

  async function onSubmit() {
    setError("");
    if (!code.trim() || !newPassword.trim()) {
      setError("Enter code and new password");
      return;
    }
    try {
      setLoading(true);
      await resetPassword({ identifier, code, newPassword });
      onResetSuccess();
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
        <h2 style={{ marginTop: 0 }}>Сброс пароля</h2>

        <div style={{ marginTop: 10 }}>
          <div style={{ opacity: 0.85, fontSize: 13 }}>Аккаунт: {identifier}</div>
        </div>

        <div style={{ marginTop: 10 }}>
          <label>Код</label>
          <input value={code} onChange={(e) => setCode(e.target.value)} type="text" inputMode="numeric" />
        </div>

        <div style={{ marginTop: 10 }}>
          <label>Новый пароль</label>
          <input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} type="password" />
        </div>

        {error ? <div className="error">{error}</div> : null}

        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <button onClick={onClose} disabled={loading}>
            Закрыть
          </button>
          <button onClick={onSubmit} disabled={loading || !code.trim() || !newPassword.trim()}>
            {loading ? "Сбрасываем..." : "Сбросить пароль"}
          </button>
        </div>
      </div>
    </div>
  );
}

