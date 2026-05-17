export const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

export const AUTH_STORAGE_KEY = "ooa_auth";

export function readStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function getAuthToken() {
  const auth = readStoredAuth();
  return auth?.sessionId || auth?.accessToken || null;
}

export async function parseErrorResponse(res, fallback = "Request failed") {
  const body = await res.json().catch(() => ({}));
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  return fallback;
}

export async function apiFetch(path, options = {}) {
  const token = getAuthToken();
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const message = await parseErrorResponse(res);
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}
