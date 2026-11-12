import { useMemo, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight, Eye, LayoutList, Rows3 } from 'lucide-react'
import { useGet, useServerToday } from '../../hooks/useApi'
import OperatorBookingModal from '../../components/OperatorBookingModal'
import { Badge, Empty, PageHeader, Spinner, Table, Tabs } from '../../components/ui'
import { addDays, dLabel, inr, t12 } from '../../utils/format'

const TABS = [
  ['ALL', 'All', null],
  ['PAYMENT_SUBMITTED', 'Pending verification', 'PAYMENT_SUBMITTED'],
  ['CONFIRMED', 'Confirmed', 'CONFIRMED,ARRIVED'],
  ['WASHING', 'Washing', 'WASHING'],
  ['COMPLETED', 'Completed', 'COMPLETED'],
  ['CANCELLED', 'Cancelled', 'CANCELLED'],
  ['NO_SHOW', 'No-show', 'NO_SHOW'],
]

export default function Appointments() {
  const today = useServerToday()
  const [view, setView] = useState('table')
  const [date, setDate] = useState('')
  const [tab, setTab] = useState('ALL')
  const [open, setOpen] = useState(null)
  const [month, setMonth] = useState('')
  const cur = date || today
  const mon = month || (today || '').slice(0, 7)

  const params = useMemo(() => {
    if (view === 'calendar') {
      const [yy, mm] = mon.split('-').map(Number)
      return { from: `${mon}-01`, to: `${mon}-${String(new Date(yy, mm, 0).getDate()).padStart(2, '0')}` }
    }
    const p = {}
    if (view === 'schedule' || date) p.date = cur
    if (view === 'table' && TABS.find((t) => t[0] === tab)[2]) p.status = TABS.find((t) => t[0] === tab)[2]
    return p
  }, [view, date, cur, tab, mon])
  const { data, loading, reload } = useGet('/bookings', { params, enabled: !!today, poll: 15000 })
  if (!today) return <Spinner />
  const rows = (data?.bookings || []).filter((b) => view !== 'table' || !['EXPIRED', 'RESERVED'].includes(b.status) || tab === 'ALL')

  return (
    <>
      <PageHeader title="Appointments" subtitle="Calendar, daily schedule and every booking’s lifecycle."
        actions={<div className="flex rounded-xl bg-white p-1 shadow-card">
          {[['table', LayoutList, 'Table'], ['schedule', Rows3, 'Daily schedule'], ['calendar', CalendarDays, 'Calendar']].map(([k, I, l]) => (
            <button key={k} onClick={() => setView(k)} className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium ${view === k ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}><I className="h-4 w-4" />{l}</button>))}
        </div>} />

      {view !== 'calendar' && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button className="btn-secondary btn-sm" onClick={() => setDate(addDays(cur, -1))} aria-label="Previous day"><ChevronLeft className="h-4 w-4" /></button>
          <input type="date" className="input !w-auto" value={date || (view === 'schedule' ? cur : '')} onChange={(e) => setDate(e.target.value)} aria-label="Filter by date" />
          <button className="btn-secondary btn-sm" onClick={() => setDate(addDays(cur, 1))} aria-label="Next day"><ChevronRight className="h-4 w-4" /></button>
          <button className="btn-ghost btn-sm" onClick={() => setDate(today)}>Today</button>
          {view === 'table' && date && <button className="btn-ghost btn-sm" onClick={() => setDate('')}>All dates</button>}
        </div>
      )}
      {view === 'table' && <Tabs value={tab} onChange={setTab} tabs={TABS.map(([k, l]) => [k, l])} />}

      {loading ? <Spinner /> : view === 'calendar' ? (
        <Calendar month={mon} setMonth={setMonth} bookings={rows} today={today} onPick={(d) => { setDate(d); setView('schedule') }} />
      ) : view === 'schedule' ? (
        <Schedule rows={rows} onOpen={setOpen} />
      ) : (
        <Table head={['Ref', 'Student', 'Date', 'Time', 'Mode', 'Amount', 'Payment', 'Status', 'Machine', '']}
          empty={rows.length === 0 && <Empty icon={CalendarDays} title="No appointments match" hint="Try another filter or date." />}>
          {rows.map((b) => (
            <tr key={b.id} className="hover:bg-slate-50/70">
              <td className="td font-mono font-semibold">{b.display_ref}</td>
              <td className="td"><p className="font-medium">{b.student.name}</p><p className="text-xs text-slate-400">{b.student.roll_number}</p></td>
              <td className="td whitespace-nowrap">{dLabel(b.booking_date)}</td>
              <td className="td whitespace-nowrap">{t12(b.start_time)} – {t12(b.end_time)}</td>
              <td className="td">{b.wash_mode}</td><td className="td">{inr(b.price)}</td>
              <td className="td"><Badge status={b.payment_status} /></td><td className="td"><Badge status={b.status} /></td>
              <td className="td">{b.machine_number || '—'}</td>
              <td className="td"><button className="btn-secondary btn-sm" onClick={() => setOpen(b.id)}><Eye className="h-3.5 w-3.5" />Manage</button></td>
            </tr>
          ))}
        </Table>
      )}
      <OperatorBookingModal bookingId={open} onClose={() => setOpen(null)} onChanged={reload} />
    </>
  )
}

