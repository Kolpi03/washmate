import { useCallback, useEffect, useRef, useState } from 'react'
import api, { errMsg } from '../services/api'

/** GET helper with loading/error state and optional polling. */
export function useGet(path, { params, poll, enabled = true } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState('')
  const key = JSON.stringify([path, params])
  const alive = useRef(true)

  const load = useCallback(async (silent) => {
    if (!enabled) return
    if (!silent) setLoading(true)
    try {
      const r = await api.get(path, { params })
      if (alive.current) { setData(r.data); setError('') }
    } catch (e) {
      if (alive.current) setError(errMsg(e))
    } finally {
      if (alive.current) setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled])

  useEffect(() => {
    alive.current = true
    load()
    let t
    if (poll) t = setInterval(() => load(true), poll)
    return () => { alive.current = false; clearInterval(t) }
  }, [load, poll])

  return { data, loading, error, reload: () => load(true), refetch: () => load(false) }
}

/** The server's "today" (hostel local time), so clients in other time zones book correctly. */
export function useServerToday() {
  const [today, setToday] = useState(null)
  useEffect(() => {
    api.get('/health').then((r) => setToday(r.data.time.slice(0, 10))).catch(() => {
      const d = new Date()
      setToday(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
    })
  }, [])
  return today
}
