import { useEffect, useState } from "react";

export function getViewportTier(width = typeof window !== "undefined" ? window.innerWidth : 1280) {
  if (width <= 768) return "mobile";
  if (width <= 1200) return "tablet";
  return "desktop";
}

/** mobile ≤768 | tablet 769–1200 | desktop >1200 */
export default function useViewportTier() {
  const [tier, setTier] = useState(() => getViewportTier());

  useEffect(() => {
    const onResize = () => setTier(getViewportTier());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return tier;
}
