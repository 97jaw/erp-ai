import { useState } from "react";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function monthStartIso() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
}

export default function DateRangePicker({ onApply, onCancel }) {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  return (
    <div className="ooa-date-picker">
      <div className="ooa-date-picker__row">
        <label>
          <span>From</span>
          <input
            type="date"
            value={dateFrom}
            max={dateTo}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </label>
        <label>
          <span>To</span>
          <input
            type="date"
            value={dateTo}
            min={dateFrom}
            max={todayIso()}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </label>
      </div>
      <div className="ooa-date-picker__actions">
        <button type="button" className="ooa-disclosure-prompt__primary" onClick={() => onApply(dateFrom, dateTo)}>
          Apply range
        </button>
        <button type="button" className="ooa-disclosure-prompt__secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
