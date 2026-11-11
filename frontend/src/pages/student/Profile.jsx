import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import api, { errMsg } from '../../services/api'
import { useAuth } from '../../context/AuthContext'
import { Field, PageHeader, useToast } from '../../components/ui'

export default function Profile() {
  const { user, setUser } = useAuth()
  const toast = useToast()
  const [f, setF] = useState({ name: user.name, roll_number: user.roll_number || '', email: user.email, hostel: user.hostel || '' })
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => {
    e.preventDefault(); setBusy(true)
    try { const { data } = await api.patch('/auth/me', f); setUser(data.user); toast.success('Profile updated') }
    catch (err) { toast.error(errMsg(err)) } finally { setBusy(false) }
  }
  return (
    <>
      <PageHeader title="Profile" subtitle="Keep your details up to date so the operator can find your booking." />
      <form onSubmit={save} className="card max-w-xl space-y-4 p-6">
        <Field label="Full name"><input className="input" required value={f.name} onChange={set('name')} /></Field>
        <Field label="Roll number"><input className="input" required value={f.roll_number} onChange={set('roll_number')} /></Field>
        <Field label="Email"><input className="input" type="email" required value={f.email} onChange={set('email')} /></Field>
        <Field label="Hostel / room"><input className="input" required value={f.hostel} onChange={set('hostel')} /></Field>
        <button className="btn-primary" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save changes</button>
      </form>
    </>
  )
}
