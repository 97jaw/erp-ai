import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AdminLayout from "./components/AdminLayout";
import AdminGate from "./AdminGate";
import Dashboard from "./pages/Dashboard";
import UsersList from "./pages/UsersList";
import UserDetail from "./pages/UserDetail";
import UserCreate from "./pages/UserCreate";
import RolesList from "./pages/RolesList";
import RoleDetail from "./pages/RoleDetail";
import DepartmentsPage from "./pages/DepartmentsPage";
import PermissionsPage from "./pages/PermissionsPage";
import FeatureFlagsPage from "./pages/FeatureFlagsPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import UsagePage from "./pages/UsagePage";
import SecurityPage from "./pages/SecurityPage";
import MonitoringPage from "./pages/MonitoringPage";

export default function AdminApp({ user, onLogout }) {
  useEffect(() => {
    document.body.classList.add("ooa-admin-route");
    return () => document.body.classList.remove("ooa-admin-route");
  }, []);

  return (
    <div className="ooa-admin-app">
      <AdminGate>
      <Routes>
        <Route element={<AdminLayout user={user} onLogout={onLogout} />}>
          <Route index element={<Dashboard />} />
          <Route path="users" element={<UsersList />} />
          <Route path="users/new" element={<UserCreate />} />
          <Route path="users/:id" element={<UserDetail />} />
          <Route path="roles" element={<RolesList />} />
          <Route path="roles/:id" element={<RoleDetail />} />
          <Route path="departments" element={<DepartmentsPage />} />
          <Route path="permissions" element={<PermissionsPage />} />
          <Route path="feature-flags" element={<FeatureFlagsPage />} />
          <Route path="audit-logs" element={<AuditLogsPage />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="monitoring" element={<MonitoringPage />} />
          <Route path="security" element={<SecurityPage />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Route>
      </Routes>
      </AdminGate>
    </div>
  );
}
