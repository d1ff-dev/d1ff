import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import DashboardLayout from './components/DashboardLayout'
import LoginPage from './pages/LoginPage'
import SetupPage from './pages/SetupPage'
import RepositoriesPage from './pages/RepositoriesPage'
import SettingsPage from './pages/SettingsPage'
import AccountPage from './pages/AccountPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/setup" element={<SetupPage />} />
            <Route element={<DashboardLayout />}>
              <Route path="/repositories" element={<RepositoriesPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/account" element={<AccountPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/repositories" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
