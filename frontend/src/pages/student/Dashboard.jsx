import { Link, useOutletContext } from 'react-router-dom'
import { Bell, CalendarCheck, CalendarClock, CheckCircle2, Hourglass, ListChecks } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useGet } from '../../hooks/useApi'
import { Badge, Empty, PageHeader, Spinner, StatCard } from '../../components/ui'
import { dLabel, dtLabel, inr, t12 } from '../../utils/format'

export default function Dashboard() {
  const { user } = useAuth()
  const { notes } = useOutletContext()
  const { data, loading } = useGet('/bookings/my', { poll: 15000 })
  if (loading) return <Spinner />
  const all = data?.bookings || []
  const real = all.filter((b) => !['EXPIRED', 'REJECTED'].includes(b.status))
  const completed = all.filter((b) => b.status === 'COMPLETED').length
  const pending = all.filter((b) => ['RESERVED', 'PAYMENT_SUBMITTED'].includes(b.status)).length
  const upcoming = all.filter((b) => ['CONFIRMED', 'ARRIVED', 'WASHING'].includes(b.status))
    .sort((a, b) => (a.booking_date + a.start_time).localeCompare(b.booking_date + b.start_time))[0]
  const recent = all.slice(0, 5)
  const nlist = (notes.data?.notifications || []).slice(0, 4)

  return (
    <>
      <PageHeader title={`Welcome, ${user.name.split(' ')[0]} 👋`} subtitle="Here’s what’s happening with your laundry."
        actions={<Link to="/student/book" className="btn-primary"><CalendarClock className="h-4 w-4" />Book a wash</Link>} />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatCard icon={ListChecks} label="Total bookings" value={real.length} />
        <StatCard icon={CheckCircle2} tone="green" label="Completed washes" value={completed} />
        <StatCard icon={Hourglass} tone="amber" label="Pending bookings" value={pending} hint="awaiting payment / verification" />
      </div>
      <div className="mb-6 card overflow-hidden">
        {upcoming ? (
          <div className="flex flex-wrap items-center gap-5 bg-gradient-to-r from-brand-700 to-brand-500 p-6 text-white">
            <div className="rounded-2xl bg-white/15 p-4"><CalendarCheck className="h-8 w-8" /></div>
            <div className="flex-1">
              <p className="text-sm text-blue-100">Your next appointment</p>
              <p className="text-2xl font-bold text-white">{dLabel(upcoming.booking_date, { weekday: 'long', day: 'numeric', month: 'long' })} · {t12(upcoming.start_time)}</p>
              <p className="text-sm text-blue-100">{upcoming.wash_mode} · {upcoming.display_ref} · {inr(upcoming.price)}</p>
            </div>
            <Badge status={upcoming.status} className="!bg-white !text-brand-700" />
          </div>
        ) : <Empty icon={CalendarClock} title="No upcoming appointment" hint="Pick a mode and a time — it takes under a minute." action={<Link to="/student/book" className="btn-primary">Book a wash</Link>} />}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Recent bookings</h2><Link className="text-sm font-medium text-brand-600" to="/student/bookings">View all</Link></div>
          {recent.length === 0 ? <p className="py-6 text-center text-sm text-slate-500">Nothing yet.</p> : (
            <ul className="divide-y divide-slate-100">{recent.map((b) => (
              <li key={b.id} className="flex items-center justify-between gap-3 py-3">
                <div><p className="text-sm font-semibold">{b.wash_mode} <span className="font-mono text-xs text-slate-400">{b.display_ref}</span></p><p className="text-xs text-slate-500">{dLabel(b.booking_date)} · {t12(b.start_time)}</p></div>
                <Badge status={b.status} />
              </li>))}</ul>
          )}
        </section>
        <section className="card p-5">
          <div className="mb-3 flex items-center justify-between"><h2 className="flex items-center gap-2 font-semibold"><Bell className="h-4 w-4" />Notifications</h2><Link className="text-sm font-medium text-brand-600" to="/student/notifications">View all</Link></div>
          {nlist.length === 0 ? <p className="py-6 text-center text-sm text-slate-500">You’re all caught up.</p> : (
            <ul className="divide-y divide-slate-100">{nlist.map((n) => (
              <li key={n.id} className="py-3"><p className="flex items-center gap-2 text-sm font-semibold">{!n.is_read && <span className="h-2 w-2 rounded-full bg-brand-600" />}{n.title}</p><p className="text-xs text-slate-500">{n.message}</p><p className="mt-0.5 text-[11px] text-slate-400">{dtLabel(n.sent_at)}</p></li>))}</ul>
          )}
        </section>
      </div>
    </>
  )
}
