import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useGet } from '../../hooks/useApi'
import { Field, PageHeader, Spinner, useToast } from '../../components/ui'

const GROUPS = [
  ['Payment', [['upi_id', 'UPI ID', 'text', 'Students pay to this ID'], ['upi_qr_code_url', 'UPI QR code image URL', 'text', 'Optional – public link to your QR image']]],
  ['Operating hours', [['open_time', 'Opening time', 'time'], ['close_time', 'Closing time', 'time'], ['slot_interval_minutes', 'Appointment grid (minutes)', 'number'], ['max_advance_days', 'Bookable days ahead', 'number']]],
  ['Policies', [['turnaround_buffer_minutes', 'Turnaround buffer between washes (min)', 'number'], ['grace_period_minutes', 'Late-arrival grace period (min)', 'number'], ['reservation_hold_minutes', 'Unpaid reservation hold (min)', 'number'], ['reminder_minutes_before', 'Reminder lead time (min)', 'number'], ['student_cancel_cutoff_minutes', 'Student cancellation cutoff (min before)', 'number']]],
  ['General', [['hostel_name', 'Hostel name', 'text']]],
]

export default function SettingsPage() {
  const toast = useToast()
  const { data, loading } = useGet('/settings')
  const [f, setF] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (data) setF(data.settings) }, [data])
  if (loading || !f) return <Spinner />

  const save = async (e) => {
    e.preventDefault(); setBusy(true)
    try { const { data: d } = await api.patch('/settings', f); setF(d.settings); toast.success('Settings saved') }
    catch (err) { toast.error(errMsg(err)) } finally { setBusy(false) }
  }
  return (
    <>
      <PageHeader title="Settings" subtitle="Operating hours, policies and the UPI details shown to students." />
      <form onSubmit={save} className="space-y-6">
        {GROUPS.map(([title, fields]) => (
          <section key={title} className="card p-5">
            <h2 className="mb-4 font-semibold">{title}</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {fields.map(([k, label, type, hint]) => (
                <Field key={k} label={label} hint={hint}><input className="input" type={type} min={type === 'number' ? 0 : undefined} value={f[k] ?? ''} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>
              ))}
            </div>
          </section>
        ))}
        <button className="btn-primary" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save settings</button>
      </form>
    </>
  )
}
