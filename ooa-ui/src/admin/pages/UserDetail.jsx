import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import GlassCard from "../../components/glass/GlassCard";
import GlassInput from "../../components/glass/GlassInput";
import PageHeader, { PrimaryButton, SecondaryButton } from "../components/PageHeader";
import { adminApi } from "../api";

export default function UserDetail() {
  const { id } = useParams();
  const [user, setUser] = useState(null);
  const [roles, setRoles] = useState([]);
  const [allRoles, setAllRoles] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [audit, setAudit] = useState([]);
  const [form, setForm] = useState({ name: "", email: "", language: "en", is_active: true });
  const [error, setError] = useState("");
  const [tab, setTab] = useState("profile");

  const load = useCallback(async () => {
    setError("");
    try {
      const [u, roleList, sess, aud] = await Promise.all([
        adminApi.user(id),
        adminApi.roles(),
        adminApi.userSessions(id),
        adminApi.userAudit(id, { limit: 20 }),
      ]);
      setUser(u);
      setRoles(u.roles || []);
      setAllRoles(roleList.roles || []);
      setSessions(sess.sessions || []);
      setAudit(aud.events || []);
      setForm({
        name: u.name || "",
        email: u.email || "",
        language: u.language || "en",
        is_active: u.is_active !== false,
      });
    } catch (err) {
      setError(err.message);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    try {
      await adminApi.updateUser(id, form);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleRole = async (role, assigned) => {
    try {
      if (assigned) await adminApi.removeRole(id, role.id);
      else await adminApi.assignRole(id, role.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!user && !error) return <p>Loading…</p>;

  return (
    <>
      <PageHeader
        title={user?.name || "User"}
        subtitle={user?.file_id}
        backTo="/admin/users"
        actions={
          <>
            <PrimaryButton type="button" onClick={save}>
              Save
            </PrimaryButton>
            <SecondaryButton type="button" onClick={() => adminApi.unlockUser(id).then(load)}>
              Unlock
            </SecondaryButton>
          </>
        }
      />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <div className="ooa-admin-toolbar">
        {["profile", "roles", "sessions", "audit"].map((t) => (
          <button
            key={t}
            type="button"
            className={`ooa-glass-button${tab === t ? " ooa-glass-button--primary" : ""}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "profile" && (
        <GlassCard style={{ padding: "1.25rem" }}>
          <div className="ooa-admin-form-grid">
            <div className="ooa-admin-field">
              <label>Name</label>
              <GlassInput className="ooa-glass-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="ooa-admin-field">
              <label>Email</label>
              <GlassInput className="ooa-glass-input" value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="ooa-admin-field">
              <label>
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active
              </label>
            </div>
          </div>
          <h3 style={{ marginTop: "1rem" }}>Effective permissions</h3>
          <ul className="ooa-admin-perm-list">
            {(user?.permissions || []).map((p) => (
              <li key={p}>✓ {p}</li>
            ))}
          </ul>
        </GlassCard>
      )}
      {tab === "roles" && (
        <GlassCard style={{ padding: "1rem" }}>
          {allRoles.map((r) => {
            const assigned = roles.includes(r.name);
            return (
              <label key={r.id} style={{ display: "block", marginBottom: "0.5rem" }}>
                <input type="checkbox" checked={assigned} onChange={() => toggleRole(r, assigned)} /> {r.display_name} ({r.name})
              </label>
            );
          })}
        </GlassCard>
      )}
      {tab === "sessions" && (
        <GlassCard className="ooa-admin-table-wrap">
          <table className="ooa-admin-table">
            <thead>
              <tr>
                <th>Started</th>
                <th>Expires</th>
                <th>IP</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>{s.started_at ? new Date(s.started_at).toLocaleString() : "—"}</td>
                  <td>{s.expires_at ? new Date(s.expires_at).toLocaleString() : "—"}</td>
                  <td>{s.ip_address || "—"}</td>
                  <td>{s.revoked_at ? "Revoked" : "Active"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <SecondaryButton type="button" onClick={() => adminApi.revokeUserSessions(id).then(load)} style={{ marginTop: "0.75rem" }}>
            Revoke all sessions
          </SecondaryButton>
        </GlassCard>
      )}
      {tab === "audit" && (
        <GlassCard className="ooa-admin-table-wrap">
          <table className="ooa-admin-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((e) => (
                <tr key={e.id}>
                  <td>{e.created_at ? new Date(e.created_at).toLocaleString() : "—"}</td>
                  <td>{e.event_action}</td>
                  <td>{e.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      )}
    </>
  );
}
