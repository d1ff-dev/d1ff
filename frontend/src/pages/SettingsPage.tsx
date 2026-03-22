import { useEffect, useState } from 'react'
import {
  getMe, getInstallations,
  saveSettings,
  type User, type InstallationWithConfig, type SettingsPayload
} from '../api'

const PROVIDERS = ['openai', 'anthropic', 'google', 'deepseek'] as const

function InstallationForm({ item, onSaved }: {
  item: InstallationWithConfig
  onSaved: (id: number) => void
}) {
  const { installation, config } = item
  const [provider, setProvider] = useState(config.provider || 'openai')
  const [model, setModel] = useState(config.model || '')
  const [apiKey, setApiKey] = useState('')
  const [endpoint, setEndpoint] = useState(config.custom_endpoint || '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const payload: SettingsPayload = {
        installation_id: installation.installation_id,
        provider,
        model,
        api_key: apiKey,
        custom_endpoint: endpoint,
      }
      await saveSettings(payload)
      onSaved(installation.installation_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <article>
      <header>
        <strong>{installation.account_login}</strong> ({installation.account_type})
      </header>
      {error && <p role="alert">{error}</p>}
      <form onSubmit={handleSubmit}>
        <label htmlFor={`provider-${installation.installation_id}`}>LLM Provider</label>
        <select
          id={`provider-${installation.installation_id}`}
          value={provider}
          onChange={e => setProvider(e.target.value)}
          required
        >
          {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>

        <label htmlFor={`model-${installation.installation_id}`}>Model</label>
        <input
          id={`model-${installation.installation_id}`}
          type="text"
          value={model}
          onChange={e => setModel(e.target.value)}
          placeholder="e.g. gpt-4o, claude-opus-4-5, gemini-pro"
          required
        />

        <label htmlFor={`endpoint-${installation.installation_id}`}>
          Custom LLM Endpoint (optional)
        </label>
        <input
          id={`endpoint-${installation.installation_id}`}
          type="url"
          value={endpoint}
          onChange={e => setEndpoint(e.target.value)}
          placeholder="https://my-azure-openai.openai.azure.com (leave blank for default)"
          autoComplete="off"
        />
        <small>Leave blank to use the default provider URL.</small>

        <label htmlFor={`api-key-${installation.installation_id}`}>API Key</label>
        <input
          id={`api-key-${installation.installation_id}`}
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder={config.has_key ? 'Key saved — enter new key to update' : 'Enter your API key'}
          required={!config.has_key}
          autoComplete="off"
        />

        <button type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
      </form>
    </article>
  )
}

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null)
  const [items, setItems] = useState<InstallationWithConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    Promise.all([getMe(), getInstallations()])
      .then(([me, installations]) => {
        setUser(me)
        setItems(installations)
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  function handleSaved(id: number) {
    setSavedIds(prev => new Set([...prev, id]))
  }

  if (loading) return <main className="container"><p aria-busy="true">Loading…</p></main>
  if (error) return <main className="container"><p role="alert">{error}</p></main>

  return (
    <main className="container">
      <h1>d1ff Settings</h1>
      <p>
        Signed in as <strong>{user?.login}</strong> —{' '}
        <a href="/logout">Sign out</a>
      </p>
      {items.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '2rem 0' }}>
          <p>No installations found. This can happen if the GitHub App hasn't been installed yet,
             or if the webhook hasn't arrived.</p>
          <a href="/logout" role="button" style={{ display: 'inline-block', marginTop: '1rem' }}>
            Re-authenticate with GitHub
          </a>
          <p style={{ marginTop: '1.5rem' }}>
            <small>This will re-sync your installations from GitHub.</small>
          </p>
        </div>
      ) : (
        items.map(item => (
          <div key={item.installation.installation_id}>
            {savedIds.has(item.installation.installation_id) && (
              <p role="alert">Settings saved successfully.</p>
            )}
            <InstallationForm item={item} onSaved={handleSaved} />
          </div>
        ))
      )}
    </main>
  )
}
