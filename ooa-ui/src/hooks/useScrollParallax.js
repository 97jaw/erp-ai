import { useEffect, useState } from "react";

export default function useScrollParallax(containerRef) {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const onScroll = () => {
      setOffset(container.scrollTop);
    };

    onScroll();
    container.addEventListener("scroll", onScroll, { passive: true });
    return () => container.removeEventListener("scroll", onScroll);
  }, [containerRef]);

  return offset;
}
