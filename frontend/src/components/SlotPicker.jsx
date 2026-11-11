import { useEffect, useState } from 'react'
import { Clock, Users } from 'lucide-react'
import api, { errMsg } from '../services/api'
import { addDays, dLabel, t12 } from '../utils/format'
import { Spinner } from './ui'

/** Date chips + available appointment grid. value = { date, start } */
export default function SlotPicker({ today, days = 7, modeId, duration, value, onChange }) {
  const [slots, setSlots] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!value.date || (!modeId && !duration)) return
    let live = true
    setSlots(null); setErr('')
    api.get('/machines/availability', { params: { date: value.date, wash_mode_id: modeId, duration } })
      .then((r) => live && setSlots(r.data))
      .catch((e) => live && setErr(errMsg(e)))
    return () => { live = false }
  }, [value.date, modeId, duration])

  const dates = today ? Array.from({ length: days + 1 }, (_, i) => addDays(today, i)) : []
  return (
    <div className="space-y-5">
      <div>
        <span className="label">Date</span>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {dates.map((d) => (
            <button key={d} type="button" onClick={() => onChange({ date: d, start: '' })}
              className={`min-w-[78px] rounded-xl border px-3 py-2 text-center text-sm transition ${value.date === d ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-200 bg-white hover:border-brand-300'}`}>
              <span className="block text-[11px] uppercase opacity-80">{dLabel(d, { weekday: 'short' })}</span>
              <span className="font-semibold">{dLabel(d, { day: 'numeric', month: 'short' })}</span>
            </button>
          ))}
        </div>
      </div>
      <div>
        <span className="label">Available appointments</span>
        {err && <p className="text-sm text-red-600">{err}</p>}
        {!slots && !err && <Spinner label="Checking machine capacity…" />}
        {slots && slots.slots.length === 0 && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">No appointments left on this day. Try another date.</p>}
        {slots && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {slots.slots.map((s) => (
              <button key={s.start_time} type="button" disabled={!s.available} onClick={() => onChange({ ...value, start: s.start_time })}
                aria-label={`${t12(s.start_time)} ${s.available ? 'available' : 'full'}`}
                className={`rounded-xl border px-3 py-2.5 text-left transition ${value.start === s.start_time ? 'border-brand-600 bg-brand-50 ring-2 ring-brand-200' : s.available ? 'border-slate-200 bg-white hover:border-brand-400' : 'cursor-not-allowed border-slate-100 bg-slate-50 text-slate-300'}`}>
                <span className="flex items-center gap-1.5 text-sm font-semibold"><Clock className="h-3.5 w-3.5" />{t12(s.start_time)}</span>
                <span className="mt-0.5 flex items-center gap-1 text-xs"><Users className="h-3 w-3" />{s.available ? `${s.remaining} machine${s.remaining > 1 ? 's' : ''} free` : 'Fully booked'}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
