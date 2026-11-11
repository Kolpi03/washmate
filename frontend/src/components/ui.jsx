import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from 'lucide-react'
import { STATUS_STYLE, statusText } from '../utils/format'

/* ---------- toasts ---------- */
const ToastCtx = createContext(null)
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((message, type = 'success') => {
    const id = Math.random().toString(36).slice(2)
    setItems((l) => [...l, { id, message, type }])
    setTimeout(() => setItems((l) => l.filter((i) => i.id !== id)), 4200)
  }, [])
  const api = { success: (m) => push(m, 'success'), error: (m) => push(m, 'error'), info: (m) => push(m, 'info') }
  const icon = { success: <CheckCircle2 className="h-5 w-5 text-emerald-600" />, error: <XCircle className="h-5 w-5 text-red-600" />, info: <Info className="h-5 w-5 text-brand-600" /> }
  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2" role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className="pointer-events-auto flex items-start gap-3 rounded-xl border border-slate-100 bg-white p-3 shadow-lg">
            {icon[i.type]}
            <p className="flex-1 text-sm text-slate-700">{i.message}</p>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

/* ---------- primitives ---------- */
export function Badge({ status, children, className = '' }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${STATUS_STYLE[status] || 'bg-slate-100 text-slate-600 ring-slate-200'} ${className}`}>
      {children || statusText(status)}
    </span>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500" role="status">
      <Loader2 className="h-5 w-5 animate-spin text-brand-600" /> {label}
    </div>
  )
}

export function Empty({ icon: Icon, title, hint, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {Icon && <div className="mb-3 rounded-2xl bg-brand-50 p-3 text-brand-600"><Icon className="h-6 w-6" /></div>}
      <p className="font-semibold text-slate-800">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-sm text-slate-500">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function StatCard({ icon: Icon, label, value, tone = 'brand', hint }) {
  const tones = { brand: 'bg-brand-50 text-brand-600', green: 'bg-emerald-50 text-emerald-600', amber: 'bg-amber-50 text-amber-600', red: 'bg-red-50 text-red-600', slate: 'bg-slate-100 text-slate-600' }
  return (
    <div className="card flex items-center gap-4 p-4">
      <div className={`rounded-xl p-3 ${tones[tone]}`}><Icon className="h-5 w-5" /></div>
      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-slate-500">{label}</p>
        <p className="text-2xl font-bold leading-tight text-slate-900">{value}</p>
        {hint && <p className="truncate text-xs text-slate-400">{hint}</p>}
      </div>
    </div>
  )
}

export function Field({ label, children, hint, error }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  )
}

export function Modal({ open, onClose, title, children, footer, wide }) {
  const ref = useRef()
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    ref.current?.focus()
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}
        className={`card max-h-[92vh] w-full overflow-y-auto rounded-b-none outline-none sm:rounded-2xl ${wide ? 'sm:max-w-2xl' : 'sm:max-w-md'}`}>
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

/** Confirmation dialog with optional reason textbox. */
export function ConfirmDialog({ open, title, message, confirmText = 'Confirm', danger, askReason, reasonLabel = 'Reason', reasonRequired, extra, onConfirm, onClose }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (open) { setReason(''); setBusy(false) } }, [open])
  const go = async () => {
    setBusy(true)
    try { await onConfirm(reason) } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title={title}
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Keep as is</button>
        <button className={danger ? 'btn-danger' : 'btn-primary'} disabled={busy || (askReason && reasonRequired && !reason.trim())} onClick={go}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}{confirmText}
        </button>
      </>}>
      <div className="flex gap-3">
        <AlertTriangle className={`mt-0.5 h-5 w-5 shrink-0 ${danger ? 'text-red-600' : 'text-amber-500'}`} />
        <div className="w-full space-y-3 text-sm text-slate-600">
          <p>{message}</p>
          {askReason && (
            <Field label={reasonLabel}><textarea className="input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={reasonRequired ? 'Required' : 'Optional'} /></Field>
          )}
          {extra}
        </div>
      </div>
    </Modal>
  )
}

export function Table({ head, children, empty }) {
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-100">
          <thead className="bg-slate-50/70"><tr>{head.map((h) => <th key={h} className="th whitespace-nowrap">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-100">{children}</tbody>
        </table>
      </div>
      {empty}
    </div>
  )
}

export function ProgressBar({ value }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${value}%` }} />
    </div>
  )
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1">
      {tabs.map(([k, label, count]) => (
        <button key={k} onClick={() => onChange(k)}
          className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition ${value === k ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
          {label}{count != null && <span className="ml-1.5 rounded-full bg-slate-200/70 px-1.5 text-xs">{count}</span>}
        </button>
      ))}
    </div>
  )
}
