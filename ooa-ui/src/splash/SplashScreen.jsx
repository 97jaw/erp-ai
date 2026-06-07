import { useCallback, useEffect, useRef, useState } from "react";
import ComingSoonModal from "./ComingSoonModal";
import FeatureTeaserStack from "./FeatureTeaserStack";
import GreetingSection from "./GreetingSection";
import HeroBackground from "./HeroBackground";
import LoginInline from "./LoginInline";
import OutlookConnectModal from "./OutlookConnectModal";
import QuickActionPills from "./QuickActionPills";
import SplashFooter from "./SplashFooter";
import SplashHeader from "./SplashHeader";
import TrustIndicators from "./TrustIndicators";
import WidgetStack from "./WidgetStack";
import { resolveSplashTheme, splashThemeClass } from "./themes/splashThemes";
import { normalizeAuthFromLogin } from "../config/api";
import {
  getSplashThemePreference,
  isFirstSplashVisit,
  markSplashVisited,
  shouldAutoSkipSplash,
  stashSplashQuery,
} from "./splashStorage";

const OUTLOOK_INFO = {
  connect: {
    title: "Coming Soon",
    body:
      "Microsoft OAuth sign-in will arrive in a future release. Your credentials are not sent anywhere today — this button only previews the integration experience.",
  },
  learn: {
    title: "Outlook Integration",
    body:
      "We will use secure Microsoft OAuth (not stored passwords) to read email metadata and summaries for AI insights. MFA-friendly and enterprise compliant.",
  },
};

function buildAuthPayload(body, fileId) {
  return normalizeAuthFromLogin(body, fileId);
}

