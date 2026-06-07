import FeatureTeaserWidget from "./widgets/FeatureTeaserWidget";

const TEASERS = [
  {
    icon: "✦",
    title: "ERP Intelligence",
    description: "Ask about finance, projects, and operations in plain language — after you sign in.",
  },
  {
    icon: "🔐",
    title: "Your File ID",
    description: "Secure access with your Elrace File ID. We load your profile and permissions on login.",
  },
  {
    icon: "◊",
    title: "Odoo Live",
    description: "Connected to your live Odoo data for accurate answers and reports.",
  },
];

export default function FeatureTeaserStack() {
  return (
    <aside className="splash-right" aria-label="Product highlights">
      {TEASERS.map((item, index) => (
        <FeatureTeaserWidget
          key={item.title}
          icon={item.icon}
          title={item.title}
          description={item.description}
          delay={index * 60}
        />
      ))}
    </aside>
  );
}
