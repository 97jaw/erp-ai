import QueryTab from "./QueryTab";

export default function RightSidebar({
  id,
  open = false,
  queries,
  activeQueryId,
  previewQueryId,
  onSelect,
  onPreview,
  onClose,
  onReask,
}) {
  if (!queries.length) return null;

  const previewQuery = queries.find((query) => query.id === previewQueryId);

  return (
    <aside
      id={id}
      className={`ooa-right-sidebar ${open ? "is-open" : ""}`}
      aria-label="Query history"
    >
      <div className="ooa-right-sidebar__scroll">
        {queries.map((query, index) => (
          <div
            key={query.id}
            onMouseEnter={() => onPreview?.(query.id)}
            onMouseLeave={() => onPreview?.(null)}
          >
            <QueryTab
              query={query}
              tabNumber={queries.length - index}
              active={query.id === activeQueryId}
              onSelect={onSelect}
              onClose={onClose}
              onReask={onReask}
            />
          </div>
        ))}
      </div>
      {previewQuery && open ? (
        <div className="ooa-tab-preview" role="tooltip">
          <div className="ooa-tab-preview__title">Query: {previewQuery.question}</div>
          <div className="ooa-tab-preview__body">
            <p>{previewQuery.response?.text || "Generating response..."}</p>
          </div>
          <div className="ooa-tab-preview__hint">Click to view full response</div>
        </div>
      ) : null}
    </aside>
  );
}
