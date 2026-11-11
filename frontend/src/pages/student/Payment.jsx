import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, Clock, Copy, Hourglass, Loader2, QrCode, Smartphone, XCircle } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useGet } from '../../hooks/useApi'
import { Badge, Field, PageHeader, Spinner, useToast } from '../../components/ui'
import { dLabel, inr, t12 } from '../../utils/format'

function Countdown({ to }) {
  const [left, setLeft] = useState(0)
  useEffect(() => {
    const tick = () => setLeft(Math.max(0, Math.floor((new Date(to) - Date.now()) / 1000)))
    tick(); const t = setInterval(tick, 1000); return () => clearInterval(t)
  }, [to])
  return <span className="font-mono font-bold">{String(Math.floor(left / 60)).padStart(2, '0')}:{String(left % 60).padStart(2, '0')}</span>
}

export default function Payment() {
  const { id } = useParams()
  const toast = useToast()
  const bk = useGet(`/bookings/${id}`, { poll: 8000 })
  const st = useGet('/settings')
  const [ref, setRef] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  if (bk.loading || st.loading) return <Spinner />
  if (bk.error) return <div className="card p-8 text-center text-slate-500">{bk.error}. <Link className="text-brand-600" to="/student/bookings">Back to bookings</Link></div>
  const b = bk.data.booking
  const s = st.data.settings
  const upiLink = `upi://pay?pa=${encodeURIComponent(s.upi_id || '')}&pn=WashMate&am=${b.price}&cu=INR&tn=${encodeURIComponent('WashMate ' + b.display_ref)}`

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr('')
    try {
      await api.post('/payments/submit', { booking_id: b.id, transaction_reference: ref })
      toast.success('Reference submitted. The operator will verify your payment.')
      bk.reload()
    } catch (e2) { setErr(errMsg(e2)) } finally { setBusy(false) }
  }
  const copy = () => navigator.clipboard?.writeText(s.upi_id).then(() => toast.success('UPI ID copied'))

  const done = ['CONFIRMED', 'ARRIVED', 'WASHING', 'COMPLETED'].includes(b.status)
  return (
    <>
      <PageHeader title="Payment" subtitle={`Booking ${b.display_ref} · ${b.wash_mode} · ${dLabel(b.booking_date)} at ${t12(b.start_time)}`} actions={<Badge status={b.status} />} />
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card space-y-5 p-6">
          <div className="rounded-2xl bg-gradient-to-br from-brand-700 to-brand-500 p-5 text-white">
            <p className="text-sm text-blue-100">Amount to pay</p>
            <p className="text-4xl font-extrabold text-white">{inr(b.price)}</p>
          </div>
          {s.upi_id ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-xl border border-slate-200 p-3">
                <div><p className="text-xs text-slate-400">Operator UPI ID</p><p className="font-mono text-sm font-semibold" data-testid="upi-id">{s.upi_id}</p></div>
                <button className="btn-secondary btn-sm" onClick={copy}><Copy className="h-3.5 w-3.5" />Copy</button>
              </div>
              {s.upi_qr_code_url
                ? <img src={s.upi_qr_code_url} alt="UPI QR code" className="mx-auto h-48 w-48 rounded-xl border border-slate-200 object-contain p-2" />
                : <div className="flex items-center gap-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-500"><QrCode className="h-4 w-4" />No QR code configured – pay using the UPI ID.</div>}
              <a href={upiLink} className="btn-secondary w-full sm:hidden"><Smartphone className="h-4 w-4" />Open UPI app</a>
            </div>
          ) : <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">The operator has not configured a UPI ID yet. Please contact the operator.</p>}
          <ol className="list-decimal space-y-1.5 pl-5 text-sm text-slate-600">
            <li>Pay exactly <b>{inr(b.price)}</b> to the UPI ID above.</li>
            <li>Copy the <b>UPI transaction reference (UTR)</b> from your payment app.</li>
            <li>Paste it on the right and submit. The operator checks it against the real UPI records.</li>
          </ol>
        </section>

        <section className="card p-6">
          {b.status === 'RESERVED' && (
            <form onSubmit={submit} className="space-y-4">
              <div className="flex items-center gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-800"><Clock className="h-4 w-4" />Slot held for <Countdown to={b.expires_at} /> — then it is released.</div>
              <Field label="UPI transaction reference" hint="6–40 letters or digits, e.g. the 12-digit UTR">
                <input className="input font-mono" required minLength={6} maxLength={40} value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. 412345678901" />
              </Field>
              {err && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{err}</p>}
              <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Submit for verification</button>
              <p className="text-xs text-slate-400">Entering a reference does not confirm your booking – only the operator’s verification does.</p>
            </form>
          )}
          {b.status === 'PAYMENT_SUBMITTED' && (
            <Status icon={Hourglass} tone="amber" title="Waiting for operator verification" text={`Reference ${b.transaction_reference} was submitted. This page updates automatically.`} />
          )}
          {done && (
            <Status icon={CheckCircle2} tone="green" title="Payment verified – booking confirmed" text={`Your reference is ${b.booking_reference}. Please be at the washing area at ${t12(b.start_time)} on ${dLabel(b.booking_date)}.`}
              extra={<Link to="/student/bookings" className="btn-primary mt-4">View my bookings</Link>} />
          )}
          {['REJECTED', 'EXPIRED', 'CANCELLED'].includes(b.status) && (
            <Status icon={XCircle} tone="red" title={b.status === 'EXPIRED' ? 'Reservation expired' : b.status === 'REJECTED' ? 'Payment could not be verified' : 'Booking cancelled'}
              text={b.reject_reason || b.cancel_reason || 'The slot was released. You can book again.'} extra={<Link to="/student/book" className="btn-primary mt-4">Book again</Link>} />
          )}
        </section>
      </div>
    </>
  )
}

function Status({ icon: Icon, tone, title, text, extra }) {
  const c = { amber: 'bg-amber-50 text-amber-600', green: 'bg-emerald-50 text-emerald-600', red: 'bg-red-50 text-red-600' }[tone]
  return (
    <div className="flex h-full flex-col items-center justify-center py-8 text-center" data-testid="payment-status">
      <div className={`mb-4 rounded-full p-4 ${c}`}><Icon className="h-8 w-8" /></div>
      <h2 className="text-lg font-bold">{title}</h2>
      <p className="mt-2 max-w-xs text-sm text-slate-500">{text}</p>
      {extra}
    </div>
  )
}
