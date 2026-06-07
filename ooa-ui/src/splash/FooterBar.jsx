import SkipButton from "./SkipButton";

export default function FooterBar({ skipLabel, onSkip }) {
  return (
    <footer className="splash-footer">
      <p className="splash-footer__brand">
        <strong>◊</strong> Odoo Omni-Agent · Elrace
      </p>
      <SkipButton label={skipLabel} onClick={onSkip} />
    </footer>
  );
}
