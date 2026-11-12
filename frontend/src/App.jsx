import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import { Spinner } from './components/ui'
import Shell from './layouts/Shell'
import Landing from './pages/auth/Landing'
import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import SetPassword from './pages/auth/SetPassword'
import StudentDashboard from './pages/student/Dashboard'
import BookWash from './pages/student/BookWash'
import Payment from './pages/student/Payment'
import MyBookings from './pages/student/MyBookings'
import Notifications from './pages/student/Notifications'  // shared by both portals
import Profile from './pages/student/Profile'
import Overview from './pages/operator/Overview'
import Appointments from './pages/operator/Appointments'
import Payments from './pages/operator/Payments'
import Machines from './pages/operator/Machines'
import WashModes from './pages/operator/WashModes'
import Reschedules from './pages/operator/Reschedules'
import Reports from './pages/operator/Reports'
import SettingsPage from './pages/operator/Settings'

function Guard({ role, children }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  if (!user) return <Navigate to={role === 'OPERATOR' ? '/operator/login' : '/login'} replace />
  if (user.role !== role) return <Navigate to={user.role === 'OPERATOR' ? '/operator' : '/student'} replace />
  return children
}

function Public({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  if (user) return <Navigate to={user.role === 'OPERATOR' ? '/operator' : '/student'} replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Public><Landing /></Public>} />
      <Route path="/login" element={<Public><Login portal="STUDENT" /></Public>} />
      <Route path="/register" element={<Public><Register /></Public>} />
      <Route path="/operator/set-password" element={<SetPassword />} />
      <Route path="/operator/login" element={<Public><Login portal="OPERATOR" /></Public>} />

      <Route path="/student" element={<Guard role="STUDENT"><Shell role="STUDENT" /></Guard>}>
        <Route index element={<StudentDashboard />} />
        <Route path="book" element={<BookWash />} />
        <Route path="payment/:id" element={<Payment />} />
        <Route path="bookings" element={<MyBookings />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="profile" element={<Profile />} />
      </Route>

      <Route path="/operator" element={<Guard role="OPERATOR"><Shell role="OPERATOR" /></Guard>}>
        <Route index element={<Overview />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="payments" element={<Payments />} />
        <Route path="machines" element={<Machines />} />
        <Route path="modes" element={<WashModes />} />
        <Route path="reschedules" element={<Reschedules />} />
        <Route path="reports" element={<Reports />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
