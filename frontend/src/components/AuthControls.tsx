import React from "react";
import { useAuth } from "../auth/AuthContext";

export default function AuthControls(props: { onOpenAuth: (tab: "login" | "register" | "forgot") => void }) {
  const { user, loading, logout } = useAuth();

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
      {loading ? <div style={{ opacity: 0.8, fontSize: 13 }}>Загрузка...</div> : null}
      {!loading && user ? (
        <>
          <div style={{ opacity: 0.9, fontSize: 13 }}>
            Пользователь: <b>{user.login}</b>
          </div>
          <button onClick={logout}>Выйти</button>
        </>
      ) : null}
      {!loading && !user ? (
        <>
          <button onClick={() => props.onOpenAuth("login")}>Войти</button>
          <button onClick={() => props.onOpenAuth("register")}>Регистрация</button>
        </>
      ) : null}
    </div>
  );
}

