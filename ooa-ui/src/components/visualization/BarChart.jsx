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

export default function BarChart({ data }) {
  const series = useMemo(() => normalizeBarSeries(data?.data), [data]);
  if (!series.length) return null;

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
      <div className="ooa-chart-card__canvas">
        <ResponsiveContainer width="100%" height={240}>
          <RechartsBarChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--ooa-glass-border)" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: "var(--ooa-text-muted)", fontSize: 11 }} />
            <YAxis tick={{ fill: "var(--ooa-text-muted)", fontSize: 11 }} />
            <Tooltip
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
