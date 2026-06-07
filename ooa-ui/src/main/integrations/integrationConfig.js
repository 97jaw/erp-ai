export const INTEGRATIONS = [
  {
    id: "onedrive",
    icon: "☁",
    name: "OneDrive",
    path: "/integrations/onedrive",
    status: "disconnected",
  },
  {
    id: "sharepoint",
    icon: "📁",
    name: "SharePoint",
    path: "/integrations/sharepoint",
    status: "disconnected",
  },
  {
    id: "owncloud",
    icon: "📦",
    name: "ownCloud",
    path: "/integrations/owncloud",
    status: "disconnected",
  },
  {
    id: "slack",
    icon: "💬",
    name: "Slack",
    path: "/integrations/slack",
    status: "disconnected",
  },
  {
    id: "email",
    icon: "📧",
    name: "Email (Outlook)",
    path: "/integrations/email",
    status: "disconnected",
  },
  {
    id: "whatsapp",
    icon: "📱",
    name: "WhatsApp Business",
    path: "/integrations/whatsapp",
    status: "disconnected",
  },
  {
    id: "google",
    icon: "🔵",
    name: "Google Apps",
    path: "/integrations/google",
    status: "disconnected",
  },
];

export function getIntegration(id) {
  return INTEGRATIONS.find((item) => item.id === id) || null;
}
