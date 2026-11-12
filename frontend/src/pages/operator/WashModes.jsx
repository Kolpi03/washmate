import { useState } from 'react'
import { Droplets, Loader2, Pencil, Plus, Timer } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useGet } from '../../hooks/useApi'
import { Badge, Field, Modal, PageHeader, Spinner, Table, useToast } from '../../components/ui'
import { inr } from '../../utils/format'

const BLANK = { name: '', description: '', duration_minutes: 45, water_litres: 50, price: 30, is_active: true }

export default function WashModes() {
  const toast = useToast()
  const { data, loading, reload } = useGet('/wash-modes', { params: { all: 1 } })
  const [form, setForm] = useState(null)
  const [busy, setBusy] = useState(false)
  if (loading) return <Spinner />

  const save = async (e) => {
    e.preventDefault(); setBusy(true)
    const body = { ...form, duration_minutes: Number(form.duration_minutes), water_litres: Number(form.water_litres), price: Number(form.price) }
    try {
      form.id ? await api.patch(`/wash-modes/${form.id}`, body) : await api.post('/wash-modes', body)
      toast.success(form.id ? 'Wash mode updated' : 'Wash mode created'); setForm(null); reload()
    } catch (err) { toast.error(errMsg(err)) } finally { setBusy(false) }
  }
  const toggle = async (m) => {
    try { await api.patch(`/wash-modes/${m.id}`, { is_active: !m.is_active }); toast.success(`${m.name} ${m.is_active ? 'deactivated' : 'activated'}`); reload() }
    catch (e) { toast.error(errMsg(e)) }
  }
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <>
      <PageHeader title="Wash Modes" subtitle="Prices, durations and water estimates are yours to set. Existing bookings keep the values they were booked with."
        actions={<button className="btn-primary" onClick={() => setForm({ ...BLANK })}><Plus className="h-4 w-4" />Add wash mode</button>} />
      <p className="mb-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">The starting values are <b>illustrative</b>, not your actual hostel prices. Update them to match reality.</p>
      <Table head={['Mode', 'Description', 'Duration', 'Water (est.)', 'Price', 'Status', '']}>
        {data.wash_modes.map((m) => (
          <tr key={m.id} className="hover:bg-slate-50/70">
            <td className="td font-semibold">{m.name}</td><td className="td max-w-xs text-slate-500">{m.description}</td>
            <td className="td whitespace-nowrap"><Timer className="mr-1 inline h-3.5 w-3.5 text-slate-400" />{m.duration_minutes} min</td>
            <td className="td whitespace-nowrap"><Droplets className="mr-1 inline h-3.5 w-3.5 text-slate-400" />{m.water_litres} L</td>
            <td className="td font-semibold">{inr(m.price)}</td>
            <td className="td"><Badge status={m.is_active ? 'AVAILABLE' : 'INACTIVE'}>{m.is_active ? 'Active' : 'Inactive'}</Badge></td>
            <td className="td whitespace-nowrap"><div className="flex gap-1.5"><button className="btn-secondary btn-sm" onClick={() => setForm({ ...m })}><Pencil className="h-3.5 w-3.5" />Edit</button><button className="btn-ghost btn-sm" onClick={() => toggle(m)}>{m.is_active ? 'Deactivate' : 'Activate'}</button></div></td>
          </tr>))}
      </Table>
      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? 'Edit wash mode' : 'New wash mode'}>
        {form && <form onSubmit={save} className="space-y-4">
          <Field label="Name"><input className="input" required maxLength={60} value={form.name} onChange={set('name')} /></Field>
          <Field label="Description"><textarea className="input" rows={2} maxLength={400} value={form.description} onChange={set('description')} /></Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Minutes"><input className="input" type="number" min={5} required value={form.duration_minutes} onChange={set('duration_minutes')} /></Field>
            <Field label="Water (L)"><input className="input" type="number" min={0} required value={form.water_litres} onChange={set('water_litres')} /></Field>
            <Field label="Price (₹)"><input className="input" type="number" min={0} step="0.5" required value={form.price} onChange={set('price')} /></Field>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active (visible to students)</label>
          <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save wash mode</button>
        </form>}
      </Modal>
    </>
  )
}
