import { API_BASE, apiFetch, getAuthToken, parseErrorResponse } from "../config/api";

export const adminApi = {
  me: () => apiFetch("/auth/me"),
  users: (params = {}) => {
    const q = new URLSearchParams();
    if (params.search) q.set("search", params.search);
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    const qs = q.toString();
    return apiFetch(`/admin/users${qs ? `?${qs}` : ""}`);
  },
  user: (id) => apiFetch(`/admin/users/${id}`),
  createUser: (body) => apiFetch("/admin/users", { method: "POST", body: JSON.stringify(body) }),
  updateUser: (id, body) =>
    apiFetch(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteUser: (id) => apiFetch(`/admin/users/${id}`, { method: "DELETE" }),
  activateUser: (id) => apiFetch(`/admin/users/${id}/activate`, { method: "POST" }),
  deactivateUser: (id) => apiFetch(`/admin/users/${id}/deactivate`, { method: "POST" }),
  unlockUser: (id) => apiFetch(`/admin/users/${id}/unlock`, { method: "POST" }),
  userSessions: (id) => apiFetch(`/admin/users/${id}/sessions`),
  revokeUserSessions: (id) => apiFetch(`/admin/users/${id}/sessions`, { method: "DELETE" }),
  userAudit: (id, params = {}) => {
    const q = new URLSearchParams(params);
    return apiFetch(`/admin/users/${id}/audit?${q}`);
  },
  assignRole: (userId, roleId) =>
    apiFetch(`/admin/users/${userId}/roles`, {
      method: "POST",
      body: JSON.stringify({ role_id: roleId }),
    }),
  removeRole: (userId, roleId) =>
    apiFetch(`/admin/users/${userId}/roles/${roleId}`, { method: "DELETE" }),
  roles: () => apiFetch("/admin/roles"),
  rolePermissions: (roleId) => apiFetch(`/admin/roles/${roleId}/permissions`),
  createRole: (body) => apiFetch("/admin/roles", { method: "POST", body: JSON.stringify(body) }),
  updateRole: (id, body) =>
    apiFetch(`/admin/roles/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRole: (id) => apiFetch(`/admin/roles/${id}`, { method: "DELETE" }),
  grantRolePermission: (roleId, permissionId) =>
    apiFetch(`/admin/roles/${roleId}/permissions`, {
      method: "POST",
      body: JSON.stringify({ permission_id: permissionId }),
    }),
  revokeRolePermission: (roleId, permissionId) =>
    apiFetch(`/admin/roles/${roleId}/permissions/${permissionId}`, { method: "DELETE" }),
  permissions: () => apiFetch("/admin/permissions"),
  departments: () => apiFetch("/admin/departments"),
  createDepartment: (body) =>
    apiFetch("/admin/departments", { method: "POST", body: JSON.stringify(body) }),
  updateDepartment: (id, body) =>
    apiFetch(`/admin/departments/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  departmentUsers: (id) => apiFetch(`/admin/departments/${id}/users`),
  featureFlags: () => apiFetch("/admin/feature-flags"),
  updateFeatureFlag: (id, body) =>
    apiFetch(`/admin/feature-flags/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  createFeatureFlag: (body) =>
    apiFetch("/admin/feature-flags", { method: "POST", body: JSON.stringify(body) }),
  audit: (params = {}) => {
    const q = new URLSearchParams(params);
    return apiFetch(`/admin/audit?${q}`);
  },
  usage: (params = {}) => {
    const q = new URLSearchParams(params);
    return apiFetch(`/admin/usage?${q}`);
  },
  usageByUser: (params = {}) => {
    const q = new URLSearchParams(params);
    return apiFetch(`/admin/usage/by-user?${q}`);
  },
  usageByDepartment: (params = {}) => {
    const q = new URLSearchParams(params);
    return apiFetch(`/admin/usage/by-department?${q}`);
  },
  usageCosts: (params = {}) => {
    const q = new URLSearchParams(params);
    return apiFetch(`/admin/usage/costs?${q}`);
  },
  securitySummary: () => apiFetch("/admin/security/summary"),
  profileSecurity: () => apiFetch("/profile/security"),
  mfaSetup: () => apiFetch("/auth/mfa/setup", { method: "POST" }),
  mfaConfirm: (code) =>
    apiFetch("/auth/mfa/confirm", { method: "POST", body: JSON.stringify({ code }) }),
  mfaDisable: (code) =>
    apiFetch("/auth/mfa", { method: "DELETE", body: JSON.stringify({ code }) }),
  auditExport: async (params = {}) => {
    const q = new URLSearchParams(params);
    const token = getAuthToken();
    const res = await fetch(`${API_BASE}/admin/audit/export?${q}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      throw new Error(await parseErrorResponse(res, "Export failed"));
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-export-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  },
};
