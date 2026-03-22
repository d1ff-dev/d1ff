# Frontend Dashboard Redesign

Redesign the frontend from a simple two-page switcher to a full dashboard application with routing, authentication flow, and sidebar navigation.

## Context

Currently `App.tsx` switches between `GetStartedPage` (unauthenticated) and `SettingsPage` (authenticated) with no URL routing. The app needs proper routes, a dashboard layout with sidebar navigation, a repositories page, and a first-run settings modal.

## Architecture

### Routing (react-router-dom)

| Path | Component | Access |
|------|-----------|--------|
| `/login` | `LoginPage` | Public |
| `/` | Redirect → `/repositories` | Protected |
| `/repositories` | `RepositoriesPage` | Protected |
| `/settings` | `SettingsPage` | Protected |
| `/account` | `AccountPage` | Protected |

### Auth Flow

1. `App.tsx` loads → calls `getMe()` → stores result in `AuthContext`
2. `AuthContext` provides `{ user, loading, hasGlobalSettings }` to the component tree
3. `<ProtectedRoute>` wraps all dashboard routes — redirects to `/login` if not authenticated
4. `LoginPage` redirects to `/repositories` if already authenticated
5. On first login (no global settings configured), `<SettingsModal>` appears over the current page

### LoginPage (`/login`)

Reuses the current `GetStartedPage` layout (hero left, card right). One route with query parameter `?mode=signin` to toggle between sign-up and sign-in text.

**Sign Up mode (default):**
- Card title: "Get started"
- Card subtitle: "Connect your GitHub or self-host on your own infrastructure. Open source, free forever."
- GitHub button: "Sign up with GitHub"
- Footer link: "Already have an account? Sign in" → `/login?mode=signin`

**Sign In mode (`?mode=signin`):**
- Card title: "Welcome back"
- Card subtitle: "Sign in to continue reviewing your code."
- GitHub button: "Sign in with GitHub"
- Footer link: "New to d1ff? Create an account" → `/login`

Both modes trigger the same OAuth flow (`/auth/github/login`). The hero section (left side) does not change between modes.

### DashboardLayout

Wraps all protected pages. Structure:
- **Sidebar** (fixed, left): logo area with username (no PRO badge), navigation items, user section
- **Main content** (right): `<Outlet>` renders the active page

**Sidebar navigation items:**
1. Repositories (icon: folder)
2. Settings (icon: gear)
3. Account (icon: user)

Active item has green highlight. Items link via react-router `<NavLink>`.

### RepositoriesPage (`/repositories`)

- Header: "Repositories" title + subtitle "List of repositories accessible to d1ff."
- Action button: "+ Add Repositories" → links to `GITHUB_APP_INSTALL_URL`
- Search input: filters repository list client-side
- Table: single column "Repository" with sort toggle, rows show repo name with folder icon
- Pagination: rows per page selector, page indicator, navigation arrows
- Data source: `GET /api/repositories`

### SettingsPage (`/settings`)

Redesigned from current installation-only view to a two-tier settings model:

**Global Default Settings (top section):**
- One form: provider, model, API key, custom endpoint
- Applies to all installations that don't have custom overrides
- Data source: `GET /api/global-settings`, `POST /api/global-settings`

**Per-Installation Overrides (below):**
- List of installations
- Each shows "Using default" or its custom configuration
- "Customize" button to set per-installation override
- "Reset to default" to remove override and fall back to global
- Data source: existing `GET /api/installations`, `POST /api/settings`

### SettingsModal

Modal overlay that appears on first login when `hasGlobalSettings === false`.

- Contains the global settings form (provider, model, API key, custom endpoint)
- Cannot be dismissed without saving (no close button, no click-outside-to-close)
- After successful save, modal closes and user sees the current page (typically `/repositories`)
- Uses the same form component as the Global Default section on SettingsPage

### AccountPage (`/account`)

- GitHub avatar (from user data or GitHub URL)
- GitHub login and display name
- "Sign out" button → `GET /logout`

## Backend Changes

### New API Endpoints

**`GET /api/repositories`**
- For each of the user's installations, fetches repository list from GitHub API
- Returns `[{ name: string, full_name: string, installation_id: number, private: boolean }]`
- In-memory cache per user with 5-minute TTL
- Cache invalidated on login (when installations are synced)

**`GET /api/global-settings`**
- Returns the user's global LLM settings: `{ provider, model, has_key, custom_endpoint }`
- Returns `404` if no global settings configured (used by frontend to trigger SettingsModal)

**`POST /api/global-settings`**
- Body: `{ provider, model, api_key, custom_endpoint }`
- Creates or updates the user's global settings
- API key is encrypted before storage (same as per-installation keys)

### Modified Endpoints

- `POST /auth/github/callback` — redirect changed from `/settings` to `/repositories`
- `GET /logout` — redirect changed from `GITHUB_APP_INSTALL_URL` to `/login`

### New Database Entity: Global Settings

Table `user_global_settings`:
- `user_id` (FK → users, unique)
- `provider` (text)
- `model` (text)
- `encrypted_api_key` (text)
- `custom_endpoint` (text, nullable)
- `created_at` (timestamp, default now)
- `updated_at` (timestamp, default now, updated on change)

### Settings Fallback Logic

When the system needs LLM settings for an installation:
1. Check if installation has its own `api_keys` row with a key for **any** provider — if yes, use that installation's config
2. If not, use the user's global settings
3. If no global settings exist, the review cannot proceed (this state is prevented by the SettingsModal on first login)

Note: per-installation override is independent of the global provider choice. An installation can use a different provider than the global default.

### Repository Data Source

The `/api/repositories` endpoint fetches live data from the GitHub API (not from the existing `repositories` database table). The DB table is used for webhook event processing; the frontend shows a live view of what the user has access to via their installations. Results are cached in-memory per user (5-minute TTL).

## New Frontend Dependencies

- `react-router-dom` (~15KB gzip) — client-side routing

## Existing Dependencies (unchanged)

- `framer-motion` — remains in use for page transitions and animations

## File Structure

```
frontend/src/
├── App.tsx                      # BrowserRouter + route definitions
├── main.tsx                     # Entry point (unchanged)
├── api.ts                       # Add getRepositories, getGlobalSettings, saveGlobalSettings
├── contexts/
│   └── AuthContext.tsx           # User state + global settings check
├── components/
│   ├── FadeIn.tsx                # Existing (unchanged)
│   ├── DashboardLayout.tsx       # Sidebar + Outlet
│   ├── Sidebar.tsx               # Navigation component
│   ├── ProtectedRoute.tsx        # Auth guard
│   └── SettingsModal.tsx         # First-run settings modal
├── pages/
│   ├── LoginPage.tsx             # Renamed from GetStartedPage, with mode param
│   ├── RepositoriesPage.tsx      # Repository table
│   ├── SettingsPage.tsx          # Redesigned: global + per-installation
│   └── AccountPage.tsx           # Profile + logout
└── globals.css                   # Existing (unchanged)
```

## Platform-Agnostic Design Notes

- UI labels say "Repositories", not "GitHub Repositories"
- Provider buttons on LoginPage are per-platform (GitHub active, GitLab with "SOON" badge)
- The installation model is generic — `account_type` field can represent GitHub org, GitLab group, etc.
- No GitHub-specific terminology in dashboard UI except login/signup buttons
