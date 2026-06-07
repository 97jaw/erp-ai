/** Build progressive inspection bullet lines from API inspection payload. */

function formatDimensionList(dimensions) {
  if (!dimensions?.length) return null;
  const labels = dimensions.map((d) =>
    String(d).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
  );
  if (labels.length === 1) return labels[0];
  return `${labels.length} dimensions (${labels.slice(0, 3).join(", ")})`;
}

export function buildInspectionLines(inspection) {
  if (!inspection || inspection.item_count === 0) {
    return ["No structured data detected"];
  }

  const lines = [];

  if (inspection.item_count > 1) {
    lines.push(`${inspection.item_count} related items dropped`);
  }

  lines.push(`Detected: ${inspection.display_type || inspection.primary_data_type}`);

  if (inspection.report_subject) {
    lines.push(`Subject: ${inspection.report_subject}`);
  }

  if (inspection.date_range) {
    lines.push(`Range: ${inspection.date_range}`);
  }

  if (inspection.row_count > 0) {
    const noun = inspection.row_count === 1 ? "record" : "records";
    lines.push(`Records: ${inspection.row_count.toLocaleString()} ${noun}`);
  } else if (inspection.metric_count > 0) {
    lines.push(`Metrics: ${inspection.metric_count} KPIs`);
  }

  const dimLine = formatDimensionList(inspection.dimensions);
  if (dimLine) {
    lines.push(dimLine);
  }

  if (inspection.has_comparison) {
    lines.push("Includes period comparison");
  }

  if (inspection.has_time_series) {
    lines.push("Spans multiple time periods");
  }

  if (inspection.has_negatives) {
    lines.push("Includes negative values");
  }

  const depth = inspection.is_summary_or_detailed;
  if (depth === "detailed") {
    lines.push("Detailed dataset — appendix-friendly");
  } else if (depth === "kpi_only") {
    lines.push("Summary-level KPIs");
  }

  if (inspection.data_completeness != null && inspection.data_completeness < 0.75) {
    lines.push("Some fields are incomplete — narrative summary will help");
  }

  return lines;
}
