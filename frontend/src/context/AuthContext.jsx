import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import api from '../services/api'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get('/auth/me')
      setUser(data.user)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const onUnauth = () => setUser(null)
    window.addEventListener('washmate:unauthorized', onUnauth)
    return () => window.removeEventListener('washmate:unauthorized', onUnauth)
  }, [refresh])

  const login = async (email, password, portal) => {
    const { data } = await api.post('/auth/login', { email, password, portal })
    setUser(data.user)
    return data.user
  }
  const register = async (payload) => {
    const { data } = await api.post('/auth/register', payload)
    setUser(data.user)
    return data.user
  }
  const logout = async () => {
    await api.post('/auth/logout').catch(() => {})
    setUser(null)
  }
  return <Ctx.Provider value={{ user, setUser, loading, login, register, logout, refresh }}>{children}</Ctx.Provider>
}
