import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getMe, getAppConfig, type User, type AppConfig } from '../api'

interface AuthState {
  user: User | null
  loading: boolean
  hasGlobalSettings: boolean
  setHasGlobalSettings: (v: boolean) => void
  appConfig: AppConfig | null
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  hasGlobalSettings: false,
  setHasGlobalSettings: () => {},
  appConfig: null,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [hasGlobalSettings, setHasGlobalSettings] = useState(false)
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null)

  useEffect(() => {
    Promise.all([
      getMe().then((u) => {
        setUser(u)
        setHasGlobalSettings(u.hasGlobalSettings)
      }).catch(() => setUser(null)),
      getAppConfig().then(setAppConfig).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, hasGlobalSettings, setHasGlobalSettings, appConfig }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
