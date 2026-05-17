import { useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

export default function PermissionsPage() {
  const [permissions, setPermissions] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi
      .permissions()
      .then((d) => setPermissions(d.permissions || []))
      .catch((err) => setError(err.message));
  }, []);

  const byCategory = permissions.reduce((acc, p) => {
    const c = p.category || "other";
    if (!acc[c]) acc[c] = [];
    acc[c].push(p);
    return acc;
  }, {});

  return (
    <>
      <PageHeader title="Permissions" subtitle="Read-only catalog" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <GlassCard style={{ padding: "1rem" }}>
        {Object.entries(byCategory).map(([cat, perms]) => (
          <section key={cat} style={{ marginBottom: "1.25rem" }}>
            <h3 style={{ textTransform: "capitalize" }}>{cat}</h3>
            <ul className="ooa-admin-perm-list">
              {perms.map((p) => (
                <li key={p.id}>
                  <code>{p.code}</code> — {p.display_name}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </GlassCard>
    </>
  );
}
