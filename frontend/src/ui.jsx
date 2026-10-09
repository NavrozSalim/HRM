import { createContext, useContext, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Inbox, X } from "lucide-react";

const ToastContext = createContext(null);
export function useToast() { return useContext(ToastContext); }

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = (message, tone = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((items) => [...items, { id, message, tone }]);
    setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 4200);
  };
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-wrap" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast ${toast.tone === "bad" ? "bad" : ""}`}>
            {toast.tone === "bad" ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

const ROLE_NAMES = { super_admin: "Super user", management: "Management", employee: "Employee" };

export const humanize = (value) => {
  if (value === null || value === undefined || value === "") return "—";
  if (ROLE_NAMES[value]) return ROLE_NAMES[value];
  const text = String(value).replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

export function Field({ label, error, hint, children, className = "" }) {
  return <label className={`field ${className}`}><span>{label}</span>{children}{hint && !error && <small>{hint}</small>}{error && <em>{error}</em>}</label>;
}

export function Modal({ title, children, onClose }) {
  useEffect(() => {
    const onKey = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} type="button" aria-label="Close"><X size={18} /></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function ConfirmDialog({ title, body, confirmLabel = "Confirm", danger, onConfirm, onClose }) {
  return (
    <Modal title={title} onClose={onClose}>
      <p className="muted">{body}</p>
      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={onClose} type="button">Cancel</button>
        <button className={`btn ${danger ? "btn-danger" : "btn-primary"}`} onClick={onConfirm} type="button">{confirmLabel}</button>
      </div>
    </Modal>
  );
}

export function Badge({ value }) {
  return <span className={`badge ${value || ""}`}>{humanize(value)}</span>;
}

export function Tabs({ items, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {items.map((item) => {
        const key = typeof item === "string" ? item : item.value;
        const label = typeof item === "string" ? humanize(item) : item.label;
        return <button key={key} type="button" role="tab" aria-selected={value === key} className={`tab ${value === key ? "active" : ""}`} onClick={() => onChange(key)}>{label}</button>;
      })}
    </div>
  );
}

export function Switch({ checked, onChange, label, description, disabled }) {
  return (
    <label className={`switch-row ${disabled ? "disabled" : ""}`}>
      <span className="switch-text"><strong>{label}</strong>{description && <small>{description}</small>}</span>
      <span className="switch">
        <input type="checkbox" checked={!!checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
        <span className="switch-track" />
      </span>
    </label>
  );
}

export function Avatar({ name, src, size = 36 }) {
  const initials = (name || "?").split(" ").filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  if (src) return <img className="avatar" src={src} alt="" style={{ width: size, height: size }} />;
  return <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.38 }}>{initials}</span>;
}

export function KeyValue({ items }) {
  return (
    <dl className="kv">
      {items.filter(Boolean).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value === null || value === undefined || value === "" ? "—" : value}</dd></div>)}
    </dl>
  );
}

export function Empty({ title, body, action }) {
  return <div className="empty"><Inbox size={28} /><strong>{title}</strong>{body && <p className="muted">{body}</p>}{action}</div>;
}

export function Spinner({ label = "Loading…" }) {
  return <div className="loading"><span className="spinner" />{label}</div>;
}

export function Pager({ page, count, pageSize = 25, onPage }) {
  const pages = Math.max(1, Math.ceil((count || 0) / pageSize));
  return (
    <div className="pager">
      <span className="muted">{count || 0} records</span>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn btn-ghost btn-sm" type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span className="muted">Page {page} of {pages}</span>
        <button className="btn btn-ghost btn-sm" type="button" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}

export const maskAccount = (value) => (value && value.length > 4 ? `•••• ${value.slice(-4)}` : value);

export const money = (value, currency = "USD") => {
  if (value === null || value === undefined || value === "") return "—";
  const amount = Number(value);
  if (Number.isNaN(amount)) return value;
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(amount);
};
