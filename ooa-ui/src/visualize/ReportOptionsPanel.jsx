import CollapsibleSection from "./cards/CollapsibleSection";
import LayoutPicker from "./LayoutPicker";
import PdfOptions from "./PdfOptions";
import ThemePicker from "./ThemePicker";

function themeLabel(themes, value) {
  return themes.find((t) => t.id === value)?.name || value;
}

function layoutLabel(layouts, value) {
  return layouts.find((l) => l.id === value)?.name || value;
}

function pdfSummary({ includeLogo, pageNumbers, watermark }) {
  const parts = [];
  if (includeLogo) parts.push("Logo");
  if (pageNumbers) parts.push("Pages");
  if (watermark && watermark !== "none") parts.push(watermark);
  return parts.length ? parts.join(" · ") : "Defaults";
}

export default function ReportOptionsPanel({
  themes,
  layouts,
  selectedTheme,
  selectedLayout,
  includeLogo,
  pageNumbers,
  watermark,
  onThemeChange,
  onLayoutChange,
  onIncludeLogoChange,
  onPageNumbersChange,
  onWatermarkChange,
  disabled,
}) {
  if (!themes?.length) return null;

  return (
    <div className="ooa-viz-options">
      <CollapsibleSection
        icon="🎨"
        title="Theme"
        subtitle={themeLabel(themes, selectedTheme)}
        defaultOpen={false}
      >
        <ThemePicker
          themes={themes}
          value={selectedTheme}
          onChange={onThemeChange}
          disabled={disabled}
          embedded
        />
      </CollapsibleSection>

      <CollapsibleSection
        icon="📐"
        title="Layout"
        subtitle={layoutLabel(layouts, selectedLayout)}
        defaultOpen={false}
      >
        <LayoutPicker
          layouts={layouts}
          value={selectedLayout}
          onChange={onLayoutChange}
          disabled={disabled}
          embedded
        />
      </CollapsibleSection>

      <CollapsibleSection
        icon="📄"
        title="PDF options"
        subtitle={pdfSummary({ includeLogo, pageNumbers, watermark })}
        defaultOpen={false}
      >
        <PdfOptions
          includeLogo={includeLogo}
          pageNumbers={pageNumbers}
          watermark={watermark}
          onIncludeLogoChange={onIncludeLogoChange}
          onPageNumbersChange={onPageNumbersChange}
          onWatermarkChange={onWatermarkChange}
          disabled={disabled}
          embedded
        />
      </CollapsibleSection>
    </div>
  );
}
