function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "U";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

export default function ProfileBlock({ user, className = "" }) {
  const displayName = user?.userName || "User";
  const role = user?.roles?.[0] || user?.fileId || "Member";

  return (
    <div className={`splash-profile${className ? ` ${className}` : ""}`} aria-label={displayName}>
      <span className="splash-profile__avatar" aria-hidden="true">
        {initials(displayName)}
      </span>
      <span className="splash-profile__meta">
        <span className="splash-profile__name">{displayName}</span>
        <span className="splash-profile__role">{role}</span>
      </span>
    </div>
  );
}
