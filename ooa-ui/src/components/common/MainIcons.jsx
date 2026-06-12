const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function IconProfile({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="3.5" {...stroke} />
      <path d="M5 20c0-3.5 3.1-6 7-6s7 2.5 7 6" {...stroke} />
    </svg>
  );
}

export function IconSearch({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6" {...stroke} />
      <path d="M16 16l5 5" {...stroke} />
    </svg>
  );
}

export function IconNewChat({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" {...stroke} />
    </svg>
  );
}

export function IconChats({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6h16v10H8l-4 4V6z" {...stroke} />
    </svg>
  );
}

export function IconClock({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8" {...stroke} />
      <path d="M12 8v5l3 2" {...stroke} />
    </svg>
  );
}

export function IconAudit({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3l8 4v5c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V7l8-4z" {...stroke} />
      <circle cx="12" cy="11" r="2.5" {...stroke} />
      <path d="M12 13.5V16" {...stroke} />
    </svg>
  );
}

export function IconBell({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 10a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6" {...stroke} />
      <path d="M10 20a2 2 0 0 0 4 0" {...stroke} />
    </svg>
  );
}

export function IconSun({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4" {...stroke} />
      <path
        d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
        {...stroke}
      />
    </svg>
  );
}

export function IconSettings({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3" {...stroke} />
      <path
        d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4l1.4-1.4M17 7l1.4-1.4"
        {...stroke}
      />
    </svg>
  );
}

export function IconLogout({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10 6H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4" {...stroke} />
      <path d="M14 12H8M18 8l4 4-4 4" {...stroke} />
    </svg>
  );
}

export function IconMic({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" {...stroke} />
      <path d="M6 11a6 6 0 0 0 12 0M12 17v4" {...stroke} />
    </svg>
  );
}

export function IconSend({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h12M13 7l5 5-5 5" {...stroke} />
    </svg>
  );
}

export function IconDeepThink({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3a6.5 6.5 0 0 1 6.5 6.5c0 2.4-1.3 4.1-2.6 5.4-.6.6-.9 1.4-.9 2.1v1h-6v-1c0-.7-.3-1.5-.9-2.1C6.8 13.6 5.5 11.9 5.5 9.5A6.5 6.5 0 0 1 12 3Z" {...stroke} />
      <path d="M10 21h4M12 7.5v3M10.5 9h3" {...stroke} />
    </svg>
  );
}

export function IconChart({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 18V8M12 18V4M19 18v-6" {...stroke} />
    </svg>
  );
}

export function IconProjects({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 20V9l8-5 8 5v11H4z" {...stroke} />
      <path d="M9 20v-6h6v6" {...stroke} />
    </svg>
  );
}

export function IconCash({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="7" width="18" height="10" rx="2" {...stroke} />
      <circle cx="12" cy="12" r="2.5" {...stroke} />
    </svg>
  );
}

export function IconTrend({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 18h16M7 14l4-4 3 3 5-7" {...stroke} />
    </svg>
  );
}

export function IconClipboard({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="7" y="5" width="10" height="14" rx="2" {...stroke} />
      <path d="M9 5V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1" {...stroke} />
    </svg>
  );
}

/** Six-dot grip — drag handle for Visualize panel only (not whole message). */
export function IconGrip({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="7" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="15" cy="7" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="9" cy="12" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="15" cy="12" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="9" cy="17" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="15" cy="17" r="1.35" fill="currentColor" stroke="none" />
    </svg>
  );
}

const QUICK_ACTION_ICONS = {
  chart: IconChart,
  projects: IconProjects,
  cash: IconCash,
  trend: IconTrend,
  mic: IconMic,
  clipboard: IconClipboard,
  search: IconSearch,
  chats: IconChats,
  clock: IconClock,
  audit: IconAudit,
};

export function QuickActionIcon({ name, size = 20 }) {
  const Icon = QUICK_ACTION_ICONS[name] || IconDiamond;
  return <Icon size={size} />;
}

export function IconDiamond({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3l7 7-7 11L5 10l7-7z" {...stroke} />
    </svg>
  );
}

const INTEGRATION_ICONS = {
  onedrive: (
    <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 14a5 5 0 0 1 9.8-1.2A4 4 0 0 1 20 16H7a3 3 0 0 1-1-2z" {...stroke} />
    </svg>
  ),
  sharepoint: (
    <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h11v10H4zM15 9h5v6h-5z" {...stroke} />
    </svg>
  ),
  owncloud: (
    <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 8h14v10H5zM8 8V6h8v2" {...stroke} />
    </svg>
  ),
  slack: (
    <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 14H6a2 2 0 0 1 0-4h2v4zM10 8V6a2 2 0 0 1 4 0v2h-4zM16 10h4a2 2 0 0 1 0 4h-4v-4zM14 16v2a2 2 0 0 1-4 0v-2h4z" {...stroke} />
    </svg>
  ),
  email: (
    <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="6" width="16" height="12" rx="2" {...stroke} />
      <path d="M4 8l8 5 8-5" {...stroke} />
    </svg>
  ),
  whatsapp: (
    <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 18l-2 3 3-2a8 8 0 1 0-1-1z" {...stroke} />
    </svg>
  ),
  google: (
    <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8" {...stroke} />
      <path d="M12 8v8M8 12h8" {...stroke} />
    </svg>
  ),
};

export function IconIntegration({ id, size = 20 }) {
  const icon = INTEGRATION_ICONS[id];
  if (!icon) return <IconDiamond size={size} />;
  return icon;
}
