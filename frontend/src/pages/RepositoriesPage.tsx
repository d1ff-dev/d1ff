import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { getRepositories, type Repository } from '../api'
import { useAuth } from '../contexts/AuthContext'

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50]

export default function RepositoriesPage() {
  const { appConfig } = useAuth()
  const [repos, setRepos] = useState<Repository[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [sortAsc, setSortAsc] = useState(true)
  const [page, setPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(10)

  useEffect(() => {
    getRepositories()
      .then(setRepos)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  // Deduplicate repos by full_name (same repo can appear in multiple installations)
  const unique = repos.filter((r, i, arr) => arr.findIndex(x => x.full_name === r.full_name) === i)

  const filtered = unique
    .filter(r => r.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => sortAsc
      ? a.name.localeCompare(b.name)
      : b.name.localeCompare(a.name))

  const totalPages = Math.max(1, Math.ceil(filtered.length / rowsPerPage))
  const paginated = filtered.slice((page - 1) * rowsPerPage, page * rowsPerPage)

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
        <div className="border border-red/30 bg-red-dim p-6 font-mono text-sm text-red">{error}</div>
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
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-mono text-2xl font-bold text-fg">Repositories</h1>
            <p className="mt-1 font-body text-sm text-fg-muted">
              List of repositories accessible to d1ff.
            </p>
          </div>
          <a
            href={appConfig?.github_app_install_url || '#'}
            className="flex items-center gap-2 bg-green px-4 py-2.5 font-mono text-sm font-bold text-bg transition-all hover:shadow-[0_0_24px_rgba(29,158,117,0.3)] hover:brightness-110"
          >
            <span className="text-lg">+</span> Add Repositories
          </a>
        </div>

        {/* Search */}
        <div className="mt-6 max-w-xs">
          <div className="flex items-center gap-2 border border-border bg-bg-elevated px-3 py-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-fg-dim">
              <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              placeholder="Search repositories"
              className="w-full bg-transparent font-mono text-sm text-fg placeholder:text-fg-dim outline-none"
            />
          </div>
        </div>

        {/* Table */}
        <div className="mt-4 border border-border">
          <div
            className="flex cursor-pointer items-center gap-1 border-b border-border bg-bg-card px-4 py-2.5"
            onClick={() => setSortAsc(!sortAsc)}
          >
            <span className="font-mono text-xs text-fg-muted">Repository</span>
            <span className="font-mono text-xs text-fg-dim">{sortAsc ? '↑' : '↓'}</span>
          </div>
          {paginated.length === 0 ? (
            <div className="px-4 py-8 text-center font-body text-sm text-fg-muted">
              {search ? 'No repositories match your search.' : 'No repositories found.'}
            </div>
          ) : (
            paginated.map(repo => (
              <div key={repo.full_name} className="flex items-center gap-2 border-b border-border px-4 py-3 last:border-b-0">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-fg-muted">
                  <path d="M4 20h16a2 2 0 002-2V8a2 2 0 00-2-2h-7.93a2 2 0 01-1.66-.9l-.82-1.2A2 2 0 007.93 3H4a2 2 0 00-2 2v13a2 2 0 002 2z" />
                </svg>
                <span className="font-mono text-sm text-fg">{repo.full_name}</span>
              </div>
            ))
          )}
        </div>

        {/* Pagination */}
        <div className="mt-3 flex items-center justify-end gap-4 font-mono text-xs text-fg-muted">
          <span className="flex items-center gap-1">
            Rows per page:
            <select
              value={rowsPerPage}
              onChange={e => { setRowsPerPage(Number(e.target.value)); setPage(1) }}
              className="border border-border bg-bg-elevated text-fg outline-none"
            >
              {ROWS_PER_PAGE_OPTIONS.map(n => <option key={n} value={n} className="bg-bg-elevated text-fg">{n}</option>)}
            </select>
          </span>
          <span>Page {page} of {totalPages}</span>
          <span className="flex gap-1">
            <button onClick={() => setPage(1)} disabled={page === 1} className="disabled:text-fg-dim">«</button>
            <button onClick={() => setPage(p => p - 1)} disabled={page === 1} className="disabled:text-fg-dim">‹</button>
            <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages} className="disabled:text-fg-dim">›</button>
            <button onClick={() => setPage(totalPages)} disabled={page === totalPages} className="disabled:text-fg-dim">»</button>
          </span>
        </div>
      </motion.div>
    </div>
  )
}
