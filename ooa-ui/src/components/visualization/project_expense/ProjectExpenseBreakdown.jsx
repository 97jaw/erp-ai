import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { formatCurrency } from "./formatUtils";

function AccountRows({ accounts = [], currency }) {
  if (!accounts.length) return null;
  return (
    <div className="ooa-pe-breakdown__accounts">
      {accounts.map((account) => (
        <div key={`${account.code}-${account.name}`} className="ooa-pe-breakdown__account">
          <span>
            {account.code ? `${account.code} ` : ""}
            {account.name}
          </span>
          <span>{formatCurrency(account.total, currency, { compact: true })}</span>
        </div>
      ))}
    </div>
  );
}

function SubgroupRows({ subgroups = [], currency, expanded, onToggle }) {
  return subgroups.map((subgroup, index) => {
    const key = `${subgroup.code || subgroup.name}-${index}`;
    const isOpen = expanded.has(key);
    const hasAccounts = (subgroup.accounts || []).length > 0;
    return (
      <div key={key} className="ooa-pe-breakdown__subgroup">
        <button
          type="button"
          className="ooa-pe-breakdown__row ooa-pe-breakdown__row--subgroup"
          onClick={() => (hasAccounts ? onToggle(key) : undefined)}
          disabled={!hasAccounts}
        >
          <span>
            {hasAccounts ? (isOpen ? "▾" : "▸") : "•"} {subgroup.name}
          </span>
          <span>{formatCurrency(subgroup.total, currency, { compact: true })}</span>
        </button>
        {hasAccounts && isOpen ? (
          <AccountRows accounts={subgroup.accounts} currency={currency} />
        ) : null}
      </div>
    );
  });
}

function BreakdownGroups({ groups = [], currency }) {
  const [expandedGroups, setExpandedGroups] = useState(() => {
    const initial = new Set();
    groups.forEach((group, index) => {
      if (group.expanded || index === 0) {
        initial.add(`${group.code || group.name}-${index}`);
      }
    });
    return initial;
  });
  const [expandedSubgroups, setExpandedSubgroups] = useState(() => new Set());

  const toggleGroup = (key) => {
    setExpandedGroups((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleSubgroup = (key) => {
    setExpandedSubgroups((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return groups.map((group, index) => {
    const key = `${group.code || group.name}-${index}`;
    const isOpen = expandedGroups.has(key);
    const hasSubgroups = (group.subgroups || []).length > 0;
    return (
      <motion.div
        key={key}
        className="ooa-pe-breakdown__group"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.03 }}
      >
        <button
          type="button"
          className="ooa-pe-breakdown__row ooa-pe-breakdown__row--group"
          onClick={() => (hasSubgroups ? toggleGroup(key) : undefined)}
          disabled={!hasSubgroups}
        >
          <span>
            {hasSubgroups ? (isOpen ? "▾" : "▸") : "•"} {group.name}
          </span>
          <span>
            {formatCurrency(group.total, currency, { compact: true })}
            {group.pct ? ` · ${group.pct}%` : ""}
          </span>
        </button>
        {hasSubgroups && isOpen ? (
          <div className="ooa-pe-breakdown__subgroups">
            <SubgroupRows
              subgroups={group.subgroups}
              currency={currency}
              expanded={expandedSubgroups}
              onToggle={toggleSubgroup}
            />
          </div>
        ) : null}
      </motion.div>
    );
  });
}

export default function ProjectExpenseBreakdown({ data }) {
  const currency = data?.currency || "AED";
  const groups = useMemo(() => data?.groups || [], [data?.groups]);

  if (!groups.length) return null;

  return (
    <motion.div
      className="ooa-pe-card ooa-pe-breakdown"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="ooa-pe-card__header">
        <div>
          <div className="ooa-pe-card__title">{data.label}</div>
          <div className="ooa-pe-card__subtitle">
            Total {formatCurrency(data.grand_total, currency)}
          </div>
        </div>
      </div>

      <BreakdownGroups groups={groups} currency={currency} />

      {data.truncated ? (
        <div className="ooa-pe-breakdown__note">Showing top groups — ask for full GL export if needed.</div>
      ) : null}
    </motion.div>
  );
}
