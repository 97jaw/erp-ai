import { API_BASE } from "../../utils/chat";

export default function PDFReportCard({ data, label }) {
  const pdfUrl = data?.pdf_url ? `${API_BASE}${data.pdf_url}` : null;
  const previewUrl = data?.preview_image ? `${API_BASE}${data.preview_image}` : null;
  const sizeKb = data?.size_bytes ? Math.round(data.size_bytes / 1024) : null;

  if (!pdfUrl) return null;

  return (
    <div className="ooa-pdf-card">
      {previewUrl ? (
        <img className="ooa-pdf-card__preview" src={previewUrl} alt="" aria-hidden="true" />
      ) : null}
      <div className="ooa-pdf-card__label">{label || "Generated report"}</div>
      <div className="ooa-pdf-card__meta">
        {data?.page_count ? `${data.page_count} pages` : null}
        {sizeKb ? ` · ${sizeKb} KB` : null}
      </div>
      <div className="ooa-pdf-card__actions">
        <a className="ooa-glass-button ooa-glass-button--primary" href={pdfUrl} target="_blank" rel="noreferrer">
          Open PDF
        </a>
        <a className="ooa-glass-button" href={pdfUrl} download>
          Download
        </a>
      </div>
    </div>
  );
}
