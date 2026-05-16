import { useEffect, useMemo, useState } from "react";
import { useTheme } from "../../theme/ThemeProvider";
import ParticleCanvas from "./ParticleCanvas";

function useMotionPreferences() {
  const [paused, setPaused] = useState(false);
  const [compact, setCompact] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(max-width: 768px)").matches : false
  );
  const [reduceMotion, setReduceMotion] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(prefers-reduced-motion: reduce)").matches : false
  );

  useEffect(() => {
    const onVisibility = () => setPaused(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 768px)");
    const onChange = () => setCompact(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduceMotion(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return { paused, compact, reduceMotion, motionEnabled: !paused && !reduceMotion };
}

function useRareStreak(intervalRange, motionEnabled) {
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (!motionEnabled) {
      setActive(false);
      return undefined;
    }

    let timeoutId;
    const schedule = () => {
      const [minSeconds, maxSeconds] = intervalRange;
      const delay = (minSeconds + Math.random() * (maxSeconds - minSeconds)) * 1000;
      timeoutId = window.setTimeout(() => {
        setActive(true);
        window.setTimeout(() => {
          setActive(false);
          schedule();
        }, 1400);
      }, delay);
    };

    schedule();
    return () => window.clearTimeout(timeoutId);
  }, [intervalRange, motionEnabled]);

  return active;
}

function StarField({ count = 100, brightCount = 8 }) {
  const stars = useMemo(
    () =>
      Array.from({ length: count }, (_, index) => ({
        id: index,
        left: `${Math.random() * 100}%`,
        top: `${Math.random() * 100}%`,
        size: Math.random() * 2 + 1,
        delay: `${Math.random() * 4}s`,
        duration: `${1 + Math.random() * 3}s`,
      })),
    [count]
  );

  const brightStars = useMemo(
    () =>
      Array.from({ length: brightCount }, (_, index) => ({
        id: index,
        left: `${Math.random() * 100}%`,
        top: `${Math.random() * 100}%`,
        size: Math.random() * 1.5 + 2.5,
        delay: `${Math.random() * 5}s`,
      })),
    [brightCount]
  );

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
      {stars.map((star) => (
        <span
          key={star.id}
          style={{
            position: "absolute",
            left: star.left,
            top: star.top,
            width: star.size,
            height: star.size,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.8)",
            animation: `ooaTwinkle ${star.duration} ease-in-out ${star.delay} infinite`,
          }}
        />
      ))}
      {brightStars.map((star) => (
        <span
          key={`bright-${star.id}`}
          style={{
            position: "absolute",
            left: star.left,
            top: star.top,
            width: star.size,
            height: star.size,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.95)",
            boxShadow: "0 0 12px rgba(255,255,255,0.45)",
            animation: `ooaTwinkle 3s ease-in-out ${star.delay} infinite`,
          }}
        />
      ))}
    </div>
  );
}

function DustField({ count = 40 }) {
  const motes = useMemo(
    () =>
      Array.from({ length: count }, (_, index) => ({
        id: index,
        left: `${Math.random() * 100}%`,
        top: `${Math.random() * 100}%`,
        size: Math.random() * 3 + 1,
        delay: `${Math.random() * 5}s`,
        duration: `${6 + Math.random() * 6}s`,
      })),
    [count]
  );

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
      {motes.map((mote) => (
        <span
          key={mote.id}
          style={{
            position: "absolute",
            left: mote.left,
            top: mote.top,
            width: mote.size,
            height: mote.size,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.45)",
            animation: `ooaMoteRise ${mote.duration} ease-in-out ${mote.delay} infinite`,
          }}
        />
      ))}
    </div>
  );
}

