import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ChatScreen from "./components/chat/ChatScreen";
import AdminApp from "./admin/AdminApp";
import { ThemeProvider } from "./theme/ThemeProvider";
import {
  AUTH_STORAGE_KEY,
  clearStoredAuth,
  persistAuth,
  readStoredAuth,
  setAuthFailureHandler,
  validateStoredAuth,
} from "./config/api";
import { SplashScreen } from "./splash";
import { consumeSplashQuery, shouldAutoSkipSplash } from "./splash/splashStorage";
import IntegrationPage from "./main/integrations/IntegrationPage";
import "./splash/styles/splash.css";

function AuthenticatedApp({ auth, pendingQuery, onLogout }) {
  return (
    <Routes>
      <Route
        path="/integrations/:serviceId"
        element={
          <IntegrationPage user={auth} onLogout={onLogout} />
        }
      />
      <Route
        path="*"
        element={
          <ChatScreen
            user={auth}
            initialSpotlightQuery={pendingQuery}
            onLogout={onLogout}
          />
        }
      />
    </Routes>
  );
}

export default function App() {
  const [auth, setAuth] = useState(() => readStoredAuth());
  const [showSplash, setShowSplash] = useState(() => {
    const stored = readStoredAuth();
    return Boolean(stored) && !shouldAutoSkipSplash();
  });
  const [pendingQuery, setPendingQuery] = useState("");

  useEffect(() => {
    persistAuth(auth);
  }, [auth]);

  useEffect(() => {
    setAuthFailureHandler(() => {
      setAuth(null);
      setShowSplash(false);
      setPendingQuery("");
    });
    return () => setAuthFailureHandler(null);
  }, []);

  useEffect(() => {
    if (!auth) return undefined;
    let cancelled = false;
    (async () => {
      const ok = await validateStoredAuth();
      if (!cancelled && !ok) setAuth(null);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleAuthenticated = (payload) => {
    setAuth({
      sessionId: payload.accessToken || payload.sessionId,
      accessToken: payload.accessToken || payload.sessionId,
      refreshToken: payload.refreshToken || "",
      expiresAt: payload.expiresAt || null,
      userName: payload.userName,
      language: payload.language,
      fileId: payload.fileId,
      welcomeTitle: payload.welcomeTitle,
      welcomeMessage: payload.welcomeMessage,
      roles: payload.roles || [],
      permissions: payload.permissions || [],
    });
    setShowSplash(!shouldAutoSkipSplash());
  };

  const handleSplashComplete = () => {
    const query = consumeSplashQuery();
    setPendingQuery(query);
    setShowSplash(false);
  };

  const handleLogout = () => {
    clearStoredAuth();
    localStorage.removeItem("ooa_messages");
    localStorage.removeItem("ooa_queries");
    localStorage.removeItem("ooa_suggestions_shown");
    setAuth(null);
    setShowSplash(false);
    setPendingQuery("");
  };

  return (
    <ThemeProvider>
      <BrowserRouter>
        <a className="ooa-skip-link" href="#ooa-chat-main">
          Skip to chat
        </a>
        <Routes>
          <Route
            path="/admin/*"
            element={
              auth ? (
                <AdminApp user={auth} onLogout={handleLogout} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/*"
            element={
              showSplash || !auth ? (
                <SplashScreen
                  user={auth}
                  onAuthenticated={handleAuthenticated}
                  onSkipToChat={handleSplashComplete}
                />
              ) : (
                <AuthenticatedApp
                  auth={auth}
                  pendingQuery={pendingQuery}
                  onLogout={handleLogout}
                />
              )
            }
          />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
