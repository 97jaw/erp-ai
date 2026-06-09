import { motion } from "framer-motion";
import BarChart from "../BarChart";
import ExpenseBudgetBar from "./shared/ExpenseBudgetBar";
import OverBudgetBadge from "./shared/OverBudgetBadge";
import InsightCallouts from "./InsightCallouts";
import { formatCurrency, formatPercent } from "./formatUtils";

function KPIGrid({ kpis = {}, currency = "AED" }) {
  const entries = Object.values(kpis);
  if (!entries.length) return null;

  return (
    <div className="ooa-pe-kpi-grid">
      {entries.map((kpi, index) => {
        const isPercent = kpi.unit === "%";
        const valueLabel = isPercent
          ? formatPercent(kpi.value)
          : formatCurrency(kpi.value, kpi.unit || currency, { compact: true });
        return (
          <motion.div
            key={kpi.label || index}
            className="ooa-pe-kpi"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <div className="ooa-pe-kpi__label">{kpi.label}</div>
            <div className="ooa-pe-kpi__value">{valueLabel}</div>
            {kpi.trend?.context ? (
              <div className={`ooa-pe-kpi__trend ooa-pe-kpi__trend--${kpi.trend.direction || "neutral"}`}>
                {kpi.trend.context}
              </div>
            ) : null}
          </motion.div>
        );
      })}
    </div>
  );
}

function ExpenseLinesTable({ lines = [], currency = "AED" }) {
  if (!lines.length) return null;
  return (
    <div className="ooa-pe-lines">
      <div className="ooa-pe-section-title">Expense lines</div>
      <div className="ooa-pe-lines__table">
        {lines.map((line, index) => (
          <div key={`${line.label}-${index}`} className="ooa-pe-lines__row">
            <span>{line.label || line.name}</span>
            <span>{formatCurrency(line.amount ?? line.value, currency)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ProjectExpenseSummary({ data }) {
  if (!data) return null;

  const currency = data.currency || "AED";
  const summaryChart = data.data?.summary_chart;

  return (
    <motion.div
      className="ooa-pe-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="ooa-pe-card__header">
        <div>
          <div className="ooa-pe-card__title">{data.label || data.project_name}</div>
          {data.agreement_name ? (
            <div className="ooa-pe-card__subtitle">{data.agreement_name}</div>
          ) : null}
        </div>
        <OverBudgetBadge show={data.is_over_budget} />
      </div>

      <ExpenseBudgetBar
        spentPct={data.spend_percent_of_wo}
        isOverBudget={data.is_over_budget}
      />

      <KPIGrid kpis={data.kpis} currency={currency} />
      <InsightCallouts insights={data.insights} />

      {summaryChart ? <BarChart data={summaryChart} /> : null}
      <ExpenseLinesTable lines={data.expense_lines} currency={currency} />
    </motion.div>
  );
}
