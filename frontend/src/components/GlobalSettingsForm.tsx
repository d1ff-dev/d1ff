import { useState } from 'react'
import { saveGlobalSettings, type GlobalSettings } from '../api'

const PROVIDERS = ['openai', 'anthropic', 'google', 'deepseek'] as const

export default function GlobalSettingsForm({
  initial,
  onSaved,
}: {
  initial?: GlobalSettings | null
  onSaved: () => void
}) {
  const [provider, setProvider] = useState(initial?.provider || 'openai')
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!apiKey && !initial?.has_key) {
      setError('API key is required')
      return
    }
    setError(null)
    setSaving(true)
    try {
      await saveGlobalSettings({
        provider,
        model: '',
        api_key: apiKey,
        custom_endpoint: '',
      })
      onSaved()
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
        <label className="mb-1.5 block font-mono text-xs text-fg-muted">LLM Provider</label>
        <select
          value={provider}
          onChange={e => setProvider(e.target.value)}
          required
          className="w-full border border-border bg-bg-elevated px-4 py-2.5 font-mono text-sm text-fg outline-none transition-colors focus:border-green/50"
        >
          {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <div>
        <label className="mb-1.5 block font-mono text-xs text-fg-muted">API Key</label>
        <input
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder={initial?.has_key ? 'Key saved — enter new key to update' : 'Enter your API key'}
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
