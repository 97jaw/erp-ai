import LoginWidget from "./widgets/LoginWidget";
import OutlookWidget from "./widgets/OutlookWidget";
import ConnectLaterWidget from "./widgets/ConnectLaterWidget";

export default function AuthWidgetSlot({
  isLoggedIn,
  outlookSkipped,
  userEmail,
  loginSlotRef,
  onLoginSubmit,
  onOutlookConnect,
  onOutlookLearnMore,
  onOutlookSkip,
  onOutlookReconnect,
}) {
  return (
    <div className="splash-auth-slot">
      <div
        className={`splash-auth-slot__pane${isLoggedIn ? " splash-auth-slot__pane--out" : " splash-auth-slot__pane--in"}`}
        aria-hidden={isLoggedIn}
      >
        <LoginWidget onSubmit={onLoginSubmit} inputRef={loginSlotRef} />
      </div>

      {isLoggedIn ? (
        <div className="splash-auth-slot__pane splash-auth-slot__pane--in">
          {outlookSkipped ? (
            <ConnectLaterWidget onReconnect={onOutlookReconnect} />
          ) : (
            <OutlookWidget
              defaultEmail={userEmail}
              onConnect={onOutlookConnect}
              onLearnMore={onOutlookLearnMore}
              onSkip={onOutlookSkip}
            />
          )}
        </div>
      ) : null}
    </div>
  );
}
