import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { apiFetch } from "../../config/api";
import { humanizeLabel, humanizeOutput } from "../../utils/chat";

export default function DataTableWithPagination({
  label,
  headers: initialHeaders,
  rows: initialRows,
  pagination: initialPagination,
  queryId,
}) {
  const [headers, setHeaders] = useState(initialHeaders || []);
  const [rows, setRows] = useState(initialRows || []);
  const [pagination, setPagination] = useState(initialPagination || null);
  const [sortBy, setSortBy] = useState(initialPagination?.sort_by || null);
  const [sortDir, setSortDir] = useState(initialPagination?.sort_dir || "desc");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setHeaders(initialHeaders || []);
    setRows(initialRows || []);
    setPagination(initialPagination || null);
  }, [initialHeaders, initialRows, initialPagination, queryId]);

  const fetchPage = useCallback(async (page, nextSortBy = sortBy, nextSortDir = sortDir) => {
    if (!queryId) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await apiFetch("/query/page", {
        method: "POST",
        body: JSON.stringify({
          query_id: queryId,
          page,
          page_size: pagination?.page_size || 20,
          sort_by: nextSortBy,
          sort_dir: nextSortDir,
        }),
      });
      setHeaders(payload.headers || []);
      setRows(payload.rows || []);
      setPagination(payload.pagination || null);
    } catch (err) {
      setError(err.message || "Failed to load page");
    } finally {
      setLoading(false);
    }
  }, [pagination?.page_size, queryId, sortBy, sortDir]);

  useEffect(() => {
    if (queryId && !(initialRows || []).length) {
      fetchPage(1);
    }
  }, [fetchPage, initialRows, queryId]);

  const handleSort = (header) => {
    const nextDir = sortBy === header && sortDir === "desc" ? "asc" : "desc";
    setSortBy(header);
    setSortDir(nextDir);
    fetchPage(1, header, nextDir);
  };

  if (!rows.length && !loading) return null;

  const page = pagination?.page || 1;
  const pageSize = pagination?.page_size || rows.length || 20;
  const total = pagination?.total_records ?? rows.length;
  const rangeStart = total ? (page - 1) * pageSize + 1 : 0;
  const rangeEnd = Math.min(page * pageSize, total);

  return (
    <motion.div
      className="ooa-table-wrap"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="ooa-table-wrap__header">
        <div className="ooa-table-wrap__label">{label}</div>
        <div className="ooa-table-wrap__meta">
          Showing {rangeStart}–{rangeEnd} of {total} records
        </div>
      </div>

      <div className="ooa-table-scroll">
        <table className="ooa-table ooa-table--sortable">
          <thead>
            <tr>
              {(headers || []).map((header) => (
                <th key={header}>
                  <button
                    type="button"
                    className="ooa-table__sort"
                    onClick={() => handleSort(header)}
                  >
                    {humanizeLabel(header)}
                    {sortBy === header ? (sortDir === "desc" ? " ↓" : " ↑") : null}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${index}-${String(row[0] || index)}`}>
                {(Array.isArray(row) ? row : Object.values(row)).map((cell, cellIndex) => (
                  <td key={`${index}-${cellIndex}`}>
                    {typeof cell === "string" ? humanizeOutput(cell) : cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error ? <div className="ooa-table-wrap__error">{error}</div> : null}

      {pagination ? (
        <motion.div className="ooa-table-pagination">
          <button
            type="button"
            className="ooa-glass-button"
            disabled={!pagination.has_prev || loading}
            onClick={() => fetchPage(page - 1)}
          >
            Previous
          </button>
          <span className="ooa-table-pagination__label">
            Page {pagination.page} of {pagination.total_pages}
          </span>
          <button
            type="button"
            className="ooa-glass-button"
            disabled={!pagination.has_next || loading}
            onClick={() => fetchPage(page + 1)}
          >
            Next
          </button>
          {pagination.has_next ? (
            <button
              type="button"
              className="ooa-disclosure-prompt__primary"
              disabled={loading}
              onClick={() => fetchPage(page + 1)}
            >
              Load more
            </button>
          ) : null}
        </motion.div>
      ) : null}
    </motion.div>
  );
}
