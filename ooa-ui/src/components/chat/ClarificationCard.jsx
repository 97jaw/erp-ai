import { useState } from "react";
import { motion } from "framer-motion";
import { isArabic } from "../../utils/chat";
import { clarificationLabel, clarificationQuestion } from "../../utils/clarify";
import DateRangePicker from "./DateRangePicker";

export default function ClarificationCard({ clarification, originalQuery, onSelect, onSkip }) {
  const [showDatePicker, setShowDatePicker] = useState(false);
  if (!clarification) return null;

  const question = clarificationQuestion(clarification);
  const rtl = isArabic(question);
  const options = clarification.options?.length
    ? clarification.options
    : (clarification.matches || []).map((match, index) => ({
      id: String(match.id ?? index),
      label: match.wo_ref_no ? `${match.name} (${match.wo_ref_no})` : (match.name || String(match.id)),
      entity_type: match.entity_type || "project",
      entity_id: match.id,
      action: "confirm_entity",
      is_default: index === 0,
    }));

  const handleOption = (option) => {
    if (option.action === "open_date_picker") {
      setShowDatePicker(true);
      return;
    }
    onSelect?.(option, originalQuery);
  };

  const handleDateApply = (dateFrom, dateTo) => {
    onSelect?.(
      { query_suffix: ` from ${dateFrom} to ${dateTo}` },
      originalQuery,
    );
    setShowDatePicker(false);
  };

  return (
    <motion.div
      className="ooa-clarify-card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{ direction: rtl ? "rtl" : "ltr", textAlign: rtl ? "right" : "left" }}
    >
      <p className="ooa-clarify-card__question">{question}</p>

      <div className="ooa-clarify-card__options">
        {options.map((option) => (
          <button
            key={option.id}
            type="button"
            className={`ooa-clarify-card__option${option.is_default ? " ooa-clarify-card__option--default" : ""}`}
            onClick={() => handleOption(option)}
          >
            {clarificationLabel(option, clarification)}
            {option.is_default ? <span className="ooa-clarify-card__badge">Default</span> : null}
          </button>
        ))}
      </div>

      {showDatePicker ? (
        <DateRangePicker
          onApply={handleDateApply}
          onCancel={() => setShowDatePicker(false)}
        />
      ) : null}

      {clarification.skip_option ? (
        <button
          type="button"
          className="ooa-clarify-card__skip"
          onClick={() => onSkip?.(clarification.skip_option, originalQuery)}
        >
          {clarificationLabel(clarification.skip_option, clarification)}
        </button>
      ) : null}
    </motion.div>
  );
}
