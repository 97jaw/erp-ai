import { useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

export default function FeatureFlagsPage() {
  const [flags, setFlags] = useState([]);
  const [error, setError] = useState("");

  const load = () =>
    adminApi
      .featureFlags()
      .then((d) => setFlags(d.feature_flags || []))
      .catch((err) => setError(err.message));

  useEffect(() => {
    load();
  }, []);

  const toggle = async (flag) => {
    try {
      await adminApi.updateFeatureFlag(flag.id, { is_enabled: !flag.is_enabled });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <PageHeader title="Feature flags" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <GlassCard className="ooa-admin-table-wrap">
        <table className="ooa-admin-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Rollout %</th>
              <th>Enabled</th>
            </tr>
          </thead>
          <tbody>
            {flags.map((f) => (
              <tr key={f.id}>
                <td>{f.code}</td>
                <td>{f.name}</td>
                <td>{f.rollout_percent}</td>
                <td>
                  <input type="checkbox" checked={f.is_enabled} onChange={() => toggle(f)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </>
  );
}
