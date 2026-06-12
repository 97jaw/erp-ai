import { useSoundSettings } from "../hooks/useSoundSettings";
import MainTopBar from "../main/topbar/MainTopBar";
import AuditPanel from "./AuditPanel";

export default function AuditPage({ user, onLogout }) {
  const {
    enabled: soundEnabled,
    volume,
    toggleEnabled: onToggleSound,
    updateVolume: onVolumeChange,
  } = useSoundSettings();

  return (
    <div className="ooa-main-shell ooa-main-shell--audit">
      <MainTopBar
        user={user}
        onLogout={onLogout}
        onClearConversation={() => {}}
        soundEnabled={soundEnabled}
        volume={volume}
        onToggleSound={onToggleSound}
        onVolumeChange={onVolumeChange}
        onOpenSearch={() => {}}
      />
      <main className="ooa-audit-page" id="ooa-audit-main">
        <AuditPanel user={user} />
      </main>
    </div>
  );
}
