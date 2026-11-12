import axios from 'axios'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL || ''}/api`,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const url = err.config?.url || ''
    if (err.response?.status === 401 && !url.startsWith('/auth/')) {
      window.dispatchEvent(new Event('washmate:unauthorized'))
    }
    return Promise.reject(err)
  },
)

export const errMsg = (e) => e?.response?.data?.error || e?.message || 'Something went wrong'

export async function downloadCsv(path, params, filename) {
  const r = await api.get(path, { params: { ...params, format: 'csv' }, responseType: 'blob' })
  const url = URL.createObjectURL(r.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default api
