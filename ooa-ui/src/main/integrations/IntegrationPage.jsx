import { useParams } from "react-router-dom";
import { useSoundSettings } from "../../hooks/useSoundSettings";
import MainTopBar from "../topbar/MainTopBar";
import UnderDevelopmentScreen from "./UnderDevelopmentScreen";

export default function IntegrationPage({ user, onLogout }) {
  const { serviceId } = useParams();
  const { enabled: soundEnabled, volume, toggleEnabled: onToggleSound, updateVolume: onVolumeChange } =
    useSoundSettings();

  return (
    <div className="ooa-main-shell ooa-main-shell--integration">
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
      <UnderDevelopmentScreen serviceId={serviceId} />
    </div>
  );
}
