import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Loader2, ShieldCheck, WashingMachine } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { Field } from '../../components/ui'

export default function SetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (password !== confirm) return setError('Passwords do not match')
    setBusy(true); setError('')
    try {
      await api.post('/auth/set-password', { token, password })
      setDone(true)
    } catch (err) { setError(errMsg(err)) } finally { setBusy(false) }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-slate-900 px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <div className="rounded-xl bg-brand-600 p-2 text-white"><WashingMachine className="h-6 w-6" /></div>
          <span className="text-2xl font-bold text-white">WashMate</span>
        </div>
        <form onSubmit={submit} className="card space-y-4 p-6 sm:p-8">
          <h1 className="flex items-center gap-2 text-xl font-bold"><ShieldCheck className="h-5 w-5 text-brand-600" />Set your operator password</h1>
          {done ? (
            <p className="text-sm text-slate-600">Password saved. <Link className="font-semibold text-brand-600" to="/operator/login">Sign in</Link></p>
          ) : (<>
            {error && <div role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <Field label="New password (min 8 characters)">
              <input className="input" type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <Field label="Confirm password">
              <input className="input" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </Field>
            <button className="btn-primary w-full" disabled={busy || !token}>{busy && <Loader2 className="h-4 w-4 animate-spin" />} Save password</button>
          </>)}
        </form>
      </div>
    </div>
  )
}
