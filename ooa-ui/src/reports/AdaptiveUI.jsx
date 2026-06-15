import { useState } from "react";
import "./reports.css";

/** Render a pill_select block. */
function PillSelect({ block, onSelect }) {
  const [selected, setSelected] = useState([]);
  const [typed, setTyped] = useState("");

  const handlePillClick = (optionId) => {
    if (block.mode === "multi") {
      const next = selected.includes(optionId)
        ? selected.filter((id) => id !== optionId)
        : [...selected, optionId];
      setSelected(next);
    } else {
      setSelected([optionId]);
      const option = block.options.find((o) => o.id === optionId);
      if (option) onSelect(option.label, option);
    }
  };

  const handleTypedSubmit = (e) => {
    e.preventDefault();
    if (typed.trim()) {
      onSelect(typed.trim());
      setTyped("");
    }
  };

  return (
    <div className="rpt-ui-block rpt-pill-select">
      {block.prompt ? (
        <p className="rpt-ui-block__prompt">{block.prompt}</p>
      ) : null}
      <div className="rpt-pill-select__pills">
        {(block.options || []).map((opt) => (
          <button
            key={opt.id}
            type="button"
            className={`rpt-pill${selected.includes(opt.id) ? " rpt-pill--active" : ""}`}
            onClick={() => handlePillClick(opt.id)}
          >
            {opt.icon ? (
              <span className="rpt-pill__icon" aria-hidden="true">
                {opt.icon}
              </span>
            ) : null}
            <span className="rpt-pill__label">{opt.label}</span>
          </button>
        ))}
      </div>
      {block.allow_typed_input ? (
        <form className="rpt-pill-select__typed" onSubmit={handleTypedSubmit}>
          <input
            type="text"
            className="rpt-typed-input"
            placeholder="Or type here..."
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
          />
          <button type="submit" className="rpt-typed-submit" disabled={!typed.trim()}>
            →
          </button>
        </form>
      ) : null}
    </div>
  );
}

/** Render a date_quick block. */
function DateQuick({ block, onSelect }) {
  const [showCustom, setShowCustom] = useState(false);
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const handlePreset = (preset) => {
    onSelect(`${preset.from_date} to ${preset.to_date} (${preset.label})`);
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (customFrom && customTo) {
      onSelect(`${customFrom} to ${customTo} (Custom)`);
    }
  };

  return (
    <div className="rpt-ui-block rpt-date-quick">
      {block.prompt ? (
        <p className="rpt-ui-block__prompt">{block.prompt}</p>
      ) : null}
      <div className="rpt-date-quick__presets">
        {(block.presets || []).map((preset) => (
          <button
            key={preset.id}
            type="button"
            className="rpt-pill"
            onClick={() => handlePreset(preset)}
          >
            {preset.label}
          </button>
        ))}
        <button
          type="button"
          className={`rpt-pill${showCustom ? " rpt-pill--active" : ""}`}
          onClick={() => setShowCustom((v) => !v)}
        >
          Custom
        </button>
      </div>
      {showCustom ? (
        <form className="rpt-date-quick__custom" onSubmit={handleCustomSubmit}>
          <label className="rpt-date-label">
            From
            <input
              type="date"
              className="rpt-date-input"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              required
            />
          </label>
          <label className="rpt-date-label">
            To
            <input
              type="date"
              className="rpt-date-input"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              required
            />
          </label>
          <button
            type="submit"
            className="rpt-pill rpt-pill--accent"
            disabled={!customFrom || !customTo}
          >
            Apply
          </button>
        </form>
      ) : null}
    </div>
  );
}

/** Render a format_select block. */
function FormatSelect({ block, onSelect }) {
  const FORMAT_LABELS = {
    pdf: "PDF",
    excel: "Excel",
    both: "PDF + Excel",
  };
  return (
    <div className="rpt-ui-block rpt-format-select">
      {block.prompt ? (
        <p className="rpt-ui-block__prompt">{block.prompt}</p>
      ) : null}
      <div className="rpt-pill-select__pills">
        {(block.options || ["pdf", "excel", "both"]).map((opt) => (
          <button
            key={opt}
            type="button"
            className="rpt-pill"
            onClick={() => onSelect(FORMAT_LABELS[opt] || opt)}
          >
            {FORMAT_LABELS[opt] || opt}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Render a file_ready card. */
function FileReady({ file }) {
  return (
    <div className="rpt-file-ready">
      <div className="rpt-file-ready__icon" aria-hidden="true">
        {file.format === "pdf" ? "📄" : file.format === "excel" ? "📊" : "📁"}
      </div>
      <div className="rpt-file-ready__info">
        <span className="rpt-file-ready__name">{file.filename}</span>
        <span className="rpt-file-ready__format">
          {file.format?.toUpperCase()}
        </span>
      </div>
      <a
        href={file.url || `/reports/download/${file.report_id}`}
        download={file.filename}
        className="rpt-file-ready__download"
        target="_blank"
        rel="noreferrer"
      >
        Download
      </a>
    </div>
  );
}

/**
 * AdaptiveUI — renders interactive blocks from the agent.
 *
 * onUserAction: (payload) => void
 *   payload is string (legacy) or { label, option, block }
 */
export default function AdaptiveUI({ block, onUserAction }) {
  if (!block) return null;

  const { type } = block;

  const handleSelect = (label, option = null) => {
    onUserAction?.({ label, option, block });
  };

  if (type === "pill_select") {
    return <PillSelect block={block} onSelect={handleSelect} />;
  }
  if (type === "date_quick") {
    return <DateQuick block={block} onSelect={(text) => onUserAction?.(text)} />;
  }
  if (type === "format_select") {
    return <FormatSelect block={block} onSelect={(text) => onUserAction?.(text)} />;
  }
  if (type === "file_ready") {
    return <FileReady file={block} />;
  }

  return null;
}

/** Render a list of file_ready blocks (from file_ready_list events). */
export function FileReadyList({ files }) {
  if (!files?.length) return null;
  return (
    <div className="rpt-file-ready-list">
      {files.map((f) => (
        <FileReady key={f.report_id} file={f} />
      ))}
    </div>
  );
}
