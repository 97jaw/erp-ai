import { NavLink, Outlet, Link } from "react-router-dom";
import ThemeToggle from "../../components/common/ThemeToggle";
import { SecondaryButton } from "./PageHeader";

const NAV = [
  { to: "/admin", end: true, label: "Dashboard" },
  { to: "/admin/users", label: "Users" },
  { to: "/admin/roles", label: "Roles" },
  { to: "/admin/departments", label: "Departments" },
  { to: "/admin/permissions", label: "Permissions" },
  { to: "/admin/feature-flags", label: "Feature flags" },
  { to: "/admin/usage", label: "Usage" },
  { to: "/admin/monitoring", label: "Monitoring" },
  { to: "/admin/security", label: "Security" },
  { to: "/admin/audit-logs", label: "Audit logs" },
];

export default function AdminLayout({ user, onLogout }) {
  return (
    <div className="ooa-admin-shell">
      <aside className="ooa-admin-sidebar">
        <div className="ooa-admin-brand">Elrace AI Admin</div>
        <nav>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `ooa-admin-nav-link${isActive ? " is-active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="ooa-admin-footer-nav">
          <Link to="/" className="ooa-admin-nav-link">
            ← Back to chat
          </Link>
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <ThemeToggle />
            <SecondaryButton onClick={onLogout}>Logout</SecondaryButton>
          </div>
          {user?.userName ? (
            <p style={{ fontSize: "0.8rem", color: "var(--ooa-text-muted)", margin: "0.5rem 0 0" }}>
              {user.userName}
            </p>
          ) : null}
        </div>
      </aside>
      <main className="ooa-admin-main" id="ooa-admin-main">
        <div className="ooa-admin-page">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
