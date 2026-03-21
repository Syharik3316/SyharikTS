import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import PrivateRoute from "./components/PrivateRoute";
import { useAuth } from "./context/AuthContext";
import CheckPage from "./pages/CheckPage";
import GeneratorPage from "./pages/GeneratorPage";
import LoginPage from "./pages/LoginPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";

function LoginRoute() {
  const { user, ready, bootstrapping } = useAuth();
  if (bootstrapping || !ready) {
    return (
      <div className="container">
        <p className="hint">Загрузка…</p>
      </div>
    );
  }
  if (user) {
    return <Navigate to="/generator" replace />;
  }
  return <LoginPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Navigate to="/generator" replace />
          </PrivateRoute>
        }
      />
      <Route
        path="/generator"
        element={
          <PrivateRoute>
            <GeneratorPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/check"
        element={
          <PrivateRoute>
            <CheckPage />
          </PrivateRoute>
        }
      />
      <Route path="*" element={<Navigate to="/generator" replace />} />
    </Routes>
  );
}
