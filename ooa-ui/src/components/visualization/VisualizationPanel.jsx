import { motion } from "framer-motion";
import KPICard from "./KPICard";
import DataTable from "./DataTable";
import FinancialReport from "./FinancialReport";
import BarChart from "./BarChart";
import LineChart from "./LineChart";
import PDFReportCard from "./PDFReportCard";
import GroupedTable from "./GroupedTable";

export default function VisualizationPanel({ viz }) {
  if (!viz) return null;

  return (
    <motion.div
      className="ooa-visual-panel"
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.35 }}
    >
      {viz.visual_type === "KPI_CARD" ? <KPICard data={viz} /> : null}
      {viz.visual_type === "DATA_TABLE" ? <DataTable data={viz} /> : null}
      {viz.visual_type === "FINANCIAL_REPORT" ? <FinancialReport data={viz} /> : null}
      {viz.visual_type === "BAR_CHART" ? <BarChart data={viz} /> : null}
      {viz.visual_type === "LINE_CHART" ? <LineChart data={viz} /> : null}
      {viz.visual_type === "GROUPED_TABLE" ? <GroupedTable data={viz} /> : null}
      {viz.visual_type === "PDF_REPORT" ? <PDFReportCard data={viz.data} label={viz.label} /> : null}
    </motion.div>
  );
}
