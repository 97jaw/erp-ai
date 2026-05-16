import { useMemo, useState } from "react";
import { motion } from "framer-motion";

function formatAggregateValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return value.toLocaleString();
  }
  return String(value);
}

function GroupedTableRows({ groups, level = 0 }) {
  const [expanded, setExpanded] = useState(() => new Set());

  const toggle = (key) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return groups.map((group, index) => {
    const key = `${level}-${group.name}-${index}`;
    const children = group.children || [];
    const hasChildren = children.length > 0;
    const isOpen = expanded.has(key);
    const aggregateEntries = Object.entries(group.aggregates || {});

    return (
      <motion.div
        key={key}
        className="ooa-grouped-table__group"
        style={{ marginLeft: level * 16 }}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.03 }}
      >
        <button
          type="button"
          className="ooa-grouped-table__header"
          onClick={() => (hasChildren ? toggle(key) : undefined)}
          disabled={!hasChildren}
        >
          <span className="ooa-grouped-table__name">
            {hasChildren ? (isOpen ? "▾" : "▸") : "•"} {group.name}
          </span>
          <span className="ooa-grouped-table__metrics">
            {aggregateEntries.map(([metric, value]) => (
              <span key={metric} className="ooa-grouped-table__metric">
                {metric}: {formatAggregateValue(value)}
              </span>
            ))}
          </span>
        </button>
        {hasChildren && isOpen ? (
          <GroupedTableRows groups={children} level={level + 1} />
        ) : null}
      </motion.div>
    );
  });
}

export default function GroupedTable({ data }) {
  const groups = useMemo(
    () => data?.data?.groups || data?.groups || [],
    [data],
  );

  if (!groups.length) return null;

  return (
    <motion.div
      className="ooa-grouped-table"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <motion.div
        className="ooa-grouped-table__label"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
      >
        {data.label}
      </motion.div>
      <GroupedTableRows groups={groups} />
    </motion.div>
  );
}
