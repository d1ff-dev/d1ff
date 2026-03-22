import { motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'

export default function AccountPage() {
  const { user } = useAuth()

  return (
    <div className="px-8 py-8">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.6, ease: 'easeOut' }}
      >
        <span className="font-mono text-xs uppercase tracking-[0.2em] text-green">
          // ACCOUNT
        </span>
        <h1 className="mt-4 font-mono text-2xl font-bold text-fg">Account</h1>

        <div className="mt-8 border border-border bg-bg-card p-6 sm:p-8">
          <div className="flex items-center gap-4">
            {user?.github_id && (
              <img
                src={`https://avatars.githubusercontent.com/u/${user.github_id}?v=4&s=80`}
                alt={user.login}
                className="h-16 w-16 rounded-full border border-border"
              />
            )}
            <div>
              <div className="font-mono text-lg font-bold text-fg">{user?.login}</div>
              {user?.name && (
                <div className="font-body text-sm text-fg-muted">{user.name}</div>
              )}
            </div>
          </div>

          <div className="mt-8 border-t border-border pt-6">
            <a
              href="/logout"
              className="inline-block border border-border px-6 py-3 font-mono text-sm text-fg-muted transition-colors hover:border-red/30 hover:text-red"
            >
              Sign out
            </a>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
