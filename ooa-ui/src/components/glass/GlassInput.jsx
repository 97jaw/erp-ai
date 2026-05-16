export default function GlassInput({ className = "", recording = false, ...props }) {
  const classes = ["ooa-glass-input", recording ? "ooa-glass-input--recording" : "", className]
    .filter(Boolean)
    .join(" ");

  return <input className={classes} {...props} />;
}
