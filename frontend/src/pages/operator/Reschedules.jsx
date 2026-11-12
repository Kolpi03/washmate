import { useState } from 'react'
import { ArrowRight, Check, Repeat, Search, X } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useGet } from '../../hooks/useApi'
import { Badge, ConfirmDialog, Empty, PageHeader, Spinner, Table, Tabs, useToast } from '../../components/ui'
import { dLabel, t12 } from '../../utils/format'

export default function Reschedules() {
  const toast = useToast()
  const [tab, setTab] = useState('PENDING')
  const { data, loading, reload } = useGet('/reschedule', { params: tab === 'ALL' ? {} : { status: tab }, poll: 15000 })
  const [avail, setAvail] = useState({})
  const [dlg, setDlg] = useState(null) // {r, action}

  const check = async (r) => {
    try {
      const { data: a } = await api.get('/machines/availability', { params: { date: r.requested_date, duration: r.duration_minutes } })
      const s = a.slots.find((x) => x.start_time === r.requested_start_time)
      setAvail({ ...avail, [r.id]: s ? (s.available ? `${s.remaining} machine(s) free` : 'Fully booked now') : 'Slot no longer bookable' })
    } catch (e) { setAvail({ ...avail, [r.id]: errMsg(e) }) }
  }
  const review = async (note) => {
    try {
      await api.patch(`/reschedule/${dlg.r.id}`, { action: dlg.action, note })
      toast.success(dlg.action === 'approve' ? 'Reschedule approved – booking updated' : 'Request rejected'); setDlg(null); reload()
    } catch (e) { toast.error(errMsg(e)); setDlg(null); reload() }
  }
  const rows = data?.requests || []

  return (
    <>
      <PageHeader title="Rescheduling" subtitle="Students request a new time; you approve or reject. Capacity is re-checked at the moment of approval." />
      <Tabs value={tab} onChange={setTab} tabs={[['PENDING', 'Pending'], ['APPROVED', 'Approved'], ['REJECTED', 'Rejected'], ['ALL', 'All']]} />
      {loading ? <Spinner /> : (
        <Table head={['Student', 'Booking', 'Current → Requested', 'Reason', 'Status', 'Availability', '']}
          empty={rows.length === 0 && <Empty icon={Repeat} title="No rescheduling requests" hint="Requests from students will show up here." />}>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="td"><p className="font-medium">{r.student_name}</p><p className="text-xs text-slate-400">{r.roll_number}</p></td>
              <td className="td"><span className="font-mono font-semibold">{r.booking_ref}</span><p className="text-xs text-slate-400">{r.wash_mode}</p></td>
              <td className="td whitespace-nowrap">{dLabel(r.original_date)} {t12(r.original_start_time)} <ArrowRight className="mx-1 inline h-3.5 w-3.5 text-slate-400" /> <b>{dLabel(r.requested_date)} {t12(r.requested_start_time)}</b></td>
              <td className="td max-w-[200px] text-slate-500">{r.reason || '—'}{r.review_note && <p className="text-xs text-slate-400">Operator: {r.review_note}</p>}</td>
              <td className="td"><Badge status={r.status} /></td>
              <td className="td text-xs">{r.status === 'PENDING' ? (avail[r.id] || <button className="btn-secondary btn-sm" onClick={() => check(r)}><Search className="h-3.5 w-3.5" />Check</button>) : '—'}</td>
              <td className="td">{r.status === 'PENDING' && <div className="flex gap-1.5">
                <button className="btn-success btn-sm" onClick={() => setDlg({ r, action: 'approve' })}><Check className="h-3.5 w-3.5" />Approve</button>
                <button className="btn-danger btn-sm" onClick={() => setDlg({ r, action: 'reject' })}><X className="h-3.5 w-3.5" />Reject</button></div>}</td>
            </tr>))}
        </Table>
      )}
      <ConfirmDialog open={!!dlg} danger={dlg?.action === 'reject'} title={dlg?.action === 'approve' ? 'Approve rescheduling?' : 'Reject rescheduling?'}
        confirmText={dlg?.action === 'approve' ? 'Approve' : 'Reject'} askReason reasonLabel="Note to student" reasonRequired={dlg?.action === 'reject'}
        message={dlg && `${dlg.r.student_name}: ${dLabel(dlg.r.original_date)} ${t12(dlg.r.original_start_time)} → ${dLabel(dlg.r.requested_date)} ${t12(dlg.r.requested_start_time)}. The original time is kept in the booking history.`}
        onClose={() => setDlg(null)} onConfirm={review} />
    </>
  )
}
