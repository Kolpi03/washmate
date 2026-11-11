import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CalendarCheck, CheckCircle2, CircleDollarSign, CreditCard, Hourglass, PlayCircle, UserX, WashingMachine, Wrench, CalendarDays } from 'lucide-react'
import { useGet } from '../../hooks/useApi'
import OperatorBookingModal from '../../components/OperatorBookingModal'
import { Badge, Empty, PageHeader, Spinner, StatCard } from '../../components/ui'
import { inr, t12 } from '../../utils/format'

export default function Overview() {
  const { data, loading, reload } = useGet('/reports/overview', { poll: 15000 })
  const [open, setOpen] = useState(null)
  if (loading) return <Spinner />
  const o = data.overview
  return (
    <>
      <PageHeader title="Overview" subtitle={`Live figures for ${o.date}`} actions={<Link to="/operator/payments" className="btn-primary"><CreditCard className="h-4 w-4" />Verify payments{o.pending_verification ? ` (${o.pending_verification})` : ''}</Link>} />
      {o.at_risk_count > 0 && (
        <Link to="/operator/machines" className="mb-5 flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-800">
          <AlertTriangle className="h-5 w-5" /><p className="text-sm"><b>{o.at_risk_count} booking(s)</b> no longer fit the available machines. Review them and propose rescheduling — nothing is cancelled automatically.</p>
        </Link>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={CalendarDays} label="Bookings today" value={o.total_today} />
        <StatCard icon={CalendarCheck} label="Confirmed appointments" value={o.confirmed} />
        <StatCard icon={Hourglass} tone="amber" label="Pending verification" value={o.pending_verification} />
        <StatCard icon={PlayCircle} tone="brand" label="Currently washing" value={o.washing} />
        <StatCard icon={CheckCircle2} tone="green" label="Completed washes" value={o.completed} />
        <StatCard icon={CircleDollarSign} tone="green" label="Verified revenue today" value={inr(o.revenue_today)} />
        <StatCard icon={UserX} tone="red" label="No-shows" value={o.no_shows} />
        <StatCard icon={WashingMachine} tone="green" label="Available machines" value={o.machines.available} hint={`${o.machines.occupied} occupied`} />
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <StatCard icon={WashingMachine} tone="brand" label="Occupied machines" value={o.machines.occupied} />
        <StatCard icon={Wrench} tone="red" label="Under maintenance" value={o.machines.maintenance} />
        <StatCard icon={WashingMachine} tone="slate" label="Inactive machines" value={o.machines.inactive} />
      </div>
      <section className="card mt-6 p-5">
        <h2 className="mb-3 font-semibold">Upcoming appointments</h2>
        {o.upcoming.length === 0 ? <Empty icon={CalendarCheck} title="No upcoming appointments today" hint="Confirmed bookings will appear here." /> : (
          <ul className="divide-y divide-slate-100">{o.upcoming.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div><p className="text-sm font-semibold">{t12(b.start_time)} · {b.student.name} <span className="font-mono text-xs text-slate-400">{b.display_ref}</span></p><p className="text-xs text-slate-500">{b.wash_mode} · {b.machine_number ? `Machine ${b.machine_number}` : 'machine not assigned'}</p></div>
              <div className="flex items-center gap-2"><Badge status={b.status} /><button className="btn-secondary btn-sm" onClick={() => setOpen(b.id)}>Manage</button></div>
            </li>))}</ul>
        )}
      </section>
      <OperatorBookingModal bookingId={open} onClose={() => setOpen(null)} onChanged={reload} />
    </>
  )
}
