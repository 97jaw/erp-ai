const SOUND_FILES = {
  "theme-toggle": "/sounds/theme-toggle.mp3",
  "message-send": "/sounds/message-send.mp3",
  "message-receive": "/sounds/message-receive.mp3",
  "login-success-ar": "/sounds/login-success-ar.mp3",
  "login-success-en": "/sounds/login-success-en.mp3",
  "login-fail-ar": "/sounds/login-fail-ar.mp3",
  "login-fail-en": "/sounds/login-fail-en.mp3",
  "chime-success": "/sounds/chime-success.mp3",
  "chime-error": "/sounds/chime-error.mp3",
  "typing-start": "/sounds/typing-start.mp3",
};

const SYNTH_PROFILES = {
  "theme-toggle": { frequency: 660, duration: 0.08, type: "sine", gain: 0.08 },
  "message-send": { frequency: 520, duration: 0.06, type: "triangle", gain: 0.1 },
  "message-receive": { frequency: 740, duration: 0.12, type: "sine", gain: 0.1 },
  "login-success-en": { frequency: 620, duration: 0.18, type: "sine", gain: 0.12 },
  "login-success-ar": { frequency: 580, duration: 0.2, type: "sine", gain: 0.12 },
  "login-fail-en": { frequency: 220, duration: 0.22, type: "sawtooth", gain: 0.08 },
  "login-fail-ar": { frequency: 200, duration: 0.22, type: "sawtooth", gain: 0.08 },
  "chime-success": { frequency: 880, duration: 0.16, type: "sine", gain: 0.1 },
  "chime-error": { frequency: 180, duration: 0.2, type: "square", gain: 0.06 },
  "typing-start": { frequency: 420, duration: 0.05, type: "sine", gain: 0.03 },
};

class SoundManager {
  constructor() {
    this.enabled = localStorage.getItem("ooa_sound_enabled") !== "false";
    this.volume = Number(localStorage.getItem("ooa_sound_volume") || "0.6");
    this.cache = new Map();
    this.audioContext = null;
    this.loopTimers = new Map();
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    localStorage.setItem("ooa_sound_enabled", enabled ? "true" : "false");
    if (!enabled) {
      this.stopLoop("typing-start");
    }
  }

  setVolume(volume) {
    this.volume = Math.max(0, Math.min(1, volume));
    localStorage.setItem("ooa_sound_volume", String(this.volume));
  }

  getAudioContext() {
    if (!this.audioContext) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return null;
      this.audioContext = new AudioContextClass();
    }
    if (this.audioContext.state === "suspended") {
      this.audioContext.resume().catch(() => {});
    }
    return this.audioContext;
  }

  playTone(soundKey, options = {}) {
    const profile = SYNTH_PROFILES[soundKey];
    const context = this.getAudioContext();
    if (!profile || !context) return;

    const oscillator = context.createOscillator();
    const gainNode = context.createGain();
    const volume = options.volume ?? this.volume;
    const now = context.currentTime;

    oscillator.type = profile.type;
    oscillator.frequency.setValueAtTime(profile.frequency, now);
    gainNode.gain.setValueAtTime(0.0001, now);
    gainNode.gain.exponentialRampToValueAtTime(Math.max(0.0001, profile.gain * volume), now + 0.01);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, now + profile.duration);
    oscillator.connect(gainNode);
    gainNode.connect(context.destination);
    oscillator.start(now);
    oscillator.stop(now + profile.duration + 0.02);
  }

  async play(soundKey, options = {}) {
    if (!this.enabled) return;

    const src = SOUND_FILES[soundKey];
    if (src) {
      try {
        let audio = this.cache.get(soundKey);
        if (!audio) {
          audio = new Audio(src);
          this.cache.set(soundKey, audio);
        }
        audio.volume = options.volume ?? this.volume;
        audio.loop = Boolean(options.loop);
        audio.currentTime = 0;
        await audio.play();
        return;
      } catch (error) {
        // Fall back to synthesized tones when optional assets are missing.
      }
    }

    this.playTone(soundKey, options);
  }

  startLoop(soundKey, options = {}) {
    this.stopLoop(soundKey);
    const interval = window.setInterval(() => {
      this.play(soundKey, options);
    }, options.intervalMs || 900);
    this.loopTimers.set(soundKey, interval);
  }

  stopLoop(soundKey) {
    const timer = this.loopTimers.get(soundKey);
    if (timer) {
      window.clearInterval(timer);
      this.loopTimers.delete(soundKey);
    }
    const audio = this.cache.get(soundKey);
    if (audio) {
      audio.loop = false;
      audio.pause();
      audio.currentTime = 0;
    }
  }
}

export const sound = new SoundManager();
