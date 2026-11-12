import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarCheck, Clock, Droplets, IndianRupee, Loader2, Timer } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useGet, useServerToday } from '../../hooks/useApi'
import SlotPicker from '../../components/SlotPicker'
import { PageHeader, Spinner, useToast } from '../../components/ui'
import { dLabel, inr, t12 } from '../../utils/format'

export default function BookWash() {
  const nav = useNavigate()
  const toast = useToast()
  const today = useServerToday()
  const modes = useGet('/wash-modes')
  const settings = useGet('/settings')
  const [mode, setMode] = useState(null)
  const [pick, setPick] = useState({ date: '', start: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  if (modes.loading || !today || settings.loading) return <Spinner />
  const list = modes.data?.wash_modes || []
  const s = settings.data?.settings || {}
  const date = pick.date || today

  const endTime = () => {
    if (!pick.start || !mode) return ''
    const [h, m] = pick.start.split(':').map(Number)
    const t = h * 60 + m + mode.duration_minutes
    return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
  }

  const submit = async () => {
    setBusy(true); setErr('')
    try {
      const { data } = await api.post('/bookings', { wash_mode_id: mode.id, booking_date: date, start_time: pick.start })
      toast.success(`Slot reserved for ${s.reservation_hold_minutes} minutes. Complete payment to confirm.`)
      nav(`/student/payment/${data.booking.id}`)
    } catch (e) { setErr(errMsg(e)); toast.error(errMsg(e)) } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Book a Wash" subtitle="Choose a mode, then pick a fixed appointment. You pay in advance and the operator confirms." />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <section className="card p-5">
            <h2 className="mb-3 font-semibold"><span className="mr-2 rounded-full bg-brand-600 px-2 py-0.5 text-xs text-white">1</span>Washing mode</h2>
            {list.length === 0 ? <p className="text-sm text-slate-500">No washing modes are active right now.</p> : (
              <div className="grid gap-3 sm:grid-cols-2">
                {list.map((m) => (
                  <button key={m.id} onClick={() => { setMode(m); setPick({ date, start: '' }) }} aria-pressed={mode?.id === m.id}
                    className={`rounded-2xl border p-4 text-left transition ${mode?.id === m.id ? 'border-brand-600 bg-brand-50 ring-2 ring-brand-200' : 'border-slate-200 hover:border-brand-400'}`}>
                    <div className="flex items-start justify-between"><p className="font-semibold">{m.name}</p><p className="font-bold text-brand-700">{inr(m.price)}</p></div>
                    <p className="mt-1 min-h-[2.5rem] text-sm text-slate-500">{m.description}</p>
                    <div className="mt-3 flex gap-4 text-xs text-slate-600">
                      <span className="flex items-center gap-1"><Timer className="h-3.5 w-3.5" />{m.duration_minutes} min</span>
                      <span className="flex items-center gap-1"><Droplets className="h-3.5 w-3.5" />≈{m.water_litres} L water</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>
          <section className={`card p-5 ${mode ? '' : 'opacity-50'}`}>
            <h2 className="mb-3 font-semibold"><span className="mr-2 rounded-full bg-brand-600 px-2 py-0.5 text-xs text-white">2</span>Date & appointment time</h2>
            {mode ? (
              <SlotPicker today={today} days={Number(s.max_advance_days || 7)} modeId={mode.id} value={{ date, start: pick.start }} onChange={setPick} />
            ) : <p className="text-sm text-slate-500">Select a washing mode first.</p>}
          </section>
        </div>
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="card space-y-4 p-5">
            <h2 className="font-semibold">Review booking</h2>
            {!mode || !pick.start ? <p className="text-sm text-slate-500">Choose a mode and time to see your summary.</p> : (
              <dl className="space-y-3 text-sm">
                <Row icon={CalendarCheck} k="Date" v={dLabel(date, { weekday: 'long', day: 'numeric', month: 'long' })} />
                <Row icon={Clock} k="Time" v={`${t12(pick.start)} – ${t12(endTime())}`} />
                <Row icon={Droplets} k="Mode" v={`${mode.name} · ≈${mode.water_litres} L`} />
                <Row icon={Timer} k="Duration" v={`${mode.duration_minutes} minutes`} />
                <div className="flex items-center justify-between rounded-xl bg-brand-50 px-3 py-3"><span className="flex items-center gap-2 font-medium text-brand-800"><IndianRupee className="h-4 w-4" />Total</span><span className="text-xl font-bold text-brand-800">{inr(mode.price)}</span></div>
              </dl>
            )}
            {err && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{err}</p>}
            <button className="btn-primary w-full" disabled={!mode || !pick.start || busy} onClick={submit}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />} Reserve & continue to payment
            </button>
            <p className="text-xs text-slate-400">Your slot is held for {s.reservation_hold_minutes} minutes. Please arrive on time; a {s.grace_period_minutes}-minute grace period applies. Bring your own bucket.</p>
          </div>
        </aside>
      </div>
    </>
  )
}

const Row = ({ icon: Icon, k, v }) => (
  <div className="flex items-start gap-3"><Icon className="mt-0.5 h-4 w-4 text-slate-400" /><div><dt className="text-xs text-slate-400">{k}</dt><dd className="font-medium">{v}</dd></div></div>
)
