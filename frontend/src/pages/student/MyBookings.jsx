import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarClock, Eye, Loader2, Repeat, WashingMachine, X } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useGet, useServerToday } from '../../hooks/useApi'
import SlotPicker from '../../components/SlotPicker'
import { Badge, ConfirmDialog, Empty, Field, Modal, PageHeader, ProgressBar, Spinner, Table, Tabs, useToast } from '../../components/ui'
import { dLabel, dtLabel, inr, t12 } from '../../utils/format'

const UPCOMING = ['RESERVED', 'PAYMENT_SUBMITTED', 'CONFIRMED', 'ARRIVED', 'WASHING']

export default function MyBookings() {
  const toast = useToast()
  const today = useServerToday()
  const { data, loading, reload } = useGet('/bookings/my', { poll: 15000 })
  const settings = useGet('/settings')
  const [tab, setTab] = useState('upcoming')
  const [detail, setDetail] = useState(null)
  const [cancel, setCancel] = useState(null)
  const [resched, setResched] = useState(null)

  if (loading || !today) return <Spinner />
  const all = data?.bookings || []
  const rows = all.filter((b) => (tab === 'upcoming' ? UPCOMING.includes(b.status) : !UPCOMING.includes(b.status)))
  const nUp = all.filter((b) => UPCOMING.includes(b.status)).length

  const doCancel = async (reason) => {
    try {
      await api.patch(`/bookings/${cancel.id}/cancel`, { reason })
      toast.success('Booking cancelled'); setCancel(null); setDetail(null); reload()
    } catch (e) { toast.error(errMsg(e)); setCancel(null) }
  }

  return (
    <>
      <PageHeader title="My Bookings" subtitle="Track your appointments, payments and wash progress."
        actions={<Link className="btn-primary" to="/student/book"><CalendarClock className="h-4 w-4" />New booking</Link>} />
      <Tabs value={tab} onChange={setTab} tabs={[['upcoming', 'Upcoming & active', nUp], ['past', 'Previous bookings', all.length - nUp]]} />
      <Table head={['Reference', 'Date', 'Start', 'Ends', 'Mode', 'Amount', 'Payment', 'Status', 'Machine', 'Arrival', '']}
        empty={rows.length === 0 && <Empty icon={WashingMachine} title="No bookings here yet" hint="Book a wash to see it listed here." action={<Link className="btn-primary" to="/student/book">Book a wash</Link>} />}>
        {rows.map((b) => (
          <tr key={b.id} className="hover:bg-slate-50/60">
            <td className="td font-mono font-semibold">{b.display_ref}</td>
            <td className="td whitespace-nowrap">{dLabel(b.booking_date)}</td>
            <td className="td">{t12(b.start_time)}</td><td className="td">{t12(b.end_time)}</td>
            <td className="td">{b.wash_mode}</td><td className="td">{inr(b.price)}</td>
            <td className="td"><Badge status={b.payment_status} /></td>
            <td className="td"><Badge status={b.status} /></td>
            <td className="td">{b.machine_number || '—'}</td>
            <td className="td whitespace-nowrap">{b.arrival_time ? dtLabel(b.arrival_time) : '—'}</td>
            <td className="td"><button className="btn-secondary btn-sm" onClick={() => setDetail(b)}><Eye className="h-3.5 w-3.5" />Details</button></td>
          </tr>
        ))}
      </Table>

      <Modal open={!!detail} onClose={() => setDetail(null)} title={`Booking ${detail?.display_ref || ''}`} wide
        footer={detail && <>
          {detail.status === 'RESERVED' && <Link to={`/student/payment/${detail.id}`} className="btn-primary">Pay now</Link>}
          {detail.status === 'CONFIRMED' && <button className="btn-secondary" onClick={() => setResched(detail)}><Repeat className="h-4 w-4" />Request reschedule</button>}
          {['RESERVED', 'PAYMENT_SUBMITTED', 'CONFIRMED'].includes(detail.status) && <button className="btn-danger" onClick={() => setCancel(detail)}><X className="h-4 w-4" />Cancel booking</button>}
        </>}>
        {detail && <Detail id={detail.id} fallback={detail} />}
      </Modal>

      <ConfirmDialog open={!!cancel} danger title="Cancel this booking?" confirmText="Yes, cancel" askReason reasonLabel="Reason (optional)"
        message={settings.data ? `Cancellation of confirmed bookings closes ${settings.data.settings.student_cancel_cutoff_minutes} minutes before the appointment. If you already paid, contact the operator about your refund.` : ''}
        onConfirm={doCancel} onClose={() => setCancel(null)} />
      <RescheduleModal booking={resched} today={today} days={Number(settings.data?.settings.max_advance_days || 7)}
        onClose={() => setResched(null)} onDone={() => { setResched(null); setDetail(null); reload() }} />
    </>
  )
}

