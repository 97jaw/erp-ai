import SkipButton from "./SkipButton";

export default function SplashFooter({
  isLoggedIn,
  revealActive,
  awaitingReveal = false,
  skipLabel,
  onGetStarted,
}) {
  return (
    <footer className="splash-footer">
      <p className="splash-footer__brand">
        <strong>◊</strong> Odoo Omni-Agent · Elrace
      </p>
      {isLoggedIn ? (
        <SkipButton
          label={skipLabel}
          onClick={onGetStarted}
          className={
            revealActive
              ? "splash-pop-in splash-pop-in--delay-8"
              : awaitingReveal
                ? "splash-await-reveal"
                : ""
          }
        />
      ) : (
        <span className="splash-footer__help">Need help? Contact Admin</span>
      )}
    </footer>
  );
}
