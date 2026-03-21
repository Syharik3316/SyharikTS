import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import PrivateRoute from "./components/PrivateRoute";
import { useAuth } from "./context/AuthContext";
import Home from "./pages/Home/Home.jsx";
import Login from "./pages/Login/Login.jsx";
import Register from "./pages/Register/Register.jsx";
import RegisterConfirm from "./pages/RegisterConfirm/RegisterConfirm.jsx";
import ResetPassword from "./pages/ResetPassword/ResetPassword.jsx";
import Upload from "./pages/Upload/Upload.jsx";
import Profile from "./pages/Profile/Profile.jsx";
import GenerationDetail from "./pages/GenerationDetail/GenerationDetail.jsx";
import TechInfo from "./pages/TechInfo/TechInfo.jsx";

function GuestRoute({ children }: { children: React.ReactNode }) {
  const { user, ready, bootstrapping } = useAuth();
  if (!ready || bootstrapping) {
    return <div className="sessionLoading">Загрузка…</div>;
  }
  if (user) {
    return <Navigate to="/upload" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route
        path="/login"
        element={
          <GuestRoute>
            <Login />
          </GuestRoute>
        }
      />
      <Route
        path="/register"
        element={
          <GuestRoute>
            <Register />
          </GuestRoute>
        }
      />
      <Route path="/verify-email" element={<RegisterConfirm />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route
        path="/upload"
        element={
          <PrivateRoute>
            <Upload />
          </PrivateRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <PrivateRoute>
            <Profile />
          </PrivateRoute>
        }
      />
      <Route
        path="/profile/generations/:id"
        element={
          <PrivateRoute>
            <GenerationDetail />
          </PrivateRoute>
        }
      />
      <Route
        path="/profile/tech"
        element={
          <PrivateRoute>
            <TechInfo />
          </PrivateRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
