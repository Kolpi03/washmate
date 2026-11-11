import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, WashingMachine } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { errMsg } from '../../services/api'
import { Field, useToast } from '../../components/ui'

export default function Register() {
  const { register } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [f, setF] = useState({ name: '', roll_number: '', email: '', hostel: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    if (f.password.length < 8) return setError('Password must be at least 8 characters')
    setBusy(true); setError('')
    try {
      await register(f)
      toast.success('Account created. Welcome to WashMate!')
      nav('/student')
    } catch (err) { setError(errMsg(err)) } finally { setBusy(false) }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-gradient-to-br from-brand-50 to-white px-4 py-8">
      <div className="w-full max-w-lg">
        <Link to="/" className="mb-6 flex items-center justify-center gap-2.5">
          <div className="rounded-xl bg-brand-600 p-2 text-white"><WashingMachine className="h-6 w-6" /></div>
          <span className="text-2xl font-bold">WashMate</span>
        </Link>
        <form onSubmit={submit} className="card space-y-4 p-6 sm:p-8">
          <div><h1 className="text-xl font-bold">Create your student account</h1><p className="mt-1 text-sm text-slate-500">Operator accounts are created by the administrator only.</p></div>
          {error && <div role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name"><input className="input" required value={f.name} onChange={set('name')} autoComplete="name" /></Field>
            <Field label="Roll number"><input className="input" required value={f.roll_number} onChange={set('roll_number')} /></Field>
            <Field label="Email"><input className="input" type="email" required value={f.email} onChange={set('email')} autoComplete="email" /></Field>
            <Field label="Hostel / room"><input className="input" required value={f.hostel} onChange={set('hostel')} /></Field>
          </div>
          <Field label="Password" hint="At least 8 characters"><input className="input" type="password" required minLength={8} value={f.password} onChange={set('password')} autoComplete="new-password" /></Field>
          <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />} Create account</button>
          <p className="text-center text-sm text-slate-500">Already registered? <Link className="font-semibold text-brand-600" to="/login">Sign in</Link></p>
        </form>
      </div>
    </div>
  )
}
