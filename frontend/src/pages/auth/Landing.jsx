import { Link } from 'react-router-dom'
import { ArrowRight, BellRing, CalendarClock, CreditCard, ShieldCheck, WashingMachine } from 'lucide-react'

const steps = [
  [CalendarClock, 'Book', 'Pick a wash mode and a fixed appointment.'],
  [CreditCard, 'Pay', 'Pay in advance by UPI; the operator verifies it.'],
  [BellRing, 'Get reminded', 'A reminder arrives 15 minutes before.'],
  [WashingMachine, 'Arrive & wash', 'Walk in on time with your bucket. Done.'],
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-900 via-brand-700 to-brand-500 text-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <div className="flex items-center gap-2.5">
          <div className="rounded-xl bg-white/15 p-2"><WashingMachine className="h-6 w-6" /></div>
          <span className="text-xl font-bold">WashMate</span>
        </div>
        <Link to="/operator/login" className="flex items-center gap-1.5 rounded-xl bg-white/10 px-3.5 py-2 text-sm font-medium hover:bg-white/20">
          <ShieldCheck className="h-4 w-4" /> Operator login
        </Link>
      </header>
      <main className="mx-auto max-w-6xl px-5 pb-16 pt-10 sm:pt-20">
        <div className="max-w-2xl">
          <p className="mb-4 inline-block rounded-full bg-white/15 px-3 py-1 text-xs font-semibold uppercase tracking-wider">Smart hostel laundry management</p>
          <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-6xl">Book. Pay. Get reminded. Arrive. Wash.</h1>
          <p className="mt-5 text-lg text-blue-100">No more notebooks or guessing which machine is free. Reserve a fixed washing appointment, pay in advance and just show up.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/login" className="btn bg-white text-brand-800 hover:bg-blue-50">Student login <ArrowRight className="h-4 w-4" /></Link>
            <Link to="/register" className="btn border border-white/40 text-white hover:bg-white/10">Create student account</Link>
          </div>
        </div>
        <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(([Icon, t, d], i) => (
            <div key={t} className="rounded-2xl bg-white/10 p-5 backdrop-blur">
              <div className="mb-3 flex items-center gap-2"><span className="grid h-7 w-7 place-items-center rounded-full bg-white text-sm font-bold text-brand-700">{i + 1}</span><Icon className="h-5 w-5" /></div>
              <p className="font-semibold text-white">{t}</p>
              <p className="mt-1 text-sm text-blue-100">{d}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
