import { capabilityHintForToday } from "./quickActions";

export default function CapabilityHint() {
  return (
    <p className="splash-hint" aria-live="polite">
      {capabilityHintForToday()}
    </p>
  );
}
