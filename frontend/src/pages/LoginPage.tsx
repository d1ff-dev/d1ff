import { motion } from 'framer-motion'
import { Navigate, useSearchParams, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import FadeIn from '../components/FadeIn'

function GitHubIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.009-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
    </svg>
  )
}

function ServerIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="8" rx="1" />
      <rect x="2" y="14" width="20" height="8" rx="1" />
      <circle cx="6" cy="6" r="1" fill="currentColor" />
      <circle cx="6" cy="18" r="1" fill="currentColor" />
    </svg>
  )
}

function SparkleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
    </svg>
  )
}

function LockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" />
      <path d="M7 11V7a5 5 0 0110 0v4" />
    </svg>
  )
}

/* Decorative vertical lines for background */
function BackgroundLines() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden">
      {[...Array(12)].map((_, i) => (
        <div
          key={i}
          className="absolute top-0 bottom-0 w-px bg-border"
          style={{
            left: `${8 + i * 7.5}%`,
            opacity: i % 3 === 0 ? 0.6 : 0.25,
          }}
        />
      ))}
    </div>
  )
}

export default function LoginPage() {
  const { user, loading, appConfig } = useAuth()
  const [searchParams] = useSearchParams()
  const isSignIn = searchParams.get('mode') === 'signin'

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <span className="font-mono text-sm text-fg-muted">Loading…</span>
      </div>
    )
  }

  if (user) {
    return <Navigate to="/repositories" replace />
  }

  return (
    <div className="relative min-h-screen bg-bg">
      <BackgroundLines />

      {/* Glow orb */}
      <div className="pointer-events-none absolute left-1/4 top-1/3 h-[600px] w-[600px] rounded-full bg-green/[0.04] blur-[120px]" />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl items-center px-5 sm:px-8">
        <div className="grid w-full gap-12 lg:grid-cols-2 lg:gap-16">
          {/* Left — Hero copy */}
          <motion.div
            className="flex flex-col justify-center"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6, ease: 'easeOut' }}
          >
            <span className="font-mono text-xs uppercase tracking-[0.2em] text-green">
              // GET_STARTED
            </span>

            <h1 className="mt-6 font-mono text-3xl font-bold leading-snug tracking-tight text-fg sm:text-4xl lg:text-5xl">
              State-of-the-art AI review.{' '}
              <span className="text-green">Free&nbsp;&amp;&nbsp;open source.</span>
            </h1>

            <p className="mt-6 max-w-md font-body text-sm leading-relaxed text-fg-muted sm:text-lg">
              100% open source. Self-host on your infra or use our
              cloud&nbsp;— no vendor lock-in.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="https://github.com/d1ff-dev/d1ff"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 bg-green px-6 py-3 font-mono text-sm font-bold text-bg transition-all hover:shadow-[0_0_24px_rgba(29,158,117,0.3)] hover:brightness-110"
              >
                <SparkleIcon />
                Free &amp; open source
              </a>
              <span className="inline-flex items-center gap-2 border border-border px-6 py-3 font-mono text-sm text-fg-muted transition-colors hover:border-border-hover hover:text-fg">
                <LockIcon />
                Bring your own keys
              </span>
            </div>
          </motion.div>

          {/* Right — Login card */}
          <FadeIn delay={0.35} className="flex items-center">
            <div className="w-full border border-border bg-bg-card p-6 sm:p-8">
              <h2 className="font-mono text-lg font-bold text-fg">
                {isSignIn ? 'Welcome back' : 'Get started'}
              </h2>
              <p className="mt-2 font-body text-sm leading-relaxed text-fg-muted">
                {isSignIn
                  ? 'Sign in to continue reviewing your code.'
                  : 'Connect your GitHub or self-host on your own infrastructure. Open source, free forever.'}
              </p>

              <div className="mt-6 flex flex-col gap-3">
                {/* GitHub button */}
                <a
                  href={isSignIn ? '/auth/github/login' : (appConfig?.github_app_install_url || '#')}
                  className="group relative flex items-center gap-4 border border-border bg-bg-elevated p-4 transition-colors hover:border-green/30"
                >
                  <span className="absolute right-3 top-3 inline-flex h-5 items-center rounded-full bg-green/15 px-2 font-mono text-[11px] text-green">
                    CLOUD
                  </span>
                  <span className="text-fg-muted transition-colors group-hover:text-green">
                    <GitHubIcon />
                  </span>
                  <div>
                    <span className="block font-mono text-sm font-bold text-fg">
                      {isSignIn ? 'Sign in with GitHub' : 'Sign up with GitHub'}
                    </span>
                    <span className="block font-body text-xs text-fg-muted">
                      {isSignIn ? 'Continue with your GitHub account' : 'Install the app and get reviews in 60 seconds'}
                    </span>
                  </div>
                </a>

                {/* Self-host */}
                <a
                  href="https://github.com/d1ff-dev/d1ff"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-center gap-4 border border-border bg-bg-elevated p-4 transition-colors hover:border-green/30"
                >
                  <span className="text-fg-muted transition-colors group-hover:text-green">
                    <ServerIcon />
                  </span>
                  <div>
                    <span className="block font-mono text-sm font-bold text-fg">
                      Self-host
                    </span>
                    <span className="block font-body text-xs text-fg-muted">
                      Your infra, your keys, your data&nbsp;— full control
                    </span>
                  </div>
                </a>
              </div>

              <div className="mt-4 border-t border-border pt-4 text-center font-body text-sm text-fg-muted">
                {isSignIn ? (
                  <>New to d1ff? <Link to="/login" className="text-fg underline">Create an account</Link></>
                ) : (
                  <>Already have an account? <Link to="/login?mode=signin" className="text-fg underline">Sign in</Link></>
                )}
              </div>
            </div>
          </FadeIn>
        </div>
      </div>
    </div>
  )
}
