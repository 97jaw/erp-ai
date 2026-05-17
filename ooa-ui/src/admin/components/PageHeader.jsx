import { Link } from "react-router-dom";
import GlassButton from "../../components/glass/GlassButton";

export default function PageHeader({ title, subtitle, actions, backTo }) {
  return (
    <header className="ooa-admin-header">
      <div>
        {backTo ? (
          <Link to={backTo} className="ooa-admin-nav-link" style={{ display: "inline-block", marginBottom: "0.35rem" }}>
            ← Back
          </Link>
        ) : null}
        <h1>{title}</h1>
        {subtitle ? (
          <p style={{ margin: "0.25rem 0 0", color: "var(--ooa-text-muted)", fontSize: "0.9rem" }}>{subtitle}</p>
        ) : null}
      </div>
      {actions ? <div className="ooa-admin-actions">{actions}</div> : null}
    </header>
  );
}

export function PrimaryButton({ children, onClick, type = "button", disabled }) {
  return (
    <GlassButton className="ooa-glass-button ooa-glass-button--primary" type={type} onClick={onClick} disabled={disabled}>
      {children}
    </GlassButton>
  );
}

export function SecondaryButton({ children, onClick, type = "button", disabled }) {
  return (
    <GlassButton className="ooa-glass-button" type={type} onClick={onClick} disabled={disabled}>
      {children}
    </GlassButton>
  );
}