function Schedule({ rows, onOpen }) {
  const live = rows.filter((b) => !['EXPIRED', 'REJECTED'].includes(b.status)).sort((a, b) => a.start_time.localeCompare(b.start_time))
  if (!live.length) return <div className="card"><Empty icon={Rows3} title="Nothing scheduled" hint="No bookings on this day." /></div>
  const hours = [...new Set(live.map((b) => b.start_time.slice(0, 2)))]
  return (
    <div className="card divide-y divide-slate-100">
      {hours.map((h) => (
        <div key={h} className="flex gap-4 p-4">
          <div className="w-16 shrink-0 pt-1 text-sm font-bold text-slate-400">{t12(`${h}:00`)}</div>
          <div className="grid flex-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {live.filter((b) => b.start_time.startsWith(h)).map((b) => (
              <button key={b.id} onClick={() => onOpen(b.id)} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-left hover:border-brand-300 hover:bg-white">
                <div className="flex items-center justify-between"><span className="text-sm font-semibold">{t12(b.start_time)} · {b.student.name}</span><Badge status={b.status} /></div>
                <p className="mt-1 text-xs text-slate-500">{b.wash_mode} · {b.duration_minutes} min · {b.machine_number ? `Machine ${b.machine_number}` : 'no machine yet'}</p>
              </button>))}
          </div>
        </div>))}
    </div>
  )
}

function Calendar({ month, setMonth, bookings, today, onPick }) {
  const [y, m] = month.split('-').map(Number)
  const first = new Date(y, m - 1, 1)
  const days = new Date(y, m, 0).getDate()
  const lead = (first.getDay() + 6) % 7
  const counts = {}
  bookings.filter((b) => !['EXPIRED', 'REJECTED', 'CANCELLED'].includes(b.status)).forEach((b) => { counts[b.booking_date] = (counts[b.booking_date] || 0) + 1 })
  const shift = (n) => { const d = new Date(y, m - 1 + n, 1); setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`) }
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <button className="btn-secondary btn-sm" onClick={() => shift(-1)} aria-label="Previous month"><ChevronLeft className="h-4 w-4" /></button>
        <h2 className="font-semibold">{first.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}</h2>
        <button className="btn-secondary btn-sm" onClick={() => shift(1)} aria-label="Next month"><ChevronRight className="h-4 w-4" /></button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold uppercase text-slate-400">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => <div key={d} className="py-1">{d}</div>)}</div>
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: lead }).map((_, i) => <div key={`e${i}`} />)}
        {Array.from({ length: days }, (_, i) => {
          const iso = `${month}-${String(i + 1).padStart(2, '0')}`
          const c = counts[iso] || 0
          return (
            <button key={iso} onClick={() => onPick(iso)} className={`aspect-square rounded-xl border p-1.5 text-left text-sm transition hover:border-brand-400 ${iso === today ? 'border-brand-600 bg-brand-50' : 'border-slate-100'}`}>
              <span className="font-semibold">{i + 1}</span>
              {c > 0 && <span className="mt-1 block rounded-md bg-brand-600 px-1 text-center text-[11px] font-bold text-white">{c} wash{c > 1 ? 'es' : ''}</span>}
            </button>)
        })}
      </div>
    </div>
  )
}
