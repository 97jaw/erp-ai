export function normalizeOutputFormat(value) {
  const fmt = String(value || "pdf").toLowerCase();
  if (fmt === "xlsx" || fmt === "excel" || fmt === "spreadsheet") return "excel";
  if (fmt === "pdf") return "pdf";
  return fmt;
}

export function formatOutputLabel(format) {
  const fmt = normalizeOutputFormat(format);
  if (fmt === "excel") return "XLSX";
  return "PDF";
}

export function formatRecommendationDraft(
  recommendation,
  {
    selectedFormat,
    selectedTheme,
    selectedLayout,
    themes = [],
    layouts = [],
    includeLogo = true,
    pageNumbers = true,
    watermark = "none",
  } = {},
) {
  if (!recommendation) return "";

  const fmt = normalizeOutputFormat(selectedFormat || recommendation.format);
  const themeName =
    themes.find((t) => t.id === (selectedTheme || recommendation.theme))?.name
    || recommendation.theme_display
    || recommendation.theme
    || selectedTheme;
  const layoutName =
    layouts.find((l) => l.id === (selectedLayout || recommendation.layout))?.name
    || recommendation.layout_display
    || recommendation.layout
    || selectedLayout;
  const sections = (recommendation.section_labels || []).join("; ");
  const reasoning = recommendation.reasoning?.trim();
  const logoPart = includeLogo ? "Include company logo." : "No company logo.";
  const pagesPart = pageNumbers ? "Include page numbers." : "No page numbers.";
  const watermarkPart =
    watermark && watermark !== "none"
      ? `Use "${watermark}" watermark.`
      : "No watermark.";

  const buildLine =
    `Build a ${fmt.toUpperCase()} report with theme "${selectedTheme || recommendation.theme}" (${themeName}) ` +
    `and layout "${selectedLayout || recommendation.layout}" (${layoutName}). ` +
    `${logoPart} ${pagesPart} ${watermarkPart}` +
    (sections ? ` Include: ${sections}.` : "");

  return reasoning ? `${reasoning}\n\n${buildLine}` : buildLine;
}

export function buildButtonLabel(selectedFormat, recommendedFormat, loading) {
  if (loading) return "Building report…";
  const selected = normalizeOutputFormat(selectedFormat);
  const recommended = normalizeOutputFormat(recommendedFormat);
  const recSlug = recommended === "excel" ? "xlsx" : "pdf";
  if (selected === recommended) {
    return `Build report (Recommended ${recSlug})`;
  }
  const selectedSlug = selected === "excel" ? "xlsx" : "pdf";
  return `Build report (${selectedSlug})`;
}
