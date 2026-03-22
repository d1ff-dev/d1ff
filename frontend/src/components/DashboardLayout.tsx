import { Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from './Sidebar'
import SettingsModal from './SettingsModal'

export default function DashboardLayout() {
  const { hasGlobalSettings, setHasGlobalSettings } = useAuth()

  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      {!hasGlobalSettings && (
        <SettingsModal onSaved={() => setHasGlobalSettings(true)} />
      )}
    </div>
  )
}