function StarlightScene({ motionEnabled }) {
  const shootingStar = useRareStreak([30, 60], motionEnabled);
  const clouds = useMemo(
    () => [
      { id: 0, top: "18%", width: 220, height: 72, delay: "0s", duration: "62s" },
      { id: 1, top: "34%", width: 280, height: 84, delay: "-18s", duration: "74s" },
      { id: 2, top: "52%", width: 200, height: 64, delay: "-32s", duration: "58s" },
    ],
    []
  );

  return (
    <>
      <div
        className="ooa-bg-layer ooa-bg-layer--starlight-base"
        style={{ animation: motionEnabled ? "ooaCelestialHue 30s ease-in-out infinite" : "none" }}
      />
      <div
        className="ooa-bg-layer ooa-bg-layer--starlight-sun"
        style={{ animation: motionEnabled ? "ooaSunPulse 8s ease-in-out infinite" : "none" }}
      />
      {clouds.map((cloud) => (
        <div
          key={cloud.id}
          className="ooa-bg-layer ooa-bg-layer--cloud"
          style={{
            top: cloud.top,
            width: cloud.width,
            height: cloud.height,
            animation: motionEnabled ? `ooaCloudDrift ${cloud.duration} linear ${cloud.delay} infinite` : "none",
          }}
        />
      ))}
      <DustField count={motionEnabled ? 28 : 12} />
      {shootingStar ? <div className="ooa-bg-layer ooa-bg-layer--shooting-star" /> : null}
    </>
  );
}

function BlackbatScene({ motionEnabled, starCount, brightCount }) {
  const comet = useRareStreak([45, 90], motionEnabled);

  return (
    <>
      <div className="ooa-bg-layer ooa-bg-layer--blackbat-base" />
      <div
        className="ooa-bg-layer ooa-bg-layer--aurora"
        style={{ animation: motionEnabled ? "ooaAuroraShift 50s linear infinite" : "none" }}
      />
      <div
        className="ooa-bg-layer ooa-bg-layer--nebula ooa-bg-layer--nebula-a"
        style={{ animation: motionEnabled ? "ooaNebulaPulse 12s ease-in-out infinite" : "none" }}
      />
      <div
        className="ooa-bg-layer ooa-bg-layer--nebula ooa-bg-layer--nebula-b"
        style={{ animation: motionEnabled ? "ooaNebulaPulse 16s ease-in-out infinite reverse" : "none" }}
      />
      <div
        className="ooa-bg-layer ooa-bg-layer--planet ooa-bg-layer--planet-a"
        style={{ animation: motionEnabled ? "ooaOrbFloat 28s ease-in-out infinite" : "none" }}
      />
      <div
        className="ooa-bg-layer ooa-bg-layer--planet ooa-bg-layer--planet-b"
        style={{ animation: motionEnabled ? "ooaOrbFloat 34s ease-in-out infinite reverse" : "none" }}
      />
      <StarField count={starCount} brightCount={brightCount} />
      {comet ? <div className="ooa-bg-layer ooa-bg-layer--comet" /> : null}
    </>
  );
}

export default function AnimatedBackground() {
  const { themeName } = useTheme();
  const { compact, motionEnabled } = useMotionPreferences();
  const [pointer, setPointer] = useState(null);
  const starCount = compact ? 50 : 200;
  const brightCount = compact ? 4 : 8;

  useEffect(() => {
    if (!motionEnabled) {
      setPointer(null);
      return undefined;
    }

    const onMove = (event) => {
      setPointer({
        x: event.clientX / window.innerWidth,
        y: event.clientY / window.innerHeight,
      });
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [motionEnabled]);

  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
        zIndex: 0,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: "-20%",
          background:
            "radial-gradient(circle at 20% 20%, var(--ooa-orb-a), transparent 45%), radial-gradient(circle at 80% 30%, var(--ooa-orb-b), transparent 40%), radial-gradient(circle at 50% 80%, var(--ooa-orb-c), transparent 45%)",
          animation: motionEnabled ? "ooaMeshFlow 30s linear infinite" : "none",
        }}
      />
      {themeName === "blackbat" ? (
        <BlackbatScene motionEnabled={motionEnabled} starCount={starCount} brightCount={brightCount} />
      ) : (
        <StarlightScene motionEnabled={motionEnabled} />
      )}
      <ParticleCanvas motionEnabled={motionEnabled} themeName={themeName} pointer={pointer} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "radial-gradient(circle at center, transparent 40%, rgba(0,0,0,0.18) 100%)",
        }}
      />
    </div>
  );
}
