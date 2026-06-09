/** Resolve API base at call time so production always uses the page origin. */
export function resolveApiBase() {
  const configured = process.env.REACT_APP_API_BASE;
  if (configured && configured.trim()) {
    return configured.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    if (window.location.port === "3000") {
      return "http://localhost:8000";
    }
    return window.location.origin;
  }
  return "http://localhost:8000";
}

/** @deprecated Prefer resolveApiBase() for network calls — kept for static imports. */
export const API_BASE = resolveApiBase();

export const AUTH_STORAGE_KEY = "ooa_auth";

let authFailureHandler = null;
let refreshInFlight = null;

export function isJwt(token) {
  return Boolean(token && typeof token === "string" && token.split(".").length === 3);
}

export function readStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function persistAuth(auth) {
  if (!auth) {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return;
  }
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
}

export function clearStoredAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function setAuthFailureHandler(handler) {
  authFailureHandler = handler;
}

function notifyAuthFailure() {
  clearStoredAuth();
  authFailureHandler?.();
}

export function normalizeAuthFromLogin(body, fileId = "") {
  const accessToken = body.access_token || body.session_id || "";
  const refreshToken = body.refresh_token || "";
  const expiresIn = Number(body.expires_in) || 0;
  return {
    sessionId: accessToken,
    accessToken,
    refreshToken,
    expiresAt: expiresIn > 0 ? Date.now() + expiresIn * 1000 : null,
    userName: body.user_name,
    language: body.language,
    fileId: body.file_id || fileId,
    welcomeTitle: body.welcome_title,
    welcomeMessage: body.welcome_message,
    roles: body.roles || [],
    permissions: body.permissions || [],
    email: body.email || "",
  };
}

export function getAuthToken() {
  const auth = readStoredAuth();
  return auth?.accessToken || auth?.sessionId || null;
}

export async function refreshAccessToken() {
  const auth = readStoredAuth();
  if (!auth?.refreshToken) return null;

  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${resolveApiBase()}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: auth.refreshToken }),
      });
      if (!res.ok) return null;
      const body = await res.json();
      const accessToken = body.access_token || body.session_id;
      if (!accessToken) return null;
      const next = {
        ...auth,
        accessToken,
        sessionId: accessToken,
        refreshToken: body.refresh_token || auth.refreshToken,
        expiresAt: body.expires_in
          ? Date.now() + Number(body.expires_in) * 1000
          : auth.expiresAt,
      };
      persistAuth(next);
      return accessToken;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

export async function getValidAuthToken() {
  const auth = readStoredAuth();
  const token = auth?.accessToken || auth?.sessionId;
  if (!token) return null;

  if (!isJwt(token)) return token;

  const expiresAt = auth?.expiresAt;
  const shouldRefresh =
    auth?.refreshToken && expiresAt && Date.now() >= expiresAt - 60_000;

  if (shouldRefresh) {
    const refreshed = await refreshAccessToken();
    return refreshed || token;
  }

  return token;
}

export async function buildAuthHeaders(extra = {}) {
  const token = await getValidAuthToken();
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/** @deprecated Use buildAuthHeaders() for requests that need a fresh token. */
export function authHeaders(extra = {}) {
  const token = getAuthToken();
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function parseErrorResponse(res, fallback = "Request failed") {
  const body = await res.json().catch(() => ({}));
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  return fallback;
}

async function fetchWithAuth(path, options = {}, { retried = false } = {}) {
  const token = await getValidAuthToken();
  const headers = {
    ...(options.body && !options.headers?.["Content-Type"] && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };
  const res = await fetch(`${resolveApiBase()}${path}`, { ...options, headers });

  if (res.status === 401) {
    const canRetry = !retried && isJwt(token) && readStoredAuth()?.refreshToken;
    if (canRetry) {
      const refreshed = await refreshAccessToken();
      if (refreshed) return fetchWithAuth(path, options, { retried: true });
    }
    if (token) notifyAuthFailure();
  }

  return res;
}

export async function authFetch(path, options = {}) {
  return fetchWithAuth(path, options);
}

export async function apiFetch(path, options = {}) {
  const res = await fetchWithAuth(path, options);
  if (!res.ok) {
    const message = await parseErrorResponse(res);
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function validateStoredAuth() {
  const auth = readStoredAuth();
  const token = auth?.accessToken || auth?.sessionId;
  if (!token) return false;

  if (isJwt(token) && !auth?.refreshToken && auth?.expiresAt && Date.now() >= auth.expiresAt) {
    notifyAuthFailure();
    return false;
  }

  try {
    await apiFetch("/user/profile");
    return true;
  } catch (err) {
    if (err.status === 401) notifyAuthFailure();
    return false;
  }
}
