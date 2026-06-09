export function formatCurrency(value, currency = "AED", { compact = false } = {}) {
  const amount = Number(value) || 0;
  if (compact && Math.abs(amount) >= 1_000_000) {
    return `${currency} ${(amount / 1_000_000).toFixed(2)}M`;
  }
  if (compact && Math.abs(amount) >= 1_000) {
    return `${currency} ${(amount / 1_000).toFixed(0)}K`;
  }
  return `${currency} ${Math.abs(amount).toLocaleString("en-AE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

export function formatPercent(value) {
  const pct = Number(value) || 0;
  return `${pct.toFixed(pct % 1 === 0 ? 0 : 1)}%`;
}
