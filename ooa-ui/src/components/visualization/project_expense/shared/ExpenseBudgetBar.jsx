import { formatPercent } from "../formatUtils";

export default function ExpenseBudgetBar({ spentPct = 0, isOverBudget = false }) {
  const pct = Math.min(Math.max(Number(spentPct) || 0, 0), 120);
  const fillWidth = Math.min(pct, 100);

  return (
    <div className="ooa-pe-budget-bar">
      <div className="ooa-pe-budget-bar__track">
        <div
          className={`ooa-pe-budget-bar__fill ${isOverBudget ? "ooa-pe-budget-bar__fill--over" : ""}`}
          style={{ width: `${fillWidth}%` }}
        />
        {pct > 100 ? (
          <div
            className="ooa-pe-budget-bar__overflow"
            style={{ width: `${Math.min(pct - 100, 20)}%` }}
          />
        ) : null}
      </div>
      <div className="ooa-pe-budget-bar__label">{formatPercent(spentPct)} of W.O</div>
    </div>
  );
}
