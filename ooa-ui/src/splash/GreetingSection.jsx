import { getGreeting } from "./getGreeting";

export default function GreetingSection({ user, isLoggedIn, revealName, awaitingReveal = false }) {
  const greeting = getGreeting(user, isLoggedIn);
  const question =
    greeting.lang === "ar"
      ? "ماذا تريد أن تعرف اليوم؟"
      : "What would you like to know today?";

  return (
    <header className="splash-greeting-block">
      <h1 className="splash-greeting" lang={greeting.lang}>
        <span className="splash-greeting__line">{greeting.line1}</span>
        {isLoggedIn ? (
          <span
            className={`splash-greeting__name${
              revealName
                ? " splash-greeting__name--reveal"
                : awaitingReveal
                  ? " splash-greeting__name--await"
                  : ""
            }`}
          >
            {greeting.line2}
          </span>
        ) : (
          <span className="splash-greeting__name">{greeting.line2}</span>
        )}
      </h1>
      <p className="splash-greeting__question" dir={greeting.lang === "ar" ? "rtl" : "ltr"}>
        {question}
      </p>
    </header>
  );
}
