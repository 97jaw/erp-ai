import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GlassCard from "../../components/glass/GlassCard";
import GlassInput from "../../components/glass/GlassInput";
import PageHeader, { PrimaryButton } from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { adminApi } from "../api";

export default function UsersList() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async (q = search) => {
    setLoading(true);
    setError("");
    try {
      const data = await adminApi.users({ search: q || undefined, limit: 100 });
      setUsers(data.users || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <>
      <PageHeader
        title="Users"
        subtitle={`${users.length} users`}
        actions={
          <Link to="/admin/users/new">
            <PrimaryButton type="button">+ Add user</PrimaryButton>
          </Link>
        }
      />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <div className="ooa-admin-toolbar">
        <GlassInput
          className="ooa-glass-input"
          placeholder="Search name, file ID, email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
          style={{ minWidth: 260 }}
        />
        <PrimaryButton type="button" onClick={() => load()}>
          Search
        </PrimaryButton>
      </div>
      <GlassCard className="ooa-admin-table-wrap">
        <table className="ooa-admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>File ID</th>
              <th>Status</th>
              <th>Last login</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5}>Loading…</td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={5}>No users found.</td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id}>
                  <td>{u.name}</td>
                  <td>{u.file_id}</td>
                  <td>
                    <StatusBadge active={u.is_active} />
                    {u.is_super_admin ? " · Super" : ""}
                  </td>
                  <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}</td>
                  <td>
                    <Link to={`/admin/users/${u.id}`}>Edit</Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </GlassCard>
    </>
  );
}
