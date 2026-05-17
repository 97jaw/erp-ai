export default function StatusBadge({ active, locked }) {
  if (locked) return <span className="ooa-admin-badge ooa-admin-badge--warn">Locked</span>;
  if (active) return <span className="ooa-admin-badge ooa-admin-badge--ok">Active</span>;
  return <span className="ooa-admin-badge ooa-admin-badge--bad">Inactive</span>;
}
