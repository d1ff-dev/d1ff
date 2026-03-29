import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getInstallations } from '../api'
import FadeIn from '../components/FadeIn'

function GitHubIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.009-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
    </svg>
  )
}

export default function SetupPage() {
  const { user, appConfig } = useAuth()
  const [checking, setChecking] = useState(true)
  const [hasInstallations, setHasInstallations] = useState(false)

  useEffect(() => {
    getInstallations()
      .then((installations) => {
        setHasInstallations(installations.length > 0)
      })
      .catch(() => {})
      .finally(() => setChecking(false))
  }, [])

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <span className="font-mono text-sm text-fg-muted">Loading…</span>
      </div>
    )
  }

  if (hasInstallations) {
    return <Navigate to="/repositories" replace />
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-5">
      <FadeIn className="w-full max-w-md">
        <div className="border border-border bg-bg-card p-8">
          <h1 className="font-mono text-xl font-bold text-fg">
            Welcome, {user?.name || user?.login}!
          </h1>
          <p className="mt-3 font-body text-sm leading-relaxed text-fg-muted">
            Select the repositories you want d1ff to review.
          </p>

          <a
            href={appConfig?.github_app_install_url || '#'}
            className="mt-6 flex items-center justify-center gap-3 bg-green px-6 py-3 font-mono text-sm font-bold text-bg transition-all hover:shadow-[0_0_24px_rgba(29,158,117,0.3)] hover:brightness-110"
          >
            <GitHubIcon />
            Choose repositories
          </a>

          <p className="mt-4 text-center font-body text-xs text-fg-muted">
            Part of an organization that already uses d1ff? Ask the admin to add you.
          </p>
        </div>
      </FadeIn>
    </div>
  )
}
