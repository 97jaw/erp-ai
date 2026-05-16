import { motion } from "framer-motion";
import { useCountUp } from "../../hooks/useCountUp";

function MetricCell({ label, value, unit, color, delay }) {
  const animatedValue = useCountUp(typeof value === "number" ? value : 0);
  const display = unit === "%"
    ? `${animatedValue.toFixed(2)}%`
    : `AED ${Math.abs(animatedValue).toLocaleString("en-AE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

  return (
    <motion.div
      className="ooa-report-card__metric"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      style={{ borderColor: color }}
    >
      <div className="ooa-report-card__metric-label">{label}</div>
      <div className="ooa-report-card__metric-value" style={{ color }}>
        {display}
      </div>
    </motion.div>
  );
}

export default function FinancialReport({ data }) {
  if (!data?.kpis) return null;

  const { kpis, label, date_from, date_to } = data;
  const profitTone = kpis.net_profit >= 0 ? "var(--ooa-cyan)" : "var(--ooa-coral)";

  return (
    <motion.div
      className="ooa-report-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="ooa-report-card__header">
        <span className="ooa-report-card__title">{label}</span>
        <span className="ooa-report-card__date">{date_from} → {date_to}</span>
      </div>
      <div className="ooa-report-card__grid">
        <MetricCell label="Income" value={kpis.total_income} color="var(--ooa-cyan)" delay={0.1} />
        <MetricCell label="Expenses" value={kpis.total_expense} color="var(--ooa-coral)" delay={0.2} />
        <MetricCell label="Net Profit" value={kpis.net_profit} color={profitTone} delay={0.3} />
        <MetricCell label="Margin" value={kpis.margin} unit="%" color={profitTone} delay={0.4} />
      </div>
    </motion.div>
  );
}
