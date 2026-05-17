import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

export default function RolesList() {
  const [roles, setRoles] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi
      .roles()
      .then((d) => setRoles(d.roles || []))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <>
      <PageHeader title="Roles" subtitle="System and custom roles" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <GlassCard className="ooa-admin-table-wrap">
        <table className="ooa-admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Display</th>
              <th>Level</th>
              <th>System</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td>{r.display_name}</td>
                <td>{r.level}</td>
                <td>{r.is_system ? "Yes" : "No"}</td>
                <td>
                  <Link to={`/admin/roles/${r.id}`}>Permissions</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </>
  );
}
