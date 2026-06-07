const GREETINGS = {
  morning: { en: "Good Morning", ar: "صباح الخير" },
  afternoon: { en: "Good Afternoon", ar: "مساء الخير" },
  evening: { en: "Good Evening", ar: "مساء الخير" },
  night: { en: "Good Evening", ar: "مساء الخير" },
};

function dubaiHour() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    hour: "numeric",
    hour12: false,
    timeZone: "Asia/Dubai",
  }).formatToParts(new Date());
  const hourPart = parts.find((part) => part.type === "hour");
  return Number(hourPart?.value ?? new Date().getHours());
}

function timeOfDay(hour) {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  if (hour >= 17 && hour < 21) return "evening";
  return "night";
}

function firstName(user) {
  const lang = user?.language === "ar" ? "ar" : "en";
  if (lang === "ar" && user?.nameArabic) {
    return String(user.nameArabic).split(/\s+/)[0];
  }
  const name = user?.userName || user?.name || "there";
  return String(name).split(/\s+/)[0];
}

export function getGreeting(user, isLoggedIn = false) {
  const lang = user?.language === "ar" ? "ar" : "en";
  const period = timeOfDay(dubaiHour());
  const greeting = GREETINGS[period][lang];
  const line2 = isLoggedIn
    ? firstName(user)
    : lang === "ar"
      ? "أهلاً وسهلاً"
      : "Welcome";
  return {
    line1: greeting,
    line2,
    period,
    lang,
  };
}
