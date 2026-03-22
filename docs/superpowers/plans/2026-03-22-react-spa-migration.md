# React SPA Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Jinja2 server-rendered HTML with a React TypeScript SPA (Vite), served as static files by FastAPI from a single Docker container.

**Architecture:** A Node.js 22-alpine stage in the Dockerfile builds `frontend/` into a static bundle (`dist/`), which the Python runtime stage copies to `/app/static/`. FastAPI mounts `/assets` as StaticFiles and adds a catch-all SPA fallback route serving `index.html`. New JSON API endpoints at `/api/me`, `/api/installations`, and `POST /api/settings` replace the Jinja2 form handlers.

**Tech Stack:** FastAPI 0.115+, Vite 6, React 19, TypeScript 5.7, aiosqlite, pytest + pytest-asyncio, httpx AsyncClient, Docker multi-stage build.

---

## File Map

**Create:**
- `frontend/package.json` — npm manifest for React/Vite/TypeScript
- `frontend/vite.config.ts` — Vite config with dev proxy to FastAPI
- `frontend/tsconfig.json` — TypeScript project references root
- `frontend/tsconfig.app.json` — App TypeScript config
- `frontend/tsconfig.node.json` — Node/Vite TypeScript config
- `frontend/index.html` — SPA entry HTML with Pico CSS CDN
- `frontend/src/main.tsx` — React DOM root mount
- `frontend/src/App.tsx` — Root component (renders SettingsPage)
- `frontend/src/api.ts` — API client types and fetch helpers
- `frontend/src/pages/SettingsPage.tsx` — Settings UI component
- `src/d1ff/web/api.py` — JSON API router (`/api/me`, `/api/installations`, `POST /api/settings`)
- `tests/test_web/test_api.py` — Tests for the new JSON API endpoints

**Modify:**
- `.gitignore` — add `frontend/node_modules/`, `frontend/dist/`, `frontend/.vite/`
- `pyproject.toml` — add `aiofiles>=23.0.0` dependency
- `src/d1ff/web/router.py` — remove Jinja2 settings handlers, keep only OAuth + logout routes
- `src/d1ff/web/__init__.py` — add `api_router` export
- `src/d1ff/main.py` — include `api_router`, add StaticFiles mount + SPA fallback, remove `GET /`
- `Dockerfile` — add frontend build stage, copy static bundle into runtime image

**Delete:**
- `src/d1ff/web/templates/settings.html`
- `src/d1ff/web/templates/base.html`
- `tests/test_web/test_settings.py` — tests old Jinja2 `/settings` routes
- `tests/test_web/test_settings_endpoint.py` — tests old Jinja2 `POST /settings`

---

## Task 1: Config changes (.gitignore + aiofiles)

**Files:**
- Modify: `.gitignore`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update .gitignore**

  Append to the end of `.gitignore`:
  ```
  # Frontend
  frontend/node_modules/
  frontend/dist/
  frontend/.vite/
  ```

- [ ] **Step 2: Add aiofiles to pyproject.toml**

  In `pyproject.toml`, in the `dependencies` list, add after `"itsdangerous>=2.2.0"`:
  ```toml
  "aiofiles>=23.0.0",
  ```

  Reason: `fastapi.staticfiles.StaticFiles` requires `aiofiles` at runtime. Without it, mounting `StaticFiles` raises `RuntimeError: The 'aiofiles' package is required`.

- [ ] **Step 3: Commit**

  ```bash
  git add .gitignore pyproject.toml
  git commit -m "chore: add frontend gitignore entries and aiofiles dependency"
  ```

---

