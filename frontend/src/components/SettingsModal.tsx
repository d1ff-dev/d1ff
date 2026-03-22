import GlobalSettingsForm from './GlobalSettingsForm'

export default function SettingsModal({ onSaved }: { onSaved: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 backdrop-blur-sm">
      <div className="w-full max-w-lg border border-border bg-bg-card p-6 sm:p-8">
        <span className="font-mono text-xs uppercase tracking-[0.2em] text-green">
          // SETUP
        </span>
        <h2 className="mt-4 font-mono text-xl font-bold text-fg">Configure LLM Provider</h2>
        <p className="mt-2 font-body text-sm text-fg-muted">
          Set your default LLM provider. This applies to all your installations.
        </p>
        <div className="mt-6">
          <GlobalSettingsForm onSaved={onSaved} />
        </div>
      </div>
    </div>
  )
}
