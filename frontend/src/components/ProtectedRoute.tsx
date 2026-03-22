import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <span className="font-mono text-sm text-fg-muted">Loading…</span>
      </div>
    )
  }

  return user ? <Outlet /> : <Navigate to="/login" replace />
}
