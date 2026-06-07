import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import KPICard from "./KPICard";
import DataTable from "./DataTable";
import DataTableWithPagination from "./DataTableWithPagination";
import FinancialReport from "./FinancialReport";
import BarChart from "./BarChart";
import LineChart from "./LineChart";
import PDFReportCard from "./PDFReportCard";
import GroupedTable from "./GroupedTable";
import DateRangeBadge from "./DateRangeBadge";
import DisclosurePrompt from "./DisclosurePrompt";
import {
  STANDARD_PAGE_SIZE,
  normalizeVisualization,
  resolveVisualizationLevel,
  supportsProgressiveDisclosure,
} from "../../utils/chat";

function buildClientPagination(resolved, rowCount) {
  const pageSize = resolved.page_size || STANDARD_PAGE_SIZE;
  const total = resolved.total_records ?? rowCount;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return {
    page: 1,
    page_size: pageSize,
    total_records: total,
    total_pages: totalPages,
    has_next: total > pageSize,
    has_prev: false,
  };
}

export default function VisualizationPanel({ viz }) {
  const normalized = useMemo(() => normalizeVisualization(viz), [viz]);
  const [level, setLevel] = useState(normalized?.level || "summary");
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setLevel(normalized?.level || "summary");
    setDismissed(false);
  }, [normalized?.query_id, normalized?.label, normalized?.visual_type]);

  const resolved = useMemo(
    () => resolveVisualizationLevel(normalized, level) || normalized,
    [normalized, level],
  );

  if (!resolved) return null;

  const showDisclosure = supportsProgressiveDisclosure(normalized)
    && level === "summary"
    && Boolean(normalized.can_expand)
    && !dismissed;

  const summaryChart = resolved.data?.summary_chart;
  const detailHeaders = resolved.data?.headers || resolved.data?.detail_table?.headers || [];
  const detailRows = resolved.data?.rows || [];
  const showDetail = level !== "summary"
    && (resolved.visual_type === "FINANCIAL_REPORT" || resolved.visual_type === "DATA_TABLE")
    && (detailRows.length > 0 || resolved.query_id);

  const tableLabel = resolved.detail_label || resolved.expand_label || "Account breakdown";
  const usePagination = Boolean(resolved.query_id) && level !== "full";

  return (
    <motion.div
      className="ooa-visual-panel"
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.35 }}
    >
      <DateRangeBadge
        dateFrom={resolved.date_from}
        dateTo={resolved.date_to}
        defaulted={resolved.date_was_defaulted}
      />

      {resolved.visual_type === "KPI_CARD" ? <KPICard data={resolved} /> : null}
      {resolved.visual_type === "FINANCIAL_REPORT" ? <FinancialReport data={resolved} /> : null}

      {resolved.visual_type === "DATA_TABLE" && level === "summary" ? (
        summaryChart ? (
          <BarChart data={summaryChart} />
        ) : (
          <KPICard
            data={{
              ...resolved,
              value: resolved.total_records ?? resolved.value ?? 0,
              unit: resolved.unit || "records",
            }}
          />
        )
      ) : null}

      {summaryChart && resolved.visual_type === "FINANCIAL_REPORT" ? (
        <BarChart data={summaryChart} />
      ) : null}

      {resolved.visual_type === "BAR_CHART" ? <BarChart data={resolved} /> : null}
      {resolved.visual_type === "LINE_CHART" ? <LineChart data={resolved} /> : null}

      {showDetail && usePagination ? (
        <DataTableWithPagination
          label={tableLabel}
          headers={detailHeaders}
          rows={detailRows}
          queryId={resolved.query_id}
          pagination={buildClientPagination(resolved, detailRows.length)}
        />
      ) : null}

      {showDetail && !usePagination ? (
        <DataTable
          data={{
            ...resolved,
            label: tableLabel,
            data: {
              ...(resolved.data || {}),
              headers: detailHeaders,
              rows: detailRows,
            },
          }}
          meta={resolved}
        />
      ) : null}

      {resolved.visual_type === "GROUPED_TABLE" ? <GroupedTable data={resolved} /> : null}
      {resolved.visual_type === "PDF_REPORT" ? (
        <PDFReportCard data={resolved.data} label={resolved.label} />
      ) : null}

      {showDisclosure ? (
        <DisclosurePrompt
          expandLabel={normalized.expand_label || "See account details"}
          onExpand={() => setLevel("standard")}
          onDismiss={() => setDismissed(true)}
        />
      ) : null}

      {level === "standard"
        && resolved.query_id
        && (resolved.total_records || 0) > (resolved.page_size || STANDARD_PAGE_SIZE) ? (
          <div className="ooa-disclosure-prompt__more">
            <button type="button" className="ooa-disclosure-prompt__primary" onClick={() => setLevel("full")}>
              Load full report ({resolved.total_records} records)
            </button>
          </div>
        ) : null}

      {level === "full" && showDetail && !usePagination && resolved.total_records > detailRows.length ? (
        <DataTable
          data={{
            ...resolved,
            label: tableLabel,
            data: {
              ...(resolved.data || {}),
              headers: detailHeaders,
              rows: resolved.data?.all_rows || resolved.data?.detail_table?.rows || detailRows,
            },
          }}
          meta={{
            ...resolved,
            shown_records: (resolved.data?.all_rows || detailRows).length,
            total_records: resolved.total_records,
          }}
        />
      ) : null}
    </motion.div>
  );
}
