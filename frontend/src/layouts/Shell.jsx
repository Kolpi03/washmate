import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Bell, CalendarCheck, CalendarClock, CreditCard, LayoutDashboard, ListChecks, LogOut, Menu, Settings, SlidersHorizontal,
  User, WashingMachine, BarChart3, X, Droplets, Repeat,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useGet } from '../hooks/useApi'
import { useToast } from '../components/ui'

const STUDENT_NAV = [
  ['/student', 'Dashboard', LayoutDashboard, true],
  ['/student/book', 'Book a Wash', CalendarClock],
  ['/student/bookings', 'My Bookings', ListChecks],
  ['/student/notifications', 'Notifications', Bell],
  ['/student/profile', 'Profile', User],
]
const OPERATOR_NAV = [
  ['/operator', 'Overview', LayoutDashboard, true],
  ['/operator/appointments', 'Appointments', CalendarCheck],
  ['/operator/payments', 'Payments', CreditCard],
  ['/operator/machines', 'Machines', WashingMachine],
  ['/operator/modes', 'Wash Modes', Droplets],
  ['/operator/reschedules', 'Rescheduling', Repeat],
  ['/operator/reports', 'Reports', BarChart3],
  ['/operator/notifications', 'Notifications', Bell],
  ['/operator/settings', 'Settings', Settings],
]

export default function Shell({ role }) {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const isOp = role === 'OPERATOR'
  const items = isOp ? OPERATOR_NAV : STUDENT_NAV
  const notes = useGet('/notifications', { poll: 30000 })
  const unread = notes.data?.unread ?? 0
  const seen = useRef(new Set())

  // Browser notifications for new reminders (only if the user granted permission; app works without it)
  useEffect(() => {
    for (const n of notes.data?.notifications || []) {
      if (n.is_read || seen.current.has(n.id)) continue
      seen.current.add(n.id)
      if (!isOp && n.notification_type === 'REMINDER' && 'Notification' in window && Notification.permission === 'granted') {
        try { new Notification(n.title, { body: n.message }) } catch { /* ignore */ }
      }
    }
  }, [notes.data, isOp])

  const doLogout = async () => {
    await logout()
    toast.info('You have been logged out')
    nav(isOp ? '/operator/login' : '/login')
  }

  const side = (
    <div className={`flex h-full flex-col ${isOp ? 'bg-slate-900 text-slate-300' : 'bg-white text-slate-600'}`}>
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="rounded-xl bg-brand-600 p-2 text-white"><WashingMachine className="h-5 w-5" /></div>
        <div>
          <p className={`text-lg font-bold leading-none ${isOp ? 'text-white' : 'text-slate-900'}`}>WashMate</p>
          <p className="mt-1 text-[11px] font-medium uppercase tracking-wider text-slate-400">{isOp ? 'Operator console' : 'Student portal'}</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-2" aria-label="Main">
        {items.map(([to, label, Icon, end]) => (
          <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}
            className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
              isActive ? (isOp ? 'bg-brand-600 text-white' : 'bg-brand-50 text-brand-700') : (isOp ? 'hover:bg-slate-800 hover:text-white' : 'hover:bg-slate-50 hover:text-slate-900')}`}>
            <Icon className="h-[18px] w-[18px]" />
            <span className="flex-1">{label}</span>
            {label === 'Notifications' && unread > 0 && <span className="rounded-full bg-red-500 px-1.5 text-[11px] font-bold text-white">{unread}</span>}
          </NavLink>
        ))}
      </nav>
      <div className={`m-3 rounded-xl p-3 ${isOp ? 'bg-slate-800' : 'bg-slate-50'}`}>
        <p className={`truncate text-sm font-semibold ${isOp ? 'text-white' : 'text-slate-900'}`}>{user?.name}</p>
        <p className="truncate text-xs text-slate-400">{user?.email}</p>
        <button onClick={doLogout} className={`mt-3 flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${isOp ? 'bg-slate-700 text-white hover:bg-slate-600' : 'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100'}`}>
          <LogOut className="h-4 w-4" /> Log out
        </button>
      </div>
    </div>
  )

  return (
    <div className={`min-h-screen ${isOp ? 'bg-slate-100' : 'bg-gradient-to-br from-brand-50 via-slate-50 to-white'}`}>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 lg:block">{side}</aside>
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <button className="btn-ghost btn-sm" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
        <span className="font-bold">WashMate</span>
        <NavLink to={isOp ? '/operator/notifications' : '/student/notifications'} className="relative p-2" aria-label="Notifications">
          <Bell className="h-5 w-5" />{unread > 0 && <span className="absolute right-0.5 top-0.5 h-2.5 w-2.5 rounded-full bg-red-500" />}
        </NavLink>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 shadow-xl">
            <button className="absolute right-2 top-2 z-10 rounded-lg p-2 text-slate-400" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
            {side}
          </div>
        </div>
      )}
      <main className="px-4 py-6 sm:px-8 lg:ml-64 lg:py-8">
        <div className="mx-auto max-w-6xl">
          <Outlet context={{ notes }} />
        </div>
      </main>
    </div>
  )
}

export { SlidersHorizontal }
