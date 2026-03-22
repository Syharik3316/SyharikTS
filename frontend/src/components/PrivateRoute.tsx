import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, ready, bootstrapping } = useAuth();

  if (!ready || bootstrapping) {
    return <div className="sessionLoading">Загрузка сессии…</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
