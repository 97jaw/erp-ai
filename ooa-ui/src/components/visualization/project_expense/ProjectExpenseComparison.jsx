import { motion } from "framer-motion";
import BarChart from "../BarChart";
import OverBudgetBadge from "./shared/OverBudgetBadge";
import InsightCallouts from "./InsightCallouts";
import { formatCurrency, formatPercent } from "./formatUtils";

function ComparisonTable({ projects = [], currency = "AED" }) {
  if (!projects.length) return null;

  return (
    <div className="ooa-pe-compare__table-wrap">
      <table className="ooa-pe-compare__table">
        <thead>
          <tr>
            <th>Project</th>
            <th>W.O</th>
            <th>Spent</th>
            <th>Spend %</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr
              key={project.id || project.name}
              className={project.is_over_budget ? "ooa-pe-compare__row--alert" : ""}
            >
              <td>
                <span className="ooa-pe-compare__rank">#{project.rank}</span>
                {project.name}
              </td>
              <td>{formatCurrency(project.wo_amount, currency, { compact: true })}</td>
              <td>{formatCurrency(project.total_expenses, currency, { compact: true })}</td>
              <td>{formatPercent(project.spend_pct)}</td>
              <td>
                <OverBudgetBadge
                  show={project.is_over_budget}
                  label={project.is_over_budget ? "Over" : "On track"}
                />
                {!project.is_over_budget ? (
                  <span className="ooa-pe-badge ooa-pe-badge--ok">On track</span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ComparisonTotals({ totals = {}, currency = "AED" }) {
  if (!totals || !Object.keys(totals).length) return null;
  return (
    <div className="ooa-pe-compare__totals">
      <div>
        <span>Combined W.O</span>
        <strong>{formatCurrency(totals.combined_wo, currency, { compact: true })}</strong>
      </div>
      <div>
        <span>Combined spend</span>
        <strong>{formatCurrency(totals.combined_expenses, currency, { compact: true })}</strong>
      </div>
      <div>
        <span>Over budget</span>
        <strong>{totals.over_budget_count || 0}</strong>
      </div>
    </div>
  );
}

export default function ProjectExpenseComparison({ data }) {
  if (!data) return null;

  const currency = data.currency || "AED";
  const summaryChart = data.data?.summary_chart;

  return (
    <motion.div
      className="ooa-pe-card ooa-pe-compare"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="ooa-pe-card__header">
        <div className="ooa-pe-card__title">{data.label || "Project Comparison"}</div>
      </div>

      <InsightCallouts insights={data.insights} />
      <ComparisonTable projects={data.projects} currency={currency} />
      <ComparisonTotals totals={data.totals} currency={currency} />
      {summaryChart ? <BarChart data={summaryChart} /> : null}
    </motion.div>
  );
}
