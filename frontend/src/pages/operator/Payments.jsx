import { useState } from 'react'
import { Check, CreditCard, RotateCcw, X } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useGet } from '../../hooks/useApi'
import { Badge, ConfirmDialog, Empty, PageHeader, Spinner, Table, Tabs, useToast } from '../../components/ui'
import { dLabel, dtLabel, inr, t12 } from '../../utils/format'

export default function Payments() {
  const toast = useToast()
  const [tab, setTab] = useState('PENDING')
  const pending = useGet('/payments/pending', { poll: 10000 })
  const all = useGet('/payments', { params: tab === 'PENDING' ? undefined : { status: tab === 'ALL' ? undefined : tab }, enabled: tab !== 'PENDING', poll: 20000 })
  const [rej, setRej] = useState(null)
  const [verify, setVerify] = useState(null)
  const [busy, setBusy] = useState(false)

  const src = tab === 'PENDING' ? pending : all
  const rows = (tab === 'PENDING' ? pending.data?.payments : all.data?.payments) || []
  const reload = () => { pending.reload(); all.reload() }
  const act = async (fn, ok) => {
    if (busy) return
    setBusy(true)
    try { await fn(); toast.success(ok); reload() } catch (e) { toast.error(errMsg(e)) } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Payments" subtitle="Check each UPI reference against your actual UPI/bank records before verifying." />
      <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        A student entering a reference is <b>not proof of payment</b>. Verify only after you see the matching credit in your UPI app or bank statement.
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[['PENDING', 'Awaiting verification', pending.data?.payments.length], ['ALL', 'All'], ['VERIFIED', 'Verified'], ['REJECTED', 'Rejected'], ['REFUNDED', 'Refunded']]} />
      {src.loading ? <Spinner /> : (
        <Table head={['Student', 'Roll', 'Booking', 'UPI reference', 'Amount', 'Method', 'Status', 'Verified', 'Verified by', '']}
          empty={rows.length === 0 && <Empty icon={CreditCard} title="No payments here" hint="Submitted payments will appear in this list." />}>
          {rows.map((p) => (
            <tr key={p.id} className="hover:bg-slate-50/70">
              <td className="td font-medium">{p.student_name}</td><td className="td">{p.roll_number}</td>
              <td className="td"><span className="font-mono font-semibold">{p.booking_ref}</span><p className="text-xs text-slate-400">{dLabel(p.booking_date)} {t12(p.start_time)}</p></td>
              <td className="td font-mono">{p.transaction_reference}</td><td className="td font-semibold">{inr(p.amount)}</td><td className="td">{p.payment_method}</td>
              <td className="td"><Badge status={p.status} /></td><td className="td whitespace-nowrap">{dtLabel(p.verified_at)}</td><td className="td">{p.verified_by || '—'}</td>
              <td className="td whitespace-nowrap">
                {p.status === 'PENDING' && p.booking_status === 'PAYMENT_SUBMITTED' && <div className="flex gap-1.5">
                  <button className="btn-success btn-sm" disabled={busy} onClick={() => setVerify(p)}><Check className="h-3.5 w-3.5" />Verify</button>
                  <button className="btn-danger btn-sm" disabled={busy} onClick={() => setRej(p)}><X className="h-3.5 w-3.5" />Reject</button></div>}
                {p.status === 'VERIFIED' && ['CANCELLED', 'NO_SHOW'].includes(p.booking_status) && <button className="btn-secondary btn-sm" disabled={busy} onClick={() => act(() => api.patch(`/payments/${p.id}/refund`), 'Marked as refunded')}><RotateCcw className="h-3.5 w-3.5" />Mark refunded</button>}
              </td>
            </tr>))}
        </Table>
      )}
      <ConfirmDialog open={!!verify} title="Verify this payment?" confirmText="Yes, payment received"
        message={verify && `Confirm that ${inr(verify.amount)} with reference ${verify.transaction_reference} from ${verify.student_name} is visible in your UPI records. The booking will be confirmed.`}
        onClose={() => setVerify(null)} onConfirm={async () => { await act(() => api.patch(`/payments/${verify.id}/verify`), 'Payment verified – booking confirmed'); setVerify(null) }} />
      <ConfirmDialog open={!!rej} danger title="Reject this payment?" confirmText="Reject payment" askReason reasonRequired reasonLabel="Reason shown to student"
        message="The reserved slot will be released and the student notified." onClose={() => setRej(null)}
        onConfirm={async (reason) => { await act(() => api.patch(`/payments/${rej.id}/reject`, { reason }), 'Payment rejected'); setRej(null) }} />
    </>
  )
}
