import { useEffect, useState } from "react";
import { sound } from "../components/common/SoundManager";

export function useSoundSettings() {
  const [enabled, setEnabled] = useState(() => localStorage.getItem("ooa_sound_enabled") !== "false");
  const [volume, setVolume] = useState(() => Number(localStorage.getItem("ooa_sound_volume") || "0.6"));

  useEffect(() => {
    sound.setEnabled(enabled);
  }, [enabled]);

  useEffect(() => {
    sound.setVolume(volume);
  }, [volume]);

  const toggleEnabled = () => {
    setEnabled((current) => {
      const next = !current;
      localStorage.setItem("ooa_sound_enabled", next ? "true" : "false");
      return next;
    });
  };

  const updateVolume = (nextVolume) => {
    const clamped = Math.max(0, Math.min(1, nextVolume));
    setVolume(clamped);
    localStorage.setItem("ooa_sound_volume", String(clamped));
  };

  return { enabled, volume, toggleEnabled, updateVolume };
}
