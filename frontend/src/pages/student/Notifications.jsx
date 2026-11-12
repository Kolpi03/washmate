import { useOutletContext } from 'react-router-dom'
import { Bell, BellRing, CheckCheck } from 'lucide-react'
import api from '../../services/api'
import { Empty, PageHeader, Spinner, useToast } from '../../components/ui'
import { dtLabel } from '../../utils/format'
import { useState } from 'react'

export default function Notifications() {
  const { notes } = useOutletContext()
  const toast = useToast()
  const [perm, setPerm] = useState(typeof Notification !== 'undefined' ? Notification.permission : 'unsupported')
  if (notes.loading) return <Spinner />
  const list = notes.data?.notifications || []

  const mark = async (n) => { if (!n.is_read) { await api.patch(`/notifications/${n.id}/read`); notes.reload() } }
  const markAll = async () => { await api.patch('/notifications/read-all'); notes.reload(); toast.success('All marked as read') }
  const enable = async () => {
    const p = await Notification.requestPermission(); setPerm(p)
    p === 'granted' ? toast.success('Browser reminders enabled') : toast.info('Browser reminders stay off – in-app reminders still work')
  }

  return (
    <>
      <PageHeader title="Notifications" subtitle="Confirmations, reminders and updates about your bookings."
        actions={<>
          {perm === 'default' && <button className="btn-secondary" onClick={enable}><BellRing className="h-4 w-4" />Enable browser alerts</button>}
          <button className="btn-secondary" onClick={markAll} disabled={!notes.data?.unread}><CheckCheck className="h-4 w-4" />Mark all read</button>
        </>} />
      <div className="card divide-y divide-slate-100">
        {list.length === 0 && <Empty icon={Bell} title="No notifications yet" hint="You’ll see booking confirmations and appointment reminders here." />}
        {list.map((n) => (
          <button key={n.id} onClick={() => mark(n)} className={`flex w-full items-start gap-3 px-5 py-4 text-left transition hover:bg-slate-50 ${n.is_read ? '' : 'bg-brand-50/50'}`}>
            <div className={`mt-0.5 rounded-xl p-2 ${n.notification_type === 'REMINDER' ? 'bg-amber-50 text-amber-600' : 'bg-brand-50 text-brand-600'}`}>{n.notification_type === 'REMINDER' ? <BellRing className="h-4 w-4" /> : <Bell className="h-4 w-4" />}</div>
            <div className="flex-1"><p className="text-sm font-semibold">{n.title} {!n.is_read && <span className="ml-1 rounded-full bg-brand-600 px-1.5 text-[10px] font-bold text-white">NEW</span>}</p><p className="text-sm text-slate-600">{n.message}</p><p className="mt-1 text-xs text-slate-400">{dtLabel(n.sent_at)}{n.notification_type === 'REMINDER' && n.scheduled_at ? ` · due ${dtLabel(n.scheduled_at)}` : ''}</p></div>
          </button>
        ))}
      </div>
    </>
  )
}
