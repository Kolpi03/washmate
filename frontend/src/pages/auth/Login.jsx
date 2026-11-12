import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, ShieldCheck, WashingMachine } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { errMsg } from '../../services/api'
import { Field, useToast } from '../../components/ui'

export default function Login({ portal }) {
  const isOp = portal === 'OPERATOR'
  const { login } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const u = await login(email, password, portal)
      toast.success(`Welcome back, ${u.name.split(' ')[0]}!`)
      nav(u.role === 'OPERATOR' ? '/operator' : '/student')
    } catch (err) {
      setError(errMsg(err))
    } finally { setBusy(false) }
  }

  return (
    <div className={`grid min-h-screen place-items-center px-4 ${isOp ? 'bg-slate-900' : 'bg-gradient-to-br from-brand-50 to-white'}`}>
      <div className="w-full max-w-md">
        <Link to="/" className="mb-6 flex items-center justify-center gap-2.5">
          <div className="rounded-xl bg-brand-600 p-2 text-white"><WashingMachine className="h-6 w-6" /></div>
          <span className={`text-2xl font-bold ${isOp ? 'text-white' : 'text-slate-900'}`}>WashMate</span>
        </Link>
        <form onSubmit={submit} className="card space-y-4 p-6 sm:p-8">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold">{isOp && <ShieldCheck className="h-5 w-5 text-brand-600" />}{isOp ? 'Operator sign in' : 'Student sign in'}</h1>
            <p className="mt-1 text-sm text-slate-500">{isOp ? 'Restricted to the hostel laundry operator.' : 'Use your email or roll number.'}</p>
          </div>
          {error && <div role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
          <Field label={isOp ? 'Email' : 'Email or roll number'}>
            <input className="input" name="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password">
            <input className="input" type="password" name="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />} Sign in</button>
          <p className="text-center text-sm text-slate-500">
            {isOp ? <Link className="font-semibold text-brand-600" to="/login">Student login</Link> : <>New here? <Link className="font-semibold text-brand-600" to="/register">Create an account</Link> · <Link className="font-semibold text-slate-600" to="/operator/login">Operator</Link></>}
          </p>
        </form>
      </div>
    </div>
  )
}
