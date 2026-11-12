export const inr = (n) => `₹${Number(n ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

export function t12(hhmm) {
  if (!hhmm) return '—'
  const [h, m] = hhmm.split(':').map(Number)
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`
}

export function dLabel(iso, opts = { weekday: 'short', day: 'numeric', month: 'short' }) {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-IN', opts)
}

export function dtLabel(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
}

export function addDays(iso, n) {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(y, m - 1, d + n)
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
}

export const STATUS_STYLE = {
  RESERVED: 'bg-amber-50 text-amber-700 ring-amber-200',
  PAYMENT_SUBMITTED: 'bg-amber-50 text-amber-700 ring-amber-200',
  PENDING: 'bg-amber-50 text-amber-700 ring-amber-200',
  CONFIRMED: 'bg-blue-50 text-blue-700 ring-blue-200',
  ARRIVED: 'bg-sky-50 text-sky-700 ring-sky-200',
  WASHING: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  OCCUPIED: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  COMPLETED: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  VERIFIED: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  APPROVED: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  AVAILABLE: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  CANCELLED: 'bg-slate-100 text-slate-600 ring-slate-200',
  EXPIRED: 'bg-slate-100 text-slate-600 ring-slate-200',
  INACTIVE: 'bg-slate-100 text-slate-600 ring-slate-200',
  REFUNDED: 'bg-slate-100 text-slate-600 ring-slate-200',
  NO_SHOW: 'bg-red-50 text-red-700 ring-red-200',
  REJECTED: 'bg-red-50 text-red-700 ring-red-200',
  MAINTENANCE: 'bg-red-50 text-red-700 ring-red-200',
}

export const statusText = (s) =>
  ({ PAYMENT_SUBMITTED: 'Awaiting verification', RESERVED: 'Awaiting payment', NO_SHOW: 'No-show' })[s] ||
  (s ? s.charAt(0) + s.slice(1).toLowerCase() : '')
