export interface User {
  login: string
  name: string | null
  github_id: number
  user_id: number
}

export interface Installation {
  installation_id: number
  account_login: string
  account_type: string
}

export interface InstallationConfig {
  provider: string
  model: string
  has_key: boolean
  custom_endpoint: string | null
}

export interface InstallationWithConfig {
  installation: Installation
  config: InstallationConfig
}

export interface SettingsPayload {
  installation_id: number
  provider: string
  model: string
  api_key: string
  custom_endpoint: string
}

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (res.status === 401) {
    window.location.href = '/auth/github/login'
    throw new Error('Not authenticated')
  }
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export function getMe(): Promise<User> {
  return apiFetch<User>('/api/me')
}

export function getInstallations(): Promise<InstallationWithConfig[]> {
  return apiFetch<InstallationWithConfig[]>('/api/installations')
}

export function saveSettings(payload: SettingsPayload): Promise<{ saved: boolean }> {
  return apiFetch<{ saved: boolean }>('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
