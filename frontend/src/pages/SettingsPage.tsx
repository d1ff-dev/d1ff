import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  getInstallations, saveSettings, getGlobalSettings,
  type InstallationWithConfig, type SettingsPayload, type GlobalSettings
} from '../api'
import GlobalSettingsForm from '../components/GlobalSettingsForm'

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
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {error && (
        <div className="border border-red/30 bg-red-dim p-3 font-mono text-sm text-red">
          {error}
        </div>
      )}

      <div>
        <label
          htmlFor={`provider-${installation.installation_id}`}
          className="mb-1.5 block font-mono text-xs text-fg-muted"
        >
          LLM Provider
        </label>
        <select
          id={`provider-${installation.installation_id}`}
          value={provider}
          onChange={e => setProvider(e.target.value)}
          required
          className="w-full border border-border bg-bg-elevated px-4 py-2.5 font-mono text-sm text-fg outline-none transition-colors focus:border-green/50"
        >
          {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      <div>
        <label
          htmlFor={`model-${installation.installation_id}`}
          className="mb-1.5 block font-mono text-xs text-fg-muted"
        >
          Model
        </label>
        <input
          id={`model-${installation.installation_id}`}
          type="text"
          value={model}
          onChange={e => setModel(e.target.value)}
          placeholder="e.g. gpt-4o, claude-opus-4-5, gemini-pro"
          required
          className="w-full border border-border bg-bg-elevated px-4 py-2.5 font-mono text-sm text-fg placeholder:text-fg-dim outline-none transition-colors focus:border-green/50"
        />
      </div>

      <div>
        <label
          htmlFor={`endpoint-${installation.installation_id}`}
          className="mb-1.5 block font-mono text-xs text-fg-muted"
        >
          Custom LLM Endpoint
          <span className="ml-2 text-fg-dim">(optional)</span>
        </label>
        <input
          id={`endpoint-${installation.installation_id}`}
          type="url"
          value={endpoint}
          onChange={e => setEndpoint(e.target.value)}
          placeholder="https://my-azure-openai.openai.azure.com"
          autoComplete="off"
          className="w-full border border-border bg-bg-elevated px-4 py-2.5 font-mono text-sm text-fg placeholder:text-fg-dim outline-none transition-colors focus:border-green/50"
        />
        <p className="mt-1 font-mono text-xs text-fg-dim">
          Leave blank to use the default provider URL.
        </p>
      </div>

      <div>
        <label
          htmlFor={`api-key-${installation.installation_id}`}
          className="mb-1.5 block font-mono text-xs text-fg-muted"
        >
          API Key
        </label>
        <input
          id={`api-key-${installation.installation_id}`}
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder={config.has_key ? 'Key saved — enter new key to update' : 'Enter your API key'}
          required={!config.has_key}
          autoComplete="off"
          className="w-full border border-border bg-bg-elevated px-4 py-2.5 font-mono text-sm text-fg placeholder:text-fg-dim outline-none transition-colors focus:border-green/50"
        />
      </div>

      <button
        type="submit"
        disabled={saving}
        className="mt-2 w-full bg-green px-6 py-3 font-mono text-sm font-bold text-bg transition-all hover:shadow-[0_0_24px_rgba(29,158,117,0.3)] hover:brightness-110 disabled:opacity-50"
      >
        {saving ? 'Saving…' : 'Save Settings'}
      </button>
    </form>
  )
}

export default function SettingsPage() {
  const [items, setItems] = useState<InstallationWithConfig[]>([])
  const [globalSettings, setGlobalSettings] = useState<GlobalSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set())
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    Promise.all([getInstallations(), getGlobalSettings()])
      .then(([installations, global]) => {
        setItems(installations)
        setGlobalSettings(global)
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  function handleSaved(id: number) {
    setSavedIds(prev => new Set([...prev, id]))
    setExpandedIds(prev => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  function toggleExpanded(id: number) {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="font-mono text-sm text-fg-muted">Loading…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="border border-red/30 bg-red-dim p-6 font-mono text-sm text-red">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="px-8 py-8">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.6, ease: 'easeOut' }}
      >
        <span className="font-mono text-xs uppercase tracking-[0.2em] text-green">
          // SETTINGS
        </span>
        <h1 className="mt-4 font-mono text-2xl font-bold text-fg">Settings</h1>
        <p className="mt-1 font-body text-sm text-fg-muted">
          Configure LLM providers for your installations.
        </p>

        {/* Global Default Settings */}
        <div className="mt-8 border border-border bg-bg-card p-6 sm:p-8">
          <h2 className="mb-6 font-mono text-lg font-bold text-fg">Global Default Settings</h2>
          {globalSettings !== null && (
            <GlobalSettingsForm initial={globalSettings} onSaved={() => {}} />
          )}
        </div>

        {/* Per-Installation Overrides */}
        <div className="mt-8">
          <h2 className="font-mono text-base font-bold text-fg">Per-Installation Overrides</h2>
          <p className="mt-1 font-body text-xs text-fg-muted">
            Override the global defaults for specific installations.
          </p>

          {items.length === 0 ? (
            <motion.div
              className="mt-6 border border-border bg-bg-card p-8 text-center"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.5, ease: 'easeOut' }}
            >
              <p className="font-body text-sm text-fg-muted">
                No installations found. Install the GitHub App first, or re-authenticate.
              </p>
            </motion.div>
          ) : (
            <div className="mt-4 flex flex-col gap-4">
              {items.map((item, index) => {
                const { installation, config } = item
                const id = installation.installation_id
                const hasCustom = config.has_key
                const isExpanded = expandedIds.has(id)

                return (
                  <motion.div
                    key={id}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 + index * 0.1, duration: 0.5, ease: 'easeOut' }}
                    className="border border-border bg-bg-card p-5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm font-bold text-fg">
                          {installation.account_login}
                        </span>
                        <span className="inline-flex h-5 items-center rounded-full bg-green/15 px-2 font-mono text-[11px] text-green">
                          {installation.account_type}
                        </span>
                        {hasCustom ? (
                          <span className="inline-flex h-5 items-center rounded-full bg-bg-elevated px-2 font-mono text-[11px] text-fg-muted">
                            {config.provider} / {config.model}
                          </span>
                        ) : (
                          <span className="inline-flex h-5 items-center rounded-full bg-bg-elevated px-2 font-mono text-[11px] text-fg-dim">
                            Using default settings
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {hasCustom && (
                          <button
                            onClick={() => {
                              // Reset to default by removing custom config
                              setSavedIds(prev => {
                                const next = new Set(prev)
                                next.delete(id)
                                return next
                              })
                            }}
                            className="font-mono text-xs text-fg-muted transition-colors hover:text-red"
                          >
                            Reset to default
                          </button>
                        )}
                        <button
                          onClick={() => toggleExpanded(id)}
                          className="border border-border px-3 py-1.5 font-mono text-xs text-fg-muted transition-colors hover:border-green/30 hover:text-fg"
                        >
                          {isExpanded ? 'Cancel' : 'Customize'}
                        </button>
                      </div>
                    </div>

                    {savedIds.has(id) && (
                      <div className="mt-3 border border-green/30 bg-green-dim p-3 font-mono text-sm text-green">
                        Settings saved successfully.
                      </div>
                    )}

                    {isExpanded && (
                      <div className="mt-5 border-t border-border pt-5">
                        <InstallationForm item={item} onSaved={handleSaved} />
                      </div>
                    )}
                  </motion.div>
                )
              })}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  )
}