export default function SplashScreen({
  user: initialUser = null,
  onAuthenticated,
  onSkipToChat,
  onOpenVoice,
}) {
  const [user, setUser] = useState(initialUser);
  const [loginState, setLoginState] = useState(initialUser ? "logged_in" : "logged_out");
  const [splashThemePref, setSplashThemePref] = useState(getSplashThemePreference);
  const [autoSkip, setAutoSkip] = useState(shouldAutoSkipSplash);
  const [infoModal, setInfoModal] = useState(null);
  const [outlookOpen, setOutlookOpen] = useState(false);
  const [revealActive, setRevealActive] = useState(false);
  const loginFormRef = useRef(null);
  const hadUserOnMount = useRef(Boolean(initialUser));
  const pendingLoginReveal = useRef(false);

  const isLoggedIn = loginState === "logged_in" && Boolean(user);
  const shouldAnimateLogin = isLoggedIn && !hadUserOnMount.current;
  const awaitingReveal = isLoggedIn && shouldAnimateLogin && !revealActive;
  const revealHeader = shouldAnimateLogin && revealActive;
  const revealWidgets = revealHeader;
  const revealName = revealHeader;

  const resolvedTheme = resolveSplashTheme(splashThemePref);
  const firstVisit = isFirstSplashVisit();
  const skipLabel = firstVisit ? "Get Started →" : "Skip → Open Chat";

  useEffect(() => {
    if (initialUser) {
      setUser(initialUser);
      setLoginState("logged_in");
      if (hadUserOnMount.current) {
        setRevealActive(true);
      }
      return;
    }
    if (!pendingLoginReveal.current) {
      setUser(null);
      setLoginState("logged_out");
      setRevealActive(false);
    }
  }, [initialUser]);

  useEffect(() => {
    if (splashThemePref !== "auto") return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => setSplashThemePref("auto");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [splashThemePref]);

  const scheduleLoginReveal = useCallback(() => {
    if (hadUserOnMount.current) {
      setRevealActive(true);
      return;
    }
    pendingLoginReveal.current = true;
    setRevealActive(false);
    window.setTimeout(() => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setRevealActive(true);
          pendingLoginReveal.current = false;
        });
      });
    }, 120);
  }, []);

  useEffect(() => {
    if (!isLoggedIn || !shouldAnimateLogin || revealActive) return undefined;
    const fallbackId = window.setTimeout(() => setRevealActive(true), 600);
    return () => window.clearTimeout(fallbackId);
  }, [isLoggedIn, shouldAnimateLogin, revealActive]);

  const enterChat = useCallback(
    (action, query) => {
      if (query) stashSplashQuery(query);
      markSplashVisited(action);
      setOutlookOpen(false);
      onSkipToChat?.({ action, query });
    },
    [onSkipToChat],
  );

  const handleGetStarted = useCallback(() => {
    if (!isLoggedIn) {
      loginFormRef.current?.querySelector?.("#splash-file-id")?.focus();
      return;
    }
    setOutlookOpen(true);
  }, [isLoggedIn]);

  const handleLoginSubmit = useCallback(
    async (body, fileId) => {
      const authPayload = buildAuthPayload(body, fileId);
      setUser(authPayload);
      setLoginState("logged_in");
      onAuthenticated?.(authPayload);
      scheduleLoginReveal();
    },
    [onAuthenticated, scheduleLoginReveal],
  );

  const handlePillClick = useCallback(
    (query, pill) => {
      if (!isLoggedIn) {
        loginFormRef.current?.querySelector?.("#splash-file-id")?.focus();
        return;
      }
      enterChat("pill_clicked", query);
      if (pill?.action === "voice") onOpenVoice?.();
    },
    [enterChat, isLoggedIn, onOpenVoice],
  );

  const handleVoiceClick = useCallback(() => {
    if (!isLoggedIn) {
      loginFormRef.current?.querySelector?.("#splash-file-id")?.focus();
      return;
    }
    onOpenVoice?.();
    enterChat("voice", "");
  }, [enterChat, isLoggedIn, onOpenVoice]);

  const insight = {
    trend: "Revenue ↗ +12%",
    direction: "up",
    value: "AED 17.4M",
    description: "Best month in Q1",
  };

  const pending = { count: 3, subtitle: "Invoices waiting review" };

  const themeClass = `splash-screen ${splashThemeClass(splashThemePref)}`;

  return (
    <div className={themeClass} data-splash-theme={resolvedTheme}>
      <HeroBackground variant={resolvedTheme} />

      <SplashHeader
        user={user}
        isLoggedIn={isLoggedIn}
        revealHeader={revealHeader}
        awaitingReveal={awaitingReveal}
        splashTheme={splashThemePref}
        autoSkip={autoSkip}
        onThemeChange={setSplashThemePref}
        onAutoSkipChange={setAutoSkip}
      />

      <main className="splash-body" id="ooa-splash-main">
        <section className="splash-left" aria-label="Welcome">
          <GreetingSection
            user={user}
            isLoggedIn={isLoggedIn}
            revealName={revealName}
            awaitingReveal={awaitingReveal}
          />

          {!isLoggedIn ? <LoginInline formRef={loginFormRef} onSubmit={handleLoginSubmit} /> : null}

          <QuickActionPills
            isLoggedIn={isLoggedIn}
            className={
              revealWidgets
                ? "splash-pop-in splash-pop-in--delay-6"
                : awaitingReveal
                  ? "splash-await-reveal"
                  : ""
            }
            onPillClick={handlePillClick}
            onVoiceClick={handleVoiceClick}
          />
          <TrustIndicators
            isLoggedIn={isLoggedIn}
            reveal={revealWidgets}
            awaitingReveal={awaitingReveal}
          />
        </section>

        {isLoggedIn ? (
          <WidgetStack
            insight={insight}
            pending={pending}
            revealWidgets={revealWidgets}
            awaitingReveal={awaitingReveal}
            onInsightExplore={() => enterChat("widget_insight", "Tell me about today's revenue")}
            onPendingReview={() => enterChat("widget_pending", "Show pending approvals")}
          />
        ) : (
          <FeatureTeaserStack />
        )}
      </main>

      <SplashFooter
        isLoggedIn={isLoggedIn}
        revealActive={revealHeader}
        awaitingReveal={awaitingReveal}
        skipLabel={skipLabel}
        onGetStarted={handleGetStarted}
      />

      <OutlookConnectModal
        open={outlookOpen}
        userEmail={user?.email || ""}
        onConnect={() => setInfoModal("connect")}
        onLearnMore={() => setInfoModal("learn")}
        onSkipToChat={() => enterChat("skipped_outlook")}
        onClose={() => setOutlookOpen(false)}
      />

      <ComingSoonModal
        open={Boolean(infoModal)}
        title={OUTLOOK_INFO[infoModal]?.title || "Coming Soon"}
        body={OUTLOOK_INFO[infoModal]?.body || ""}
        onClose={() => setInfoModal(null)}
      />
    </div>
  );
}