## Task 2: Frontend scaffold — config files

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`

- [ ] **Step 1: Create `frontend/package.json`**

  ```json
  {
    "name": "d1ff-frontend",
    "private": true,
    "version": "0.1.0",
    "type": "module",
    "scripts": {
      "dev": "vite",
      "build": "tsc -b && vite build",
      "preview": "vite preview"
    },
    "dependencies": {
      "react": "^19.0.0",
      "react-dom": "^19.0.0"
    },
    "devDependencies": {
      "@types/react": "^19.0.0",
      "@types/react-dom": "^19.0.0",
      "@vitejs/plugin-react": "^4.3.4",
      "typescript": "~5.7.2",
      "vite": "^6.2.0"
    }
  }
  ```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

  ```typescript
  import { defineConfig } from 'vite'
  import react from '@vitejs/plugin-react'

  export default defineConfig({
    plugins: [react()],
    base: '/',
    server: {
      proxy: {
        '/api': 'http://localhost:8000',
        '/auth': 'http://localhost:8000',
        '/webhook': 'http://localhost:8000',
        '/health': 'http://localhost:8000',
        '/logout': 'http://localhost:8000',
      },
    },
    build: {
      outDir: 'dist',
    },
  })
  ```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

  ```json
  {
    "files": [],
    "references": [
      { "path": "./tsconfig.app.json" },
      { "path": "./tsconfig.node.json" }
    ]
  }
  ```

- [ ] **Step 4: Create `frontend/tsconfig.app.json`**

  ```json
  {
    "compilerOptions": {
      "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
      "target": "ES2020",
      "useDefineForClassFields": true,
      "lib": ["ES2020", "DOM", "DOM.Iterable"],
      "module": "ESNext",
      "skipLibCheck": true,
      "moduleResolution": "bundler",
      "allowImportingTsExtensions": true,
      "isolatedModules": true,
      "moduleDetection": "force",
      "noEmit": true,
      "jsx": "react-jsx",
      "strict": true,
      "noUnusedLocals": true,
      "noUnusedParameters": true,
      "noFallthroughCasesInSwitch": true,
      "noUncheckedSideEffectImports": true
    },
    "include": ["src"]
  }
  ```

- [ ] **Step 5: Create `frontend/tsconfig.node.json`**

  ```json
  {
    "compilerOptions": {
      "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
      "target": "ES2022",
      "lib": ["ES2023"],
      "module": "ESNext",
      "skipLibCheck": true,
      "moduleResolution": "bundler",
      "allowImportingTsExtensions": true,
      "isolatedModules": true,
      "moduleDetection": "force",
      "noEmit": true,
      "strict": true,
      "noUnusedLocals": true,
      "noUnusedParameters": true,
      "noFallthroughCasesInSwitch": true,
      "noUncheckedSideEffectImports": true
    },
    "include": ["vite.config.ts"]
  }
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json
  git commit -m "feat: add Vite + React + TypeScript frontend scaffold config"
  ```

---

## Task 3: Frontend source files

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Create `frontend/index.html`**

  ```html
  <!doctype html>
  <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>d1ff</title>
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    </head>
    <body>
      <div id="root"></div>
      <script type="module" src="/src/main.tsx"></script>
    </body>
  </html>
  ```

- [ ] **Step 2: Create `frontend/src/main.tsx`**

  ```tsx
  import { StrictMode } from 'react'
  import { createRoot } from 'react-dom/client'
  import App from './App'

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
  ```

- [ ] **Step 3: Create `frontend/src/App.tsx`**

  ```tsx
  import SettingsPage from './pages/SettingsPage'

  export default function App() {
    return <SettingsPage />
  }
  ```

- [ ] **Step 4: Create `frontend/src/api.ts`**

  ```typescript
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
  ```

- [ ] **Step 5: Create `frontend/src/pages/SettingsPage.tsx`**

  ```tsx
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
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/index.html frontend/src/
  git commit -m "feat: add React SPA source files (SettingsPage, api client)"
  ```

---

## Task 4: npm install — generate package-lock.json

**Files:**
- Create: `frontend/package-lock.json` (generated)

- [ ] **Step 1: Run npm install**

  ```bash
  cd frontend && npm install
  ```

  Expected: `node_modules/` created, `package-lock.json` generated.

- [ ] **Step 2: Verify TypeScript build passes**

  ```bash
  npm run build
  ```

  Expected: `dist/` created with `index.html` and `assets/` subdirectory. Fix any TypeScript errors before proceeding.

- [ ] **Step 3: Commit package-lock.json**

  `package-lock.json` must be committed — it's required for `npm ci` in the Dockerfile.

  ```bash
  cd ..
  git add frontend/package-lock.json
  git commit -m "chore: add package-lock.json for reproducible npm ci in Docker"
  ```

---

## Task 5: Write failing tests for the new JSON API

**Files:**
- Create: `tests/test_web/test_api.py`

The existing `tests/test_web/test_settings.py` has a `make_session_cookie` helper and `REQUIRED_ENV` dict we'll reuse verbatim.

- [ ] **Step 1: Create `tests/test_web/test_api.py`**

  ```python
  """Tests for the JSON API endpoints — GET /api/me, GET /api/installations, POST /api/settings."""

  import datetime
  import json
  from unittest.mock import AsyncMock, patch

  import pytest
  from httpx import ASGITransport, AsyncClient

  from d1ff.config import get_settings
  from d1ff.main import app
  from d1ff.storage.models import Installation

  REQUIRED_ENV = {
      "GITHUB_APP_ID": "12345",
      "GITHUB_PRIVATE_KEY": "fake-pem-key",
      "GITHUB_WEBHOOK_SECRET": "test-webhook-secret",
      "ENCRYPTION_KEY": "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldA==",
      "GITHUB_CLIENT_ID": "test-client-id",
      "GITHUB_CLIENT_SECRET": "test-client-secret",
      "SESSION_SECRET_KEY": "test-session-secret-key-32-bytes!!",
      "DATABASE_URL": "sqlite+aiosqlite:///./test_api.db",
  }

  FAKE_USER = {"login": "testuser", "github_id": 12345, "name": "Test User", "user_id": 1}

  FAKE_INSTALLATION = Installation(
      installation_id=42,
      account_login="testorg",
      account_type="Organization",
      suspended=False,
      created_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
      updated_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
  )


  def make_session_cookie(user: dict, secret_key: str) -> str:
      """Craft a signed session cookie that Starlette's SessionMiddleware will accept."""
      import base64

      from itsdangerous import TimestampSigner

      signer = TimestampSigner(secret_key)
      data = base64.b64encode(json.dumps({"user": user}).encode("utf-8"))
      return signer.sign(data).decode("utf-8")


  @pytest.fixture(autouse=True)
  def setup_env(monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[misc]
      get_settings.cache_clear()
      for key, value in REQUIRED_ENV.items():
          monkeypatch.setenv(key, value)
      yield
      get_settings.cache_clear()


  # ---------------------------------------------------------------------------
  # GET /api/me
  # ---------------------------------------------------------------------------

  async def test_get_me_unauthenticated() -> None:
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/api/me")
      assert response.status_code == 401


  async def test_get_me_authenticated() -> None:
      cookie = make_session_cookie(FAKE_USER, REQUIRED_ENV["SESSION_SECRET_KEY"])
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          client.cookies.set("session", cookie)
          response = await client.get("/api/me")
      assert response.status_code == 200
      data = response.json()
      assert data["login"] == "testuser"
      assert data["github_id"] == 12345


  # ---------------------------------------------------------------------------
  # GET /api/installations
  # ---------------------------------------------------------------------------

  async def test_get_installations_unauthenticated() -> None:
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/api/installations")
      assert response.status_code == 401


  async def test_get_installations_returns_list() -> None:
      cookie = make_session_cookie(FAKE_USER, REQUIRED_ENV["SESSION_SECRET_KEY"])
      fake_config = {
          "provider": "openai",
          "model": "gpt-4o",
          "encrypted_key": "someencryptedvalue",
          "custom_endpoint": None,
      }
      with (
          patch(
              "d1ff.web.api.InstallationRepository.list_installations_for_user",
              new=AsyncMock(return_value=[FAKE_INSTALLATION]),
          ),
          patch(
              "d1ff.web.api.get_api_key_config",
              new=AsyncMock(return_value=fake_config),
          ),
      ):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              client.cookies.set("session", cookie)
              response = await client.get("/api/installations")

      assert response.status_code == 200
      data = response.json()
      assert len(data) == 1
      assert data[0]["installation"]["installation_id"] == 42
      assert data[0]["installation"]["account_login"] == "testorg"
      assert data[0]["config"]["provider"] == "openai"
      assert data[0]["config"]["has_key"] is True
      assert "encrypted_key" not in data[0]["config"]


  # ---------------------------------------------------------------------------
  # POST /api/settings
  # ---------------------------------------------------------------------------

  async def test_post_settings_unauthenticated() -> None:
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.post("/api/settings", json={
              "installation_id": 42, "provider": "openai", "model": "gpt-4o",
              "api_key": "sk-test", "custom_endpoint": "",
          })
      assert response.status_code == 401


  async def test_post_settings_saves_config() -> None:
      cookie = make_session_cookie(FAKE_USER, REQUIRED_ENV["SESSION_SECRET_KEY"])
      mock_upsert = AsyncMock()
      with (
          patch(
              "d1ff.web.api.InstallationRepository.list_installations_for_user",
              new=AsyncMock(return_value=[FAKE_INSTALLATION]),
          ),
          patch("d1ff.web.api.upsert_api_key_for_installation", mock_upsert),
      ):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              client.cookies.set("session", cookie)
              response = await client.post("/api/settings", json={
                  "installation_id": 42,
                  "provider": "openai",
                  "model": "gpt-4o",
                  "api_key": "sk-test",
                  "custom_endpoint": "",
              })

      assert response.status_code == 200
      assert response.json() == {"saved": True}
      mock_upsert.assert_called_once_with(42, "openai", "gpt-4o", "sk-test", custom_endpoint=None)


  async def test_post_settings_invalid_provider() -> None:
      cookie = make_session_cookie(FAKE_USER, REQUIRED_ENV["SESSION_SECRET_KEY"])
      with patch(
          "d1ff.web.api.InstallationRepository.list_installations_for_user",
          new=AsyncMock(return_value=[FAKE_INSTALLATION]),
      ):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              client.cookies.set("session", cookie)
              response = await client.post("/api/settings", json={
                  "installation_id": 42, "provider": "badprovider", "model": "m",
                  "api_key": "k", "custom_endpoint": "",
              })
      assert response.status_code == 400


  async def test_post_settings_unowned_installation() -> None:
      cookie = make_session_cookie(FAKE_USER, REQUIRED_ENV["SESSION_SECRET_KEY"])
      with patch(
          "d1ff.web.api.InstallationRepository.list_installations_for_user",
          new=AsyncMock(return_value=[FAKE_INSTALLATION]),
      ):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              client.cookies.set("session", cookie)
              response = await client.post("/api/settings", json={
                  "installation_id": 999,  # not owned
                  "provider": "openai", "model": "gpt-4o",
                  "api_key": "sk-test", "custom_endpoint": "",
              })
      assert response.status_code == 403


  async def test_post_settings_invalid_endpoint() -> None:
      cookie = make_session_cookie(FAKE_USER, REQUIRED_ENV["SESSION_SECRET_KEY"])
      with patch(
          "d1ff.web.api.InstallationRepository.list_installations_for_user",
          new=AsyncMock(return_value=[FAKE_INSTALLATION]),
      ):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              client.cookies.set("session", cookie)
              response = await client.post("/api/settings", json={
                  "installation_id": 42, "provider": "openai", "model": "gpt-4o",
                  "api_key": "sk-test", "custom_endpoint": "not-a-url",
              })
      assert response.status_code == 400


  async def test_post_settings_saves_custom_endpoint() -> None:
      cookie = make_session_cookie(FAKE_USER, REQUIRED_ENV["SESSION_SECRET_KEY"])
      mock_upsert = AsyncMock()
      with (
          patch(
              "d1ff.web.api.InstallationRepository.list_installations_for_user",
              new=AsyncMock(return_value=[FAKE_INSTALLATION]),
          ),
          patch("d1ff.web.api.upsert_api_key_for_installation", mock_upsert),
      ):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              client.cookies.set("session", cookie)
              response = await client.post("/api/settings", json={
                  "installation_id": 42, "provider": "openai", "model": "gpt-4o",
                  "api_key": "sk-test",
                  "custom_endpoint": "https://my-azure.openai.azure.com",
              })

      assert response.status_code == 200
      mock_upsert.assert_called_once_with(
          42, "openai", "gpt-4o", "sk-test",
          custom_endpoint="https://my-azure.openai.azure.com",
      )


  async def test_post_settings_clears_empty_endpoint() -> None:
      """Empty string custom_endpoint is normalized to None."""
      cookie = make_session_cookie(FAKE_USER, REQUIRED_ENV["SESSION_SECRET_KEY"])
      mock_upsert = AsyncMock()
      with (
          patch(
              "d1ff.web.api.InstallationRepository.list_installations_for_user",
              new=AsyncMock(return_value=[FAKE_INSTALLATION]),
          ),
          patch("d1ff.web.api.upsert_api_key_for_installation", mock_upsert),
      ):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              client.cookies.set("session", cookie)
              response = await client.post("/api/settings", json={
                  "installation_id": 42, "provider": "openai", "model": "gpt-4o",
                  "api_key": "sk-test", "custom_endpoint": "   ",
              })

      assert response.status_code == 200
      mock_upsert.assert_called_once_with(42, "openai", "gpt-4o", "sk-test", custom_endpoint=None)
  ```

- [ ] **Step 2: Run tests — verify they FAIL (module not found)**

  ```bash
  pytest tests/test_web/test_api.py -v
  ```

  Expected: Import error or `404` failures since `src/d1ff/web/api.py` doesn't exist yet.

- [ ] **Step 3: Commit failing tests**

  ```bash
  git add tests/test_web/test_api.py
  git commit -m "test: add failing tests for JSON API endpoints (TDD)"
  ```

---

## Task 6: Implement the JSON API router

**Files:**
- Create: `src/d1ff/web/api.py`

- [ ] **Step 1: Create `src/d1ff/web/api.py`**

  ```python
  """JSON API endpoints for the React SPA."""

  import aiosqlite
  import structlog
  from fastapi import APIRouter, Depends, HTTPException, Request
  from pydantic import BaseModel

  from d1ff.storage.api_key_repo import get_api_key_config, upsert_api_key_for_installation
  from d1ff.storage.database import get_db_connection
  from d1ff.storage.installation_repo import InstallationRepository

  logger = structlog.get_logger()

  router = APIRouter(prefix="/api", tags=["api"])

  ALLOWED_PROVIDERS = {"openai", "anthropic", "google", "deepseek"}


  def _get_session_user(request: Request) -> dict[str, object]:
      user = request.session.get("user")
      if not user:
          raise HTTPException(status_code=401, detail="Not authenticated")
      return user  # type: ignore[return-value]


  def _sanitize_config(cfg: dict[str, str | None] | None) -> dict[str, str | bool | None]:
      if not cfg:
          return {"provider": "", "model": "", "has_key": False, "custom_endpoint": None}
      return {
          "provider": cfg.get("provider", ""),
          "model": cfg.get("model", ""),
          "has_key": bool(cfg.get("encrypted_key")),
          "custom_endpoint": cfg.get("custom_endpoint"),
      }


  @router.get("/me")
  async def get_me(request: Request) -> dict[str, object]:
      """Return current authenticated user from session."""
      return _get_session_user(request)


  @router.get("/installations")
  async def get_installations(
      request: Request,
      db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
  ) -> list[dict[str, object]]:
      """Return installations and their configs for the authenticated user."""
      user = _get_session_user(request)
      repo = InstallationRepository(db)
      user_installations = await repo.list_installations_for_user(int(user["user_id"]))  # type: ignore[arg-type]
      result = []
      for inst in user_installations:
          cfg = await get_api_key_config(inst.installation_id)
          result.append({
              "installation": {
                  "installation_id": inst.installation_id,
                  "account_login": inst.account_login,
                  "account_type": inst.account_type,
              },
              "config": _sanitize_config(cfg),
          })
      return result


  class SettingsRequest(BaseModel):
      installation_id: int
      provider: str
      model: str
      api_key: str
      custom_endpoint: str = ""


  @router.post("/settings")
  async def update_settings(
      request: Request,
      body: SettingsRequest,
      db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
  ) -> dict[str, bool]:
      """Save API key and provider/model config for an installation."""
      user = _get_session_user(request)
      repo = InstallationRepository(db)
      user_installations = await repo.list_installations_for_user(int(user["user_id"]))  # type: ignore[arg-type]
      user_installation_ids = {i.installation_id for i in user_installations}

      if body.installation_id not in user_installation_ids:
          raise HTTPException(status_code=403, detail="Installation not found or not owned by you.")

      if body.provider not in ALLOWED_PROVIDERS:
          raise HTTPException(status_code=400, detail=f"Invalid provider: {body.provider}")

      endpoint = body.custom_endpoint.strip() or None
      if endpoint and not (endpoint.startswith("http://") or endpoint.startswith("https://")):
          raise HTTPException(
              status_code=400,
              detail="Custom endpoint must start with http:// or https://",
          )

      await upsert_api_key_for_installation(
          body.installation_id, body.provider, body.model, body.api_key, custom_endpoint=endpoint
      )
      logger.info("settings_saved", installation_id=body.installation_id, provider=body.provider)
      return {"saved": True}
  ```

- [ ] **Step 2: Run tests — verify they pass**

  ```bash
  pytest tests/test_web/test_api.py -v
  ```

  Expected: All tests PASS.

- [ ] **Step 3: Commit**

  ```bash
  git add src/d1ff/web/api.py
  git commit -m "feat: add JSON API router (GET /api/me, GET /api/installations, POST /api/settings)"
  ```

---

## Task 7: Update web module — router.py and __init__.py

**Files:**
- Modify: `src/d1ff/web/router.py`
- Modify: `src/d1ff/web/__init__.py`

- [ ] **Step 1: Replace `src/d1ff/web/router.py`**

  Remove all Jinja2/settings handler code. Keep only OAuth and logout routes. New content:

  ```python
  """Web UI OAuth routes for the d1ff application."""

  import aiosqlite
  import structlog
  from fastapi import APIRouter, Depends, Request
  from fastapi.responses import RedirectResponse
  from starlette.responses import Response

  from d1ff.config import get_settings
  from d1ff.github.oauth_handler import oauth
  from d1ff.storage.encryption import encrypt_value
  from d1ff.storage.database import get_db_connection
  from d1ff.storage.installation_repo import InstallationRepository
  from d1ff.web.auth import GITHUB_APP_INSTALL_URL

  logger = structlog.get_logger()

  router = APIRouter()


  @router.get("/auth/github/login")
  async def github_login(request: Request) -> Response:
      """Initiate GitHub OAuth authorization flow."""
      settings = get_settings()
      redirect_uri = f"{settings.BASE_URL}/auth/github/callback"
      return await oauth.github.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


  @router.get("/auth/github/callback", name="github_callback")
  async def github_callback(
      request: Request,
      db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
  ) -> Response:
      """Handle GitHub OAuth callback — create/update user, sync installations, redirect to /settings."""
      try:
          token = await oauth.github.authorize_access_token(request)
      except (KeyError, ValueError, OSError) as exc:
          logger.exception("oauth_callback_failed", error=str(exc))
          return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)

      access_token = token["access_token"]

      # Fetch user profile from GitHub
      resp = await oauth.github.get("user", token=token)
      if resp.status_code != 200:
          logger.error("github_user_api_failed", status=resp.status_code)
          return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)
      user_data = resp.json()

      # Encrypt access token before storing
      settings = get_settings()
      encrypted_token = encrypt_value(access_token, settings.ENCRYPTION_KEY)

      # Upsert user record
      repo = InstallationRepository(db)
      user_id = await repo.upsert_user(
          github_id=user_data["id"],
          login=user_data["login"],
          email=user_data.get("email"),
          avatar_url=user_data.get("avatar_url"),
          encrypted_token=encrypted_token,
      )

      # Fetch user's installations from GitHub API and sync.
      installation_ids: list[int] = []
      page = 1
      try:
          while True:
              installations_resp = await oauth.github.get(
                  "user/installations", token=token, params={"per_page": 100, "page": page}
              )
              if installations_resp.status_code != 200:
                  logger.error("github_installations_api_failed", status=installations_resp.status_code)
                  break
              installations_data = installations_resp.json()
              batch = installations_data.get("installations", [])
              installation_ids.extend(inst["id"] for inst in batch)
              if len(batch) < 100:
                  break
              page += 1
          await repo.sync_user_installations(user_id, installation_ids)
      except Exception:
          logger.exception("installation_sync_failed")

      # Create session
      request.session["user"] = {
          "login": user_data["login"],
          "github_id": user_data["id"],
          "name": user_data.get("name"),
          "user_id": user_id,
      }

      logger.info("user_logged_in", login=user_data["login"], installations_synced=len(installation_ids))
      return RedirectResponse(url="/settings", status_code=302)


  @router.get("/logout")
  async def logout(request: Request) -> Response:
      """Clear session and redirect to GitHub App install page."""
      login = request.session.get("user", {}).get("login", "unknown")
      request.session.clear()
      logger.info("user_logged_out", login=login)
      return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)
  ```

- [ ] **Step 2: Update `src/d1ff/web/__init__.py`**

  ```python
  """Public API re-exports for the d1ff web module."""

  from d1ff.web.api import router as api_router
  from d1ff.web.auth import require_login
  from d1ff.web.router import router as web_router

  __all__ = ["api_router", "web_router", "require_login"]
  ```

- [ ] **Step 3: Run all tests to verify nothing broke**

  ```bash
  pytest tests/ -v --ignore=tests/test_web/test_settings.py --ignore=tests/test_web/test_settings_endpoint.py
  ```

  Expected: All tests pass. (The old settings tests are excluded — they will be deleted next.)

- [ ] **Step 4: Commit**

  ```bash
  git add src/d1ff/web/router.py src/d1ff/web/__init__.py
  git commit -m "refactor: remove Jinja2 settings handlers; keep OAuth + logout routes only"
  ```

---

## Task 8: Update main.py — add StaticFiles + SPA fallback

**Files:**
- Modify: `src/d1ff/main.py`

- [ ] **Step 1: Rewrite `src/d1ff/main.py`**

  ```python
  import os
  from collections.abc import AsyncGenerator
  from contextlib import asynccontextmanager
  from pathlib import Path

  import structlog
  from fastapi import FastAPI
  from fastapi.responses import FileResponse
  from fastapi.staticfiles import StaticFiles
  from slowapi import _rate_limit_exceeded_handler
  from slowapi.errors import RateLimitExceeded
  from starlette.middleware.sessions import SessionMiddleware

  from d1ff.config import get_settings
  from d1ff.github import GitHubAppClient
  from d1ff.github.oauth_handler import register_github_oauth
  from d1ff.middleware import limiter
  from d1ff.observability import configure_logging
  from d1ff.observability.router import router as observability_router
  from d1ff.storage import init_db
  from d1ff.web import api_router, web_router

  logger = structlog.get_logger()


  @asynccontextmanager
  async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
      settings = get_settings()  # Triggers fail-fast validation
      configure_logging(settings.LOG_LEVEL)
      register_github_oauth()
      logger.info("d1ff starting", version="0.1.0", host=settings.HOST, port=settings.PORT)
      await init_db(settings.DATABASE_URL)
      logger.info("storage initialized", database_url=settings.DATABASE_URL)

      app.state.github_client = GitHubAppClient(
          app_id=settings.GITHUB_APP_ID,
          private_key=settings.GITHUB_PRIVATE_KEY,
      )
      logger.info("github_app_client_initialized", app_id=settings.GITHUB_APP_ID)

      yield
      logger.info("d1ff shutting down")


  app = FastAPI(title="d1ff", version="0.1.0", lifespan=lifespan)
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
  _session_secret = os.environ.get("SESSION_SECRET_KEY", "dev-placeholder-not-for-production")
  app.add_middleware(SessionMiddleware, secret_key=_session_secret)

  # Router registration order matters: specific routes before SPA fallback
  app.include_router(observability_router)
  app.include_router(api_router)
  app.include_router(web_router)

  # Static files + SPA fallback — only registered when the built bundle exists
  # (i.e., in Docker). In dev mode (uvicorn from source), this block is skipped
  # and the app runs as a pure API server.
  _static_dir = Path(__file__).parent.parent.parent / "static"
  if _static_dir.exists():
      app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

      @app.get("/{path:path}")
      async def spa_fallback(path: str) -> FileResponse:
          return FileResponse(str(_static_dir / "index.html"))
  ```

  > **Path note:** `Path(__file__)` = `src/d1ff/main.py`. `.parent.parent.parent` = repo root (= `/app` in Docker). So `_static_dir` = `/app/static` in Docker, which is where the Dockerfile copies the Vite `dist/`.

- [ ] **Step 2: Run the API tests to verify nothing broke**

  ```bash
  pytest tests/test_web/test_api.py -v
  ```

  Expected: All tests pass.

- [ ] **Step 3: Commit**

  ```bash
  git add src/d1ff/main.py
  git commit -m "feat: add StaticFiles mount and SPA catch-all fallback to main.py"
  ```

---

## Task 9: Update Dockerfile — add frontend build stage

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Rewrite `Dockerfile`**

  ```dockerfile
  # Stage 1: Build React SPA
  FROM node:22-alpine AS frontend-builder
  WORKDIR /frontend
  COPY frontend/package.json frontend/package-lock.json ./
  RUN npm ci
  COPY frontend/ ./
  RUN npm run build

  # Stage 2: Build Python package
  FROM python:3.12-slim AS backend-builder

  # Install uv from official image
  COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

  WORKDIR /app

  # Copy dependency files first (cache layer)
  COPY pyproject.toml uv.lock README.md ./

  # Install only runtime deps without the project itself (cache layer)
  RUN uv sync --frozen --no-dev --no-install-project

  # Copy source code and prompt templates
  COPY src/ ./src/
  COPY prompts/ ./prompts/

  # Now install the project package into the venv
  RUN uv sync --frozen --no-dev

  # Stage 3: Runtime — minimal image
  FROM python:3.12-slim AS runtime

  WORKDIR /app

  ENV PYTHONDONTWRITEBYTECODE=1 \
      PYTHONUNBUFFERED=1 \
      PATH="/app/.venv/bin:$PATH"

  # Copy venv and source from backend-builder
  COPY --from=backend-builder /app/.venv /app/.venv
  COPY --from=backend-builder /app/src /app/src
  COPY --from=backend-builder /app/prompts /app/prompts

  # Copy compiled React SPA from frontend-builder
  COPY --from=frontend-builder /frontend/dist /app/static

  # Create volume mount point for SQLite
  RUN mkdir -p /data

  ENV PORT=8000
  EXPOSE ${PORT}

  HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
      CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",8000)}/health')" || exit 1

  CMD sh -c "uvicorn d1ff.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add Dockerfile
  git commit -m "feat: add Node.js frontend build stage to Dockerfile"
  ```

---

## Task 10: Delete old Jinja2 files and tests

**Files:**
- Delete: `src/d1ff/web/templates/settings.html`
- Delete: `src/d1ff/web/templates/base.html`
- Delete: `tests/test_web/test_settings.py`
- Delete: `tests/test_web/test_settings_endpoint.py`

- [ ] **Step 1: Delete Jinja2 templates**

  ```bash
  rm src/d1ff/web/templates/settings.html
  rm src/d1ff/web/templates/base.html
  rmdir src/d1ff/web/templates
  ```

- [ ] **Step 2: Delete old test files**

  ```bash
  rm tests/test_web/test_settings.py
  rm tests/test_web/test_settings_endpoint.py
  ```

- [ ] **Step 3: Run full test suite**

  ```bash
  pytest tests/ -v
  ```

  Expected: All tests pass. No references to deleted files.

- [ ] **Step 4: Commit**

  ```bash
  git add -u
  git commit -m "chore: delete Jinja2 templates and old settings endpoint tests"
  ```

---

## Task 11: Docker build verification

- [ ] **Step 1: Build the Docker image**

  ```bash
  docker build -t d1ff:local .
  ```

  Expected: Build completes without errors. Three stages complete: `frontend-builder`, `backend-builder`, `runtime`.

- [ ] **Step 2: Verify static files are in the image**

  ```bash
  docker run --rm d1ff:local sh -c "ls /app/static && ls /app/static/assets/"
  ```

  Expected: `index.html` present in `/app/static/`, JS/CSS files in `/app/static/assets/`.

- [ ] **Step 3: Run container and check health**

  ```bash
  docker run --rm -p 8001:8000 \
    -e GITHUB_APP_ID=test \
    -e GITHUB_PRIVATE_KEY=test \
    -e GITHUB_WEBHOOK_SECRET=test \
    -e ENCRYPTION_KEY=dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldA== \
    -e GITHUB_CLIENT_ID=test \
    -e GITHUB_CLIENT_SECRET=test \
    -e SESSION_SECRET_KEY=test-session-secret-key-32-bytes!! \
    d1ff:local
  ```

  Then in another terminal:
  ```bash
  curl http://localhost:8001/health   # → {"status": "ok"}
  curl http://localhost:8001/         # → index.html (200, text/html)
  curl http://localhost:8001/settings # → index.html (200, text/html)
  curl http://localhost:8001/api/me   # → 401 {"detail": "Not authenticated"}
  ```

- [ ] **Step 4: Final commit (if any fixups needed)**

  ```bash
  git add -A
  git commit -m "fix: post-docker-build adjustments"
  ```

---

## Acceptance Criteria Checklist

- [ ] **AC1** — `docker build -t d1ff .` completes; image contains `/app/static/index.html`
- [ ] **AC2** — Browser at `/settings` renders the React settings page (authenticated)
- [ ] **AC3** — Saving settings via the React form returns `{"saved": true}` without page reload
- [ ] **AC4** — `GET /api/me` without session returns 401; React redirects to `/auth/github/login`
- [ ] **AC5** — OAuth flow completes and redirects to `/settings` (React handles that path)
- [ ] **AC6** — Dev mode: `npm run dev` proxies `/api/*` to FastAPI on port 8000
- [ ] **AC7** — `GET /health` and `POST /webhook` unaffected by SPA fallback
- [ ] **AC8** — `GET /settings` returns `index.html` (not Jinja2 HTML)
