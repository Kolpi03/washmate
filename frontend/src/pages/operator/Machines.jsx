import { useState } from 'react'
import { AlertTriangle, Plus, Power, Settings2, Wrench, WashingMachine, CheckCircle2, Loader2 } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useGet } from '../../hooks/useApi'
import { Badge, ConfirmDialog, Field, Modal, PageHeader, Spinner, useToast } from '../../components/ui'
import { dLabel, dtLabel, t12 } from '../../utils/format'

export default function Machines() {
  const toast = useToast()
  const { data, loading, reload } = useGet('/machines', { poll: 15000 })
  const risk = useGet('/bookings/at-risk', { poll: 15000 })
  const [add, setAdd] = useState(false)
  const [edit, setEdit] = useState(null)
  const [maint, setMaint] = useState(null)
  const [num, setNum] = useState('')
  const [busy, setBusy] = useState(false)
  const [acting, setActing] = useState(false)
  if (loading) return <Spinner />
  const ms = data.machines

  const patch = async (m, body, ok) => {
    if (acting) return
    setActing(true)
    try {
      const r = await api.patch(`/machines/${m.id}`, body)
      toast.success(ok || `Machine ${m.machine_number} updated`)
      if (r.data.at_risk_booking_ids?.length) toast.error(`${r.data.at_risk_booking_ids.length} booking(s) may be affected – review below`)
      reload(); risk.reload()
    } catch (e) { toast.error(errMsg(e)) } finally { setActing(false) }
  }
  const create = async (e) => {
    e.preventDefault(); setBusy(true)
    try { await api.post('/machines', { machine_number: num }); toast.success('Machine added'); setAdd(false); setNum(''); reload() }
    catch (err) { toast.error(errMsg(err)) } finally { setBusy(false) }
  }
  const propose = async (b) => {
    try { await api.post(`/bookings/${b.id}/propose-reschedule`, { message: 'A washing machine is out of service, so your slot may no longer be available.' }); toast.success(`${b.student.name} was asked to reschedule`) }
    catch (e) { toast.error(errMsg(e)) }
  }

  return (
    <>
      <PageHeader title="Machines" subtitle={`${data.working} working machine(s). Booking capacity follows this number automatically.`}
        actions={<button className="btn-primary" onClick={() => setAdd(true)}><Plus className="h-4 w-4" />Add machine</button>} />

      {risk.data?.bookings.length > 0 && (
        <section className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-5" aria-label="Affected bookings">
          <h2 className="mb-1 flex items-center gap-2 font-semibold text-red-800"><AlertTriangle className="h-5 w-5" />{risk.data.bookings.length} booking(s) exceed current capacity</h2>
          <p className="mb-3 text-sm text-red-700">Only {risk.data.working_machines} machine(s) are working. These appointments are still confirmed — ask students to move, or restore a machine.</p>
          <ul className="divide-y divide-red-100 rounded-xl bg-white">{risk.data.bookings.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
              <span><b>{b.display_ref}</b> · {b.student.name} · {dLabel(b.booking_date)} {t12(b.start_time)} · {b.wash_mode}</span>
              <button className="btn-secondary btn-sm" onClick={() => propose(b)}>Propose rescheduling</button>
            </li>))}</ul>
        </section>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ms.map((m) => (
          <fieldset key={m.id} disabled={acting} className={`card m-0 min-w-0 p-5 ${['MAINTENANCE', 'INACTIVE'].includes(m.status) ? 'border-red-100 bg-red-50/30' : ''}`} data-testid={`machine-${m.machine_number}`}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3"><div className={`rounded-xl p-2.5 ${m.status === 'AVAILABLE' ? 'bg-emerald-50 text-emerald-600' : m.status === 'OCCUPIED' ? 'bg-indigo-50 text-indigo-600' : 'bg-red-50 text-red-600'}`}><WashingMachine className="h-6 w-6" /></div>
                <div><p className="text-lg font-bold">Machine {m.machine_number}</p><p className="text-xs text-slate-400">{m.assignments_today} appointment(s) today</p></div></div>
              <Badge status={m.status} />
            </div>
            <div className="mt-4 min-h-[44px] text-sm text-slate-600">
              {m.current_booking ? <p>Washing <b>{m.current_booking.student}</b> ({m.current_booking.mode}) until {t12(m.current_booking.ends)}</p>
                : m.status === 'MAINTENANCE' ? <p className="text-red-700">Under maintenance since {dtLabel(m.maintenance_since)}{m.maintenance_note ? ` – ${m.maintenance_note}` : ''}</p>
                : m.status === 'INACTIVE' ? <p>Disabled{m.maintenance_since ? ` since ${dtLabel(m.maintenance_since)}` : ''}</p> : <p>Idle and ready.</p>}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {m.status === 'MAINTENANCE' || m.status === 'INACTIVE'
                ? <button className="btn-success btn-sm" onClick={() => patch(m, { status: 'AVAILABLE' }, `Machine ${m.machine_number} restored`)}><CheckCircle2 className="h-3.5 w-3.5" />Restore</button>
                : <>
                  <button className="btn-secondary btn-sm !text-red-600" onClick={() => setMaint(m)}><Wrench className="h-3.5 w-3.5" />Maintenance</button>
                  <button className="btn-secondary btn-sm" onClick={() => patch(m, { status: 'INACTIVE' })} disabled={!!m.current_booking}><Power className="h-3.5 w-3.5" />Disable</button></>}
              <button className="btn-ghost btn-sm" onClick={() => setEdit({ ...m })}><Settings2 className="h-3.5 w-3.5" />Edit</button>
            </div>
          </fieldset>))}
      </div>

      <Modal open={add} onClose={() => setAdd(false)} title="Add machine">
        <form onSubmit={create} className="space-y-4">
          <Field label="Machine number / label"><input className="input" required autoFocus maxLength={20} value={num} onChange={(e) => setNum(e.target.value)} placeholder="e.g. M7" /></Field>
          <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Add machine</button>
        </form>
      </Modal>
      <Modal open={!!edit} onClose={() => setEdit(null)} title="Edit machine" footer={<><button className="btn-secondary" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary" onClick={async () => { await patch(edit, { machine_number: edit.machine_number, status: edit.status, maintenance_note: edit.maintenance_note || '' }); setEdit(null) }}>Save</button></>}>
        {edit && <div className="space-y-4">
          <Field label="Machine number"><input className="input" value={edit.machine_number} onChange={(e) => setEdit({ ...edit, machine_number: e.target.value })} /></Field>
          <Field label="Status"><select className="input" value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>{['AVAILABLE', 'OCCUPIED', 'MAINTENANCE', 'INACTIVE'].map((s) => <option key={s}>{s}</option>)}</select></Field>
          <Field label="Maintenance information"><textarea className="input" rows={2} value={edit.maintenance_note || ''} onChange={(e) => setEdit({ ...edit, maintenance_note: e.target.value })} placeholder="What is wrong? Technician called?" /></Field>
        </div>}
      </Modal>
      <ConfirmDialog open={!!maint} danger title={`Put machine ${maint?.machine_number} under maintenance?`} confirmText="Mark as under maintenance" askReason reasonLabel="What is wrong? (shown to operators)"
        message="Future booking capacity will drop immediately. Existing confirmed bookings are never cancelled automatically — affected ones will be listed for you to reschedule."
        onClose={() => setMaint(null)} onConfirm={async (note) => { await patch(maint, { status: 'MAINTENANCE', maintenance_note: note }); setMaint(null) }} />
    </>
  )
}