function Detail({ id, fallback }) {
  const { data } = useGet(`/bookings/${id}`, { poll: 10000 })
  const b = data?.booking || fallback
  const Row = ({ k, v }) => <div><dt className="text-xs text-slate-400">{k}</dt><dd className="text-sm font-medium">{v || '—'}</dd></div>
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2"><Badge status={b.status} /><Badge status={b.payment_status}>Payment {b.payment_status.toLowerCase()}</Badge></div>
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Row k="Date" v={dLabel(b.booking_date, { weekday: 'long', day: 'numeric', month: 'long' })} />
        <Row k="Time" v={`${t12(b.start_time)} – ${t12(b.end_time)}`} />
        <Row k="Mode" v={b.wash_mode} /><Row k="Price paid" v={inr(b.price)} />
        <Row k="Est. water" v={`${b.water_litres} L`} /><Row k="Duration" v={`${b.duration_minutes} min`} />
        <Row k="Machine" v={b.machine_number} /><Row k="UPI reference" v={b.transaction_reference} />
        <Row k="Arrived" v={b.arrival_time ? dtLabel(b.arrival_time) : null} />
      </dl>
      {b.status === 'WASHING' && <div><p className="mb-1 text-sm font-medium">Washing progress · {b.progress ?? 0}%</p><ProgressBar value={b.progress ?? 0} /></div>}
      {b.cancel_reason && <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-600">Cancellation note: {b.cancel_reason}</p>}
      {b.reject_reason && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">Payment note: {b.reject_reason}</p>}
      {data?.booking?.reschedules?.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-semibold">Rescheduling history</p>
          <ul className="space-y-2">{data.booking.reschedules.map((r) => (
            <li key={r.id} className="rounded-xl border border-slate-100 p-3 text-sm">
              <div className="flex items-center justify-between"><span>{dLabel(r.original_date)} {t12(r.original_start_time)} → {dLabel(r.requested_date)} {t12(r.requested_start_time)}</span><Badge status={r.status} /></div>
              {r.review_note && <p className="mt-1 text-xs text-slate-500">Operator: {r.review_note}</p>}
            </li>))}</ul>
        </div>
      )}
    </div>
  )
}

function RescheduleModal({ booking, today, days, onClose, onDone }) {
  const toast = useToast()
  const [pick, setPick] = useState({ date: today, start: '' })
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const submit = async () => {
    setBusy(true); setErr('')
    try {
      await api.post('/reschedule', { booking_id: booking.id, requested_date: pick.date, requested_start_time: pick.start, reason })
      toast.success('Request sent to the operator'); onDone()
    } catch (e) { setErr(errMsg(e)) } finally { setBusy(false) }
  }
  return (
    <Modal open={!!booking} onClose={onClose} title="Request a new time" wide
      footer={<><button className="btn-secondary" onClick={onClose}>Close</button>
        <button className="btn-primary" disabled={!pick.start || busy} onClick={submit}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Send request</button></>}>
      {booking && <div className="space-y-4">
        <p className="text-sm text-slate-500">Current: <b>{dLabel(booking.booking_date)} at {t12(booking.start_time)}</b>. The operator reviews every request; your current slot stays valid until approval.</p>
        <SlotPicker today={today} days={days} duration={booking.duration_minutes} modeId={booking.wash_mode_id} value={pick} onChange={setPick} />
        <Field label="Reason"><textarea className="input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. I have a lab session" /></Field>
        {err && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{err}</p>}
      </div>}
    </Modal>
  )
}
