import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CalendarCheck, CircleDollarSign, Download, Droplets, Gauge, Trophy, UserX, XCircle } from 'lucide-react'
import { downloadCsv, errMsg } from '../../services/api'
import { useGet, useServerToday } from '../../hooks/useApi'
import { Empty, PageHeader, Spinner, StatCard, Tabs, useToast } from '../../components/ui'
import { inr } from '../../utils/format'

const C = ['#2563eb', '#059669', '#d97706', '#7c3aed', '#64748b', '#0891b2']

export default function Reports() {
  const toast = useToast()
  const today = useServerToday()
  const [kind, setKind] = useState('daily')
  const [date, setDate] = useState('')
  const d = date || today
  const params = kind === 'daily' ? { date: d } : kind === 'weekly' ? { end: d } : { month: (d || '').slice(0, 7) }
  const { data, loading } = useGet(`/reports/${kind}`, { params, enabled: !!today })
  if (!today) return <Spinner />
  const r = data?.report

  const exportCsv = async () => {
    try { await downloadCsv(`/reports/${kind}`, params, `washmate-${kind}-${d}.csv`); toast.success('CSV downloaded') } catch (e) { toast.error(errMsg(e)) }
  }

  return (
    <>
      <PageHeader title="Reports & analytics" subtitle="Figures come straight from the booking database. Water values are estimates from wash-mode settings, not meter readings."
        actions={<button className="btn-secondary" onClick={exportCsv}><Download className="h-4 w-4" />Export CSV</button>} />
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <Tabs value={kind} onChange={setKind} tabs={[['daily', 'Daily'], ['weekly', 'Weekly (7 days to date)'], ['monthly', 'Monthly']]} />
        <input type="date" className="input mb-4 !w-auto" value={d} onChange={(e) => setDate(e.target.value)} aria-label="Report date" />
      </div>
      {loading || !r ? <Spinner /> : (
        <>
          <p className="mb-4 text-sm text-slate-500">{r.start === r.end ? r.start : `${r.start} → ${r.end}`}</p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={CalendarCheck} label="Bookings" value={r.total_bookings} />
            <StatCard icon={CircleDollarSign} tone="green" label="Verified revenue" value={inr(r.revenue)} />
            <StatCard icon={Trophy} tone="amber" label="Most popular mode" value={r.popular_mode || '—'} />
            <StatCard icon={Droplets} label="Est. water used" value={`${r.estimated_water_litres} L`} hint="completed washes, estimated" />
            <StatCard icon={CalendarCheck} tone="green" label="Completed washes" value={r.completed} />
            <StatCard icon={XCircle} tone="slate" label="Cancelled" value={r.cancelled} />
            <StatCard icon={UserX} tone="red" label="No-shows" value={r.no_shows} />
            <StatCard icon={Gauge} label="Machine utilisation" value={`${r.machine_utilization_pct}%`} hint="wash minutes ÷ working capacity" />
          </div>
          {r.total_bookings === 0 ? <div className="card mt-6"><Empty icon={CalendarCheck} title="No bookings in this period" hint="Pick another date or range." /></div> : (
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <Chart title="Appointment demand by hour">
                <BarChart data={r.demand_by_hour}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="hour" fontSize={12} /><YAxis allowDecimals={false} fontSize={12} /><Tooltip /><Bar dataKey="count" name="Bookings" fill={C[0]} radius={[6, 6, 0, 0]} /></BarChart>
              </Chart>
              <Chart title="Wash mode popularity">
                <PieChart><Pie data={r.mode_counts} dataKey="count" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2} label={(e) => e.name}>{r.mode_counts.map((_, i) => <Cell key={i} fill={C[i % C.length]} />)}</Pie><Tooltip /></PieChart>
              </Chart>
              {r.by_day.length > 1 && <Chart title="Bookings & revenue per day" wide>
                <LineChart data={r.by_day}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" fontSize={12} tickFormatter={(x) => x.slice(5)} /><YAxis yAxisId="l" allowDecimals={false} fontSize={12} /><YAxis yAxisId="r" orientation="right" fontSize={12} /><Tooltip /><Legend />
                  <Line yAxisId="l" type="monotone" dataKey="bookings" name="Bookings" stroke={C[0]} strokeWidth={2.5} dot={false} /><Line yAxisId="r" type="monotone" dataKey="revenue" name="Revenue (₹)" stroke={C[1]} strokeWidth={2.5} dot={false} /></LineChart>
              </Chart>}
              {r.machine_minutes.length > 0 && <Chart title="Machine utilisation (wash minutes)">
                <BarChart data={r.machine_minutes}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="machine" fontSize={12} /><YAxis fontSize={12} /><Tooltip /><Bar dataKey="minutes" name="Minutes washed" fill={C[1]} radius={[6, 6, 0, 0]} /></BarChart>
              </Chart>}
            </div>
          )}
        </>
      )}
    </>
  )
}

const Chart = ({ title, children, wide }) => (
  <section className={`card p-5 ${wide ? 'lg:col-span-2' : ''}`}>
    <h2 className="mb-3 font-semibold">{title}</h2>
    <div className="h-64"><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>
  </section>
)
