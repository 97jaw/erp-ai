import { motion } from "framer-motion";
import { useCountUp } from "../../hooks/useCountUp";

function formatNumber(value) {
  return Math.abs(value).toLocaleString("en-AE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

export default function KPICard({ data }) {
  const animatedValue = useCountUp(typeof data?.value === "number" ? data.value : 0);
  if (!data) return null;

  const { label, value, unit, data: details } = data;
  const isNegative = value < 0;

  return (
    <motion.div
      className={`ooa-kpi-card ${isNegative ? "ooa-kpi-card--negative" : "ooa-kpi-card--positive"}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <motion.div className="ooa-kpi-card__label" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
        {label}
      </motion.div>
      <motion.div
        className="ooa-kpi-card__value"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.2 }}
      >
        {unit} {formatNumber(animatedValue)}
      </motion.div>
      {details ? (
        <motion.div className="ooa-kpi-card__details" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
          {Object.entries(details).slice(0, 4).map(([key, entryValue]) =>
            typeof entryValue === "number" ? (
              <div key={key} className="ooa-kpi-card__detail-row">
                <span>{key.replace(/_/g, " ")}</span>
                <span>{entryValue.toLocaleString("en-AE", { maximumFractionDigits: 2 })}</span>
              </div>
            ) : null
          )}
        </motion.div>
      ) : null}
    </motion.div>
  );
}
