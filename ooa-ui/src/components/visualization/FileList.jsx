import { resolveApiBase } from "../../config/api";

function formatBytes(value) {
  const size = Number(value);
  if (!Number.isFinite(size) || size <= 0) return "";
  if (size >= 1_048_576) return `${(size / 1_048_576).toFixed(1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(0)} KB`;
  return `${size} B`;
}

function mimeIcon(mimetype = "") {
  const type = String(mimetype).toLowerCase();
  if (type.includes("pdf")) return "PDF";
  if (type.startsWith("image/")) return "IMG";
  if (type.includes("spreadsheet") || type.includes("excel") || type.includes("sheet")) return "XLS";
  if (type.includes("word") || type.includes("document")) return "DOC";
  if (type.includes("zip") || type.includes("compressed") || type.includes("archive")) return "ZIP";
  if (type.startsWith("text/")) return "TXT";
  return "FILE";
}

function resolveDownloadUrl(file) {
  const path = file.download_url || (file.download_token ? `/attachments/download/${file.download_token}` : "");
  if (!path) return null;
  if (path.startsWith("http")) return path;
  const base = resolveApiBase().replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

function splitLabel(label = "") {
  const raw = String(label || "").trim();
  if (!raw) return { title: "Documents", scope: "" };
  const parts = raw.split(/\s+—\s+|\s+-\s+/);
  if (parts.length >= 2) {
    return { title: parts[0].trim(), scope: parts.slice(1).join(" — ").trim() };
  }
  return { title: raw, scope: "" };
}

export default function FileList({ data }) {
  const files = data?.data?.files || [];
  const notice = data?.data?.expired_notice;
  const total = Number(data?.data?.total_count || data?.value || files.length || 0);
  const { title, scope } = splitLabel(data?.label);

  if (!files.length && !notice) return null;

  return (
    <div className="ooa-file-list">
      <div className="ooa-file-list__header">
        <span className="ooa-file-list__header-icon" aria-hidden="true">
          📎
        </span>
        <div className="ooa-file-list__header-copy">
          <div className="ooa-file-list__title">{title}</div>
          <div className="ooa-file-list__subtitle">
            {total} {total === 1 ? "file" : "files"}
            {scope ? ` · ${scope}` : ""}
          </div>
        </div>
      </div>

      {notice ? <div className="ooa-file-list__notice">{notice}</div> : null}

      <ul className="ooa-file-list__items">
        {files.map((file) => {
          const href = resolveDownloadUrl(file);
          const icon = mimeIcon(file.mimetype);
          const meta = [formatBytes(file.size_bytes), file.uploaded_at, file.source]
            .filter(Boolean)
            .join(" · ");
          return (
            <li
              key={file.download_token || `${file.name}-${file.odoo_attachment_id}`}
              className="ooa-file-list__item"
            >
              <span
                className={`ooa-file-list__icon ooa-file-list__icon--${icon.toLowerCase()}`}
                aria-hidden="true"
              >
                {icon}
              </span>
              <div className="ooa-file-list__meta">
                {href ? (
                  <a className="ooa-file-list__name ooa-file-list__name--link" href={href} download={file.name}>
                    {file.name}
                  </a>
                ) : (
                  <div className="ooa-file-list__name">{file.name}</div>
                )}
                {meta ? <div className="ooa-file-list__sub">{meta}</div> : null}
              </div>
              {href ? (
                <a className="ooa-glass-button ooa-file-list__download-btn" href={href} download={file.name}>
                  Download
                </a>
              ) : (
                <span className="ooa-glass-button ooa-file-list__download-btn ooa-file-list__download-btn--disabled">
                  Unavailable
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
