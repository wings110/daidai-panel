import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import { useEffect, useState } from 'react'
import MainLayout from './components/Layout/MainLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Tasks from './pages/Tasks'
import Scripts from './pages/Scripts'
import Envs from './pages/Envs'
import Logs from './pages/Logs'
import OpenApi from './pages/OpenApi'
import Subscriptions from './pages/Subscriptions'
import Notifications from './pages/Notifications'
import Deps from './pages/Deps'
import Users from './pages/Users'
import Settings from './pages/Settings'
import ApiDocs from './pages/ApiDocs'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn)
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

export default function App() {
  const [checking, setChecking] = useState(true)
  const checkAuth = useAuthStore((s) => s.checkAuth)

  useEffect(() => {
    // 应用启动时检查认证状态
    const initAuth = async () => {
      await checkAuth()
      setChecking(false)
    }
    initAuth()
  }, [checkAuth])

  // 认证检查中显示加载状态
  if (checking) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontSize: 14,
        color: '#8c8c8c'
      }}>
        正在加载...
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <MainLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="scripts" element={<Scripts />} />
        <Route path="envs" element={<Envs />} />
        <Route path="logs" element={<Logs />} />
        <Route path="open-api" element={<OpenApi />} />
        <Route path="subscriptions" element={<Subscriptions />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="deps" element={<Deps />} />
        <Route path="users" element={<Users />} />
        <Route path="settings" element={<Settings />} />
        <Route path="api-docs" element={<ApiDocs />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
