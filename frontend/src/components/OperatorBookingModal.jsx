import { useState } from 'react'
import { Ban, Check, CheckCircle2, Footprints, Play, UserX, WashingMachine, X } from 'lucide-react'
import api, { errMsg } from '../services/api'
import { useGet } from '../hooks/useApi'
import { Badge, ConfirmDialog, Modal, ProgressBar, useToast } from './ui'
import { dLabel, dtLabel, inr, t12 } from '../utils/format'

/** Everything an operator can do to one booking. */
export default function OperatorBookingModal({ bookingId, onClose, onChanged }) {
  const toast = useToast()
  const { data, reload } = useGet(bookingId ? `/bookings/${bookingId}` : '/health', { enabled: !!bookingId, poll: 10000 })
  const machines = useGet('/machines', { enabled: !!bookingId })
  const [machineId, setMachineId] = useState('')
  const [dlg, setDlg] = useState(null) // 'reject' | 'cancel'
  const [refund, setRefund] = useState(false)
  const b = bookingId ? data?.booking : null

  const run = async (fn, ok) => {
    try { await fn(); toast.success(ok); reload(); onChanged?.() } catch (e) { toast.error(errMsg(e)) }
  }
  const free = (machines.data?.machines || []).filter((m) => m.status === 'AVAILABLE')
  const mid = machineId || b?.machine_id || ''
  const p = (path, body) => api.patch(path, body || {})

  return (
    <>
      <Modal open={!!bookingId} onClose={onClose} title={b ? `Booking ${b.display_ref}` : 'Booking'} wide>
        {!b ? <p className="py-8 text-center text-sm text-slate-500">Loading…</p> : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2"><Badge status={b.status} /><Badge status={b.payment_status}>Payment {b.payment_status.toLowerCase()}</Badge>{b.machine_number && <Badge status="OCCUPIED">Machine {b.machine_number}</Badge>}</div>
            <div className="grid gap-4 sm:grid-cols-2">
              <dl className="space-y-1.5 rounded-xl bg-slate-50 p-4 text-sm">
                <dt className="label">Student</dt>
                <dd className="font-semibold">{b.student.name}</dd>
                <dd className="text-slate-500">Roll {b.student.roll_number} · {b.student.hostel}</dd>
                <dd className="text-slate-500">{b.student.email}</dd>
              </dl>
              <dl className="space-y-1.5 rounded-xl bg-slate-50 p-4 text-sm">
                <dt className="label">Appointment</dt>
                <dd className="font-semibold">{dLabel(b.booking_date)} · {t12(b.start_time)} – {t12(b.end_time)}</dd>
                <dd className="text-slate-500">{b.wash_mode} · {b.duration_minutes} min · ≈{b.water_litres} L · {inr(b.price)}</dd>
                <dd className="text-slate-500">UPI ref: <span className="font-mono">{b.transaction_reference || '—'}</span></dd>
                {b.arrival_time && <dd className="text-slate-500">Arrived {dtLabel(b.arrival_time)}</dd>}
              </dl>
            </div>
            {b.status === 'WASHING' && <div><p className="mb-1 text-sm font-medium">Progress {b.progress ?? 0}%</p><ProgressBar value={b.progress ?? 0} /></div>}
            {b.cancel_reason && <p className="rounded-xl bg-slate-50 p-3 text-sm">Cancel note: {b.cancel_reason}</p>}

            {['CONFIRMED', 'ARRIVED'].includes(b.status) && (
              <div className="flex flex-wrap items-end gap-2 rounded-xl border border-slate-100 p-3">
                <div className="min-w-[180px] flex-1"><span className="label">Machine</span>
                  <select className="input" value={mid} onChange={(e) => setMachineId(e.target.value)} aria-label="Select machine">
                    <option value="">Select a machine…</option>
                    {(machines.data?.machines || []).filter((m) => ['AVAILABLE', 'OCCUPIED'].includes(m.status)).map((m) => <option key={m.id} value={m.id}>{m.machine_number} ({m.status.toLowerCase()})</option>)}
                  </select></div>
                <button className="btn-secondary" disabled={!mid} onClick={() => run(() => p(`/bookings/${b.id}/assign`, { machine_id: Number(mid) }), 'Machine assigned')}><WashingMachine className="h-4 w-4" />Assign</button>
                {b.status === 'ARRIVED' && <button className="btn-primary" disabled={!mid && !free.length} onClick={() => run(() => p(`/bookings/${b.id}/start`, { machine_id: Number(mid) || undefined }), 'Wash started')}><Play className="h-4 w-4" />Start washing</button>}
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {b.status === 'PAYMENT_SUBMITTED' && <>
                <button className="btn-success" onClick={() => run(() => p(`/payments/${b.payment_id}/verify`), 'Payment verified – booking confirmed')}><Check className="h-4 w-4" />Verify payment</button>
                <button className="btn-danger" onClick={() => setDlg('reject')}><X className="h-4 w-4" />Reject payment</button></>}
              {b.status === 'CONFIRMED' && <>
                <button className="btn-primary" onClick={() => run(() => p(`/bookings/${b.id}/arrival`), 'Marked as arrived')}><Footprints className="h-4 w-4" />Mark arrived</button>
                <button className="btn-secondary" onClick={() => run(() => p(`/bookings/${b.id}/no-show`), 'Marked as no-show')}><UserX className="h-4 w-4" />Mark no-show</button></>}
              {b.status === 'WASHING' && <button className="btn-success" onClick={() => run(() => p(`/bookings/${b.id}/complete`), 'Wash completed')}><CheckCircle2 className="h-4 w-4" />Complete washing</button>}
              {['RESERVED', 'PAYMENT_SUBMITTED', 'CONFIRMED', 'ARRIVED', 'WASHING'].includes(b.status) && <button className="btn-secondary !text-red-600" onClick={() => setDlg('cancel')}><Ban className="h-4 w-4" />Cancel with reason</button>}
              {b.status === 'CONFIRMED' && <button className="btn-ghost" onClick={() => run(() => api.post(`/bookings/${b.id}/propose-reschedule`, { message: 'The operator asks you to pick a new time.' }), 'Student asked to reschedule')}>Ask to reschedule</button>}
            </div>
            <p className="text-xs text-slate-400">No-show can only be marked after the grace period following the start time. Every action is recorded in the audit log.</p>
          </div>
        )}
      </Modal>
      <ConfirmDialog open={dlg === 'reject'} danger title="Reject this payment?" confirmText="Reject payment" askReason reasonRequired reasonLabel="Reason shown to student"
        message="The transaction was not found in the UPI records. The reserved slot will be released." onClose={() => setDlg(null)}
        onConfirm={async (reason) => { await run(() => p(`/payments/${b.payment_id}/reject`, { reason }), 'Payment rejected'); setDlg(null) }} />
      <ConfirmDialog open={dlg === 'cancel'} danger title="Cancel this booking?" confirmText="Cancel booking" askReason reasonRequired reasonLabel="Cancellation reason (sent to student)"
        message="The student will be notified. Cancelling never happens automatically."
        extra={b?.payment_status === 'VERIFIED' && <label className="flex items-center gap-2"><input type="checkbox" checked={refund} onChange={(e) => setRefund(e.target.checked)} /> I have refunded the student – mark payment as refunded</label>}
        onClose={() => setDlg(null)}
        onConfirm={async (reason) => { await run(() => p(`/bookings/${b.id}/cancel`, { reason, refund }), 'Booking cancelled'); setDlg(null); setRefund(false) }} />
    </>
  )
}
