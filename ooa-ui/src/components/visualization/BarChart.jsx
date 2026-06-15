import { useMemo } from "react";
import { motion } from "framer-motion";
import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function normalizeBarSeries(data = {}) {
  if (Array.isArray(data.rows) && data.rows.length) {
    return data.rows.map((row, index) => {
      if (Array.isArray(row)) {
        return { label: String(row[0] ?? index), value: Number(row[1] ?? 0) };
      }
      if (row && typeof row === "object") {
        const label = row.label ?? row.name ?? row.category ?? `Item ${index + 1}`;
        const value = Number(row.value ?? row.amount ?? row.total ?? 0);
        return { label: String(label), value };
      }
      return { label: String(index + 1), value: Number(row) || 0 };
    });
  }

  const labels = data.labels || [];
  const values = data.values || data.series?.[0]?.values || [];
  if (labels.length) {
    return labels.map((label, index) => ({
      label: String(label),
      value: Number(values[index] ?? 0),
    }));
  }

  return [];
}

function fmtAxis(value) {
  const n = Number(value);
  if (isNaN(n)) return value;
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

function fmtTooltip(value) {
  const n = Number(value);
  if (isNaN(n)) return value;
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export default function BarChart({ data }) {
  const series = useMemo(() => normalizeBarSeries(data?.data), [data]);
  if (!series.length) return null;

  const scrollable = Boolean(data?.scrollable) || series.length > 6;
  const chartWidth = Math.max(series.length * 56, 400);

  return (
    <motion.div
      className="ooa-chart-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <motion.div
        className="ooa-chart-card__label"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
      >
        {data.label}
      </motion.div>
      <div
        className={`ooa-chart-card__canvas${scrollable ? " ooa-chart-card__canvas--scroll" : ""}`}
        style={scrollable ? { overflowX: "auto", overflowY: "hidden" } : undefined}
      >
        <ResponsiveContainer width={scrollable ? chartWidth : "100%"} height={scrollable ? 260 : 240}>
          <RechartsBarChart data={series} margin={{ top: 8, right: 8, left: 8, bottom: scrollable ? 8 : 0 }}>
            <CartesianGrid stroke="var(--ooa-glass-border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "var(--ooa-text-muted)", fontSize: 11 }}
              angle={scrollable ? -35 : 0}
              textAnchor={scrollable ? "end" : "middle"}
              height={scrollable ? 56 : 30}
              interval={0}
            />
            <YAxis tickFormatter={fmtAxis} tick={{ fill: "var(--ooa-text-muted)", fontSize: 11 }} width={60} />
            <Tooltip
              formatter={(value) => [fmtTooltip(value), data.currency || "Value"]}
              contentStyle={{
                background: "var(--ooa-glass-bg)",
                border: "1px solid var(--ooa-glass-border)",
                borderRadius: 12,
                color: "var(--ooa-text)",
              }}
            />
            <Bar
              dataKey="value"
              fill="url(#ooaBarGradient)"
              radius={[8, 8, 0, 0]}
              animationDuration={800}
              animationEasing="ease-out"
            />
            <defs>
              <linearGradient id="ooaBarGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--ooa-gold)" />
                <stop offset="100%" stopColor="color-mix(in srgb, var(--ooa-gold) 55%, white)" />
              </linearGradient>
            </defs>
          </RechartsBarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
