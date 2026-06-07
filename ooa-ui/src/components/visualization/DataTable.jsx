import { motion } from "framer-motion";
import { humanizeLabel, humanizeOutput } from "../../utils/chat";

export default function DataTable({ data, meta }) {
  if (!data?.data?.rows?.length) return null;

  const { headers, rows } = data.data;
  const pageSize = meta?.page_size || 20;
  const visibleRows = rows.slice(0, pageSize);
  const totalRecords = meta?.total_records ?? rows.length;
  const shownRecords = meta?.shown_records ?? visibleRows.length;

  return (
    <motion.div
      className="ooa-table-wrap"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="ooa-table-wrap__label">{data.label}</div>
      <div className="ooa-table-scroll">
        <table className="ooa-table">
          <thead>
            <tr>
              {(headers || Object.keys(rows[0] || {})).map((header) => (
                <th key={header}>{humanizeLabel(header)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, index) => (
              <motion.tr
                key={`${index}-${String(row[0] || index)}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04 }}
              >
                {(Array.isArray(row) ? row : Object.values(row)).map((cell, cellIndex) => (
                  <td key={`${index}-${cellIndex}`}>
                    {typeof cell === "string" ? humanizeOutput(cell) : cell}
                  </td>
                ))}
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalRecords > shownRecords ? (
        <div className="ooa-table-wrap__meta">
          Showing {shownRecords} of {totalRecords} records
        </div>
      ) : null}
    </motion.div>
  );
}
