# Frontend Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the frontend from a two-page switcher into a routed dashboard with sidebar navigation, login/signup flow, repositories page, global settings, and first-run settings modal.

**Architecture:** React Router for client-side routing, AuthContext for auth state, DashboardLayout with sidebar wrapping protected pages. Backend adds global settings table, repositories API (in-memory cached), and global-settings CRUD endpoints.

**Tech Stack:** React 19, react-router-dom, TypeScript, Tailwind CSS 4, framer-motion, FastAPI, aiosqlite

**Spec:** `docs/superpowers/specs/2026-03-22-frontend-dashboard-redesign-design.md`

---

## File Structure

### Backend (new/modified)

| File | Action | Responsibility |
|------|--------|---------------|
| `src/d1ff/storage/database.py` | Modify | Add `user_global_settings` table |
| `src/d1ff/storage/global_settings_repo.py` | Create | CRUD for global settings |
| `src/d1ff/web/api.py` | Modify | Add `/api/global-settings` and `/api/repositories` endpoints |
| `src/d1ff/web/repo_cache.py` | Create | In-memory repository cache with TTL |
| `src/d1ff/web/router.py` | Modify | Change redirect URLs |
| `tests/test_web/test_api.py` | Modify | Add tests for new endpoints |
| `tests/test_storage/test_global_settings_repo.py` | Create | Tests for global settings repo |
| `tests/test_web/test_repo_cache.py` | Create | Tests for repo cache |

### Frontend (new/modified)

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/package.json` | Modify | Add react-router-dom |
| `frontend/src/api.ts` | Modify | Add new API functions |
| `frontend/src/App.tsx` | Rewrite | BrowserRouter + route definitions |
| `frontend/src/contexts/AuthContext.tsx` | Create | Auth state provider |
| `frontend/src/components/ProtectedRoute.tsx` | Create | Auth guard wrapper |
| `frontend/src/components/DashboardLayout.tsx` | Create | Sidebar + Outlet |
| `frontend/src/components/Sidebar.tsx` | Create | Navigation sidebar |
| `frontend/src/components/SettingsModal.tsx` | Create | First-run global settings modal |
| `frontend/src/components/GlobalSettingsForm.tsx` | Create | Shared settings form |
| `frontend/src/pages/LoginPage.tsx` | Create | Renamed GetStartedPage with mode toggle |
| `frontend/src/pages/RepositoriesPage.tsx` | Create | Repository table page |
| `frontend/src/pages/SettingsPage.tsx` | Rewrite | Global + per-installation settings |
| `frontend/src/pages/AccountPage.tsx` | Create | Profile + logout |

---

## Task 1: Backend — Global Settings Database Table

**Files:**
- Modify: `src/d1ff/storage/database.py:91-122`

- [ ] **Step 1: Add user_global_settings table to init_db**

In `src/d1ff/storage/database.py`, add after the `user_installations` table creation (line 112) and before the migration block (line 114):

```python
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_global_settings (
                user_id          INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                provider         TEXT NOT NULL,
                model            TEXT NOT NULL,
                encrypted_api_key TEXT NOT NULL,
                custom_endpoint  TEXT,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            )
            """
        )
```

- [ ] **Step 2: Run existing database tests to verify no regression**

Run: `cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff && uv run pytest tests/test_storage/test_database.py -v`
Expected: All existing tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/d1ff/storage/database.py
git commit -m "feat: add user_global_settings table to database schema"
```

---

## Task 2: Backend — Global Settings Repository

**Files:**
- Create: `src/d1ff/storage/global_settings_repo.py`
- Create: `tests/test_storage/test_global_settings_repo.py`

- [ ] **Step 1: Write tests for global settings repo**

Create `tests/test_storage/test_global_settings_repo.py`:

```python
"""Tests for global settings repository."""

import aiosqlite
import pytest

from d1ff.storage.database import init_db
from d1ff.storage.global_settings_repo import GlobalSettingsRepository


@pytest.fixture
async def db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = aiosqlite.Row
    await init_db("sqlite+aiosqlite:///:memory:", _conn_override=conn)
    # Insert a test user
    await conn.execute(
        "INSERT INTO users (github_id, login, encrypted_token, created_at, updated_at) "
        "VALUES (1, 'testuser', 'enc-token', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')"
    )
    await conn.commit()
    yield conn
    await conn.close()


async def test_get_returns_none_when_no_settings(db: aiosqlite.Connection) -> None:
    repo = GlobalSettingsRepository(db)
    result = await repo.get(user_id=1)
    assert result is None


async def test_upsert_and_get(db: aiosqlite.Connection) -> None:
    repo = GlobalSettingsRepository(db)
    await repo.upsert(
        user_id=1,
        provider="openai",
        model="gpt-4o",
        encrypted_api_key="encrypted-key-value",
        custom_endpoint=None,
    )
    result = await repo.get(user_id=1)
    assert result is not None
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o"
    assert result["encrypted_api_key"] == "encrypted-key-value"
    assert result["custom_endpoint"] is None


async def test_upsert_updates_existing(db: aiosqlite.Connection) -> None:
    repo = GlobalSettingsRepository(db)
    await repo.upsert(user_id=1, provider="openai", model="gpt-4o",
                       encrypted_api_key="key1", custom_endpoint=None)
    await repo.upsert(user_id=1, provider="anthropic", model="claude-opus-4-5",
                       encrypted_api_key="key2", custom_endpoint="https://custom.api")
    result = await repo.get(user_id=1)
    assert result["provider"] == "anthropic"
    assert result["model"] == "claude-opus-4-5"
    assert result["custom_endpoint"] == "https://custom.api"


async def test_has_settings(db: aiosqlite.Connection) -> None:
    repo = GlobalSettingsRepository(db)
    assert await repo.has_settings(user_id=1) is False
    await repo.upsert(user_id=1, provider="openai", model="gpt-4o",
                       encrypted_api_key="key1", custom_endpoint=None)
    assert await repo.has_settings(user_id=1) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_storage/test_global_settings_repo.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement GlobalSettingsRepository**

Create `src/d1ff/storage/global_settings_repo.py`:

```python
"""Repository for user global LLM settings."""

from datetime import UTC, datetime

import aiosqlite


class GlobalSettingsRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get(self, user_id: int) -> dict[str, str | None] | None:
        cursor = await self._db.execute(
            "SELECT provider, model, encrypted_api_key, custom_endpoint "
            "FROM user_global_settings WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "provider": row["provider"],
            "model": row["model"],
            "encrypted_api_key": row["encrypted_api_key"],
            "custom_endpoint": row["custom_endpoint"],
        }

    async def has_settings(self, user_id: int) -> bool:
        cursor = await self._db.execute(
            "SELECT 1 FROM user_global_settings WHERE user_id = ?",
            (user_id,),
        )
        return await cursor.fetchone() is not None

    async def upsert(
        self,
        user_id: int,
        provider: str,
        model: str,
        encrypted_api_key: str,
        custom_endpoint: str | None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        await self._db.execute(
            """
            INSERT INTO user_global_settings
                (user_id, provider, model, encrypted_api_key, custom_endpoint, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id) DO UPDATE SET
                provider = excluded.provider,
                model = excluded.model,
                encrypted_api_key = excluded.encrypted_api_key,
                custom_endpoint = excluded.custom_endpoint,
                updated_at = excluded.updated_at
            """,
            (user_id, provider, model, encrypted_api_key, custom_endpoint, now, now),
        )
        await self._db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_storage/test_global_settings_repo.py -v`
Expected: All PASS

Note: The `init_db` function may need a `_conn_override` parameter for testing. If it doesn't exist, modify `init_db` to accept an optional connection. Check existing tests in `tests/test_storage/test_database.py` for the pattern used.

- [ ] **Step 5: Commit**

```bash
git add src/d1ff/storage/global_settings_repo.py tests/test_storage/test_global_settings_repo.py
git commit -m "feat: add GlobalSettingsRepository with CRUD for user global LLM settings"
```

---

## Task 3: Backend — In-Memory Repository Cache

**Files:**
- Create: `src/d1ff/web/repo_cache.py`
- Create: `tests/test_web/test_repo_cache.py`

- [ ] **Step 1: Write tests for the repo cache**

Create `tests/test_web/test_repo_cache.py`:

```python
"""Tests for in-memory repository cache."""

import time

from d1ff.web.repo_cache import RepoCache


def test_get_returns_none_for_missing_key() -> None:
    cache = RepoCache(ttl_seconds=300)
    assert cache.get(user_id=1) is None


def test_set_and_get() -> None:
    cache = RepoCache(ttl_seconds=300)
    repos = [{"name": "repo1", "full_name": "org/repo1", "installation_id": 1, "private": False}]
    cache.set(user_id=1, repos=repos)
    result = cache.get(user_id=1)
    assert result == repos


def test_expired_entry_returns_none() -> None:
    cache = RepoCache(ttl_seconds=0)  # immediate expiry
    cache.set(user_id=1, repos=[{"name": "repo1"}])
    time.sleep(0.01)
    assert cache.get(user_id=1) is None


def test_invalidate() -> None:
    cache = RepoCache(ttl_seconds=300)
    cache.set(user_id=1, repos=[{"name": "repo1"}])
    cache.invalidate(user_id=1)
    assert cache.get(user_id=1) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web/test_repo_cache.py -v`
Expected: FAIL

- [ ] **Step 3: Implement RepoCache**

Create `src/d1ff/web/repo_cache.py`:

```python
"""In-memory cache for repository listings with TTL."""

import time
from typing import Any


class RepoCache:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._store: dict[int, tuple[float, list[dict[str, Any]]]] = {}

    def get(self, user_id: int) -> list[dict[str, Any]] | None:
        entry = self._store.get(user_id)
        if entry is None:
            return None
        timestamp, repos = entry
        if time.monotonic() - timestamp > self._ttl:
            del self._store[user_id]
            return None
        return repos

    def set(self, user_id: int, repos: list[dict[str, Any]]) -> None:
        self._store[user_id] = (time.monotonic(), repos)

    def invalidate(self, user_id: int) -> None:
        self._store.pop(user_id, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web/test_repo_cache.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/d1ff/web/repo_cache.py tests/test_web/test_repo_cache.py
git commit -m "feat: add in-memory RepoCache with TTL for repository listings"
```

---

## Task 4: Backend — Global Settings API Endpoints

**Files:**
- Modify: `src/d1ff/web/api.py`
- Modify: `tests/test_web/test_api.py`

- [ ] **Step 1: Write tests for GET /api/global-settings**

Add to `tests/test_web/test_api.py`:

```python
# ---------------------------------------------------------------------------
# GET /api/global-settings
# ---------------------------------------------------------------------------

async def test_get_global_settings_unauthenticated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/global-settings")
    assert response.status_code == 401


async def test_get_global_settings_not_configured(session_cookie: str) -> None:
    with patch(
        "d1ff.web.api.GlobalSettingsRepository.get",
        new=AsyncMock(return_value=None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.get("/api/global-settings")
    assert response.status_code == 404


async def test_get_global_settings_returns_config(session_cookie: str) -> None:
    fake_settings = {
        "provider": "anthropic",
        "model": "claude-opus-4-5",
        "encrypted_api_key": "enc-key",
        "custom_endpoint": None,
    }
    with patch(
        "d1ff.web.api.GlobalSettingsRepository.get",
        new=AsyncMock(return_value=fake_settings),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.get("/api/global-settings")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "anthropic"
    assert data["has_key"] is True
    assert "encrypted_api_key" not in data
```

- [ ] **Step 2: Write tests for POST /api/global-settings**

Add to `tests/test_web/test_api.py`:

```python
# ---------------------------------------------------------------------------
# POST /api/global-settings
# ---------------------------------------------------------------------------

async def test_post_global_settings_unauthenticated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/global-settings", json={
            "provider": "openai", "model": "gpt-4o", "api_key": "sk-test", "custom_endpoint": "",
        })
    assert response.status_code == 401


async def test_post_global_settings_saves(session_cookie: str) -> None:
    mock_upsert = AsyncMock()
    with patch("d1ff.web.api.GlobalSettingsRepository.upsert", mock_upsert):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.post("/api/global-settings", json={
                "provider": "openai", "model": "gpt-4o",
                "api_key": "sk-test-key", "custom_endpoint": "",
            })
    assert response.status_code == 200
    assert response.json() == {"saved": True}
    mock_upsert.assert_called_once()


async def test_post_global_settings_invalid_provider(session_cookie: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("session", session_cookie)
        response = await client.post("/api/global-settings", json={
            "provider": "badprovider", "model": "m", "api_key": "k", "custom_endpoint": "",
        })
    assert response.status_code == 400
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_web/test_api.py -k "global_settings" -v`
Expected: FAIL

- [ ] **Step 4: Implement the endpoints in api.py**

Add to `src/d1ff/web/api.py`:

1. Add import at top:
```python
from d1ff.config import get_settings
from d1ff.storage.encryption import encrypt_value
from d1ff.storage.global_settings_repo import GlobalSettingsRepository
```

2. Add the request model:
```python
class GlobalSettingsRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    custom_endpoint: str = ""
```

3. Add the endpoints:
```python
@router.get("/global-settings")
async def get_global_settings(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),
) -> dict[str, str | bool | None]:
    user = _get_session_user(request)
    repo = GlobalSettingsRepository(db)
    settings = await repo.get(user_id=int(user["user_id"]))
    if settings is None:
        raise HTTPException(status_code=404, detail="Global settings not configured")
    return {
        "provider": settings["provider"],
        "model": settings["model"],
        "has_key": bool(settings["encrypted_api_key"]),
        "custom_endpoint": settings["custom_endpoint"],
    }


@router.post("/global-settings")
async def update_global_settings(
    request: Request,
    body: GlobalSettingsRequest,
    db: aiosqlite.Connection = Depends(get_db_connection),
) -> dict[str, bool]:
    user = _get_session_user(request)
    if body.provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {body.provider}")
    endpoint = body.custom_endpoint.strip() or None
    if endpoint and not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        raise HTTPException(status_code=400, detail="Custom endpoint must start with http:// or https://")
    settings = get_settings()
    encrypted_key = encrypt_value(body.api_key, settings.ENCRYPTION_KEY)
    repo = GlobalSettingsRepository(db)
    await repo.upsert(
        user_id=int(user["user_id"]),
        provider=body.provider,
        model=body.model,
        encrypted_api_key=encrypted_key,
        custom_endpoint=endpoint,
    )
    logger.info("global_settings_saved", user_id=user["user_id"], provider=body.provider)
    return {"saved": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_web/test_api.py -v`
Expected: All PASS (old + new)

- [ ] **Step 6: Commit**

```bash
git add src/d1ff/web/api.py tests/test_web/test_api.py
git commit -m "feat: add GET/POST /api/global-settings endpoints"
```

---

## Task 5: Backend — Repositories API Endpoint

**Files:**
- Modify: `src/d1ff/web/api.py`
- Modify: `src/d1ff/main.py:27-42` (add cache to app.state)
- Modify: `tests/test_web/test_api.py`

- [ ] **Step 1: Write tests for GET /api/repositories**

Add to `tests/test_web/test_api.py`:

```python
# ---------------------------------------------------------------------------
# GET /api/repositories
# ---------------------------------------------------------------------------

async def test_get_repositories_unauthenticated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/repositories")
    assert response.status_code == 401


async def test_get_repositories_returns_list(session_cookie: str) -> None:
    fake_repos_response = {
        "repositories": [
            {"name": "repo1", "full_name": "org/repo1", "private": False},
            {"name": "repo2", "full_name": "org/repo2", "private": True},
        ]
    }
    mock_github_get = AsyncMock()
    mock_github_get.return_value.status_code = 200
    mock_github_get.return_value.json.return_value = fake_repos_response

    with (
        patch(
            "d1ff.web.api.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
        patch("d1ff.web.api.oauth.github.get", mock_github_get),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.get("/api/repositories")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "repo1"
    assert data[0]["installation_id"] == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_web/test_api.py::test_get_repositories_returns_list -v`
Expected: FAIL

- [ ] **Step 3: Initialize RepoCache in main.py lifespan**

In `src/d1ff/main.py`, add import and initialize cache in lifespan:

```python
from d1ff.web.repo_cache import RepoCache
```

Inside `lifespan()`, before `yield`:
```python
    app.state.repo_cache = RepoCache(ttl_seconds=300)
```

- [ ] **Step 4: Implement GET /api/repositories in api.py**

Add to `src/d1ff/web/api.py`:

```python
from d1ff.github.oauth_handler import oauth
from d1ff.web.repo_cache import RepoCache
```

```python
@router.get("/repositories")
async def get_repositories(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),
) -> list[dict[str, object]]:
    user = _get_session_user(request)
    user_id = int(user["user_id"])

    # Check cache first
    cache: RepoCache = request.app.state.repo_cache
    cached = cache.get(user_id=user_id)
    if cached is not None:
        return cached

    repo = InstallationRepository(db)
    installations = await repo.list_installations_for_user(user_id)

    # Fetch user's GitHub token from session to make API calls
    token = {"access_token": "", "token_type": "bearer"}
    # We need the user's OAuth token — retrieve from DB
    cursor = await db.execute(
        "SELECT encrypted_token FROM users WHERE id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="User record not found")

    from d1ff.storage.encryption import decrypt_value
    settings = get_settings()
    access_token = decrypt_value(row["encrypted_token"], settings.ENCRYPTION_KEY)
    token["access_token"] = access_token

    all_repos: list[dict[str, object]] = []
    for inst in installations:
        page = 1
        while True:
            resp = await oauth.github.get(
                f"user/installations/{inst.installation_id}/repositories",
                token=token,
                params={"per_page": 100, "page": page},
            )
            if resp.status_code != 200:
                logger.warning("github_repos_fetch_failed",
                               installation_id=inst.installation_id,
                               status=resp.status_code)
                break
            data = resp.json()
            repos = data.get("repositories", [])
            for r in repos:
                all_repos.append({
                    "name": r["name"],
                    "full_name": r["full_name"],
                    "installation_id": inst.installation_id,
                    "private": r.get("private", False),
                })
            if len(repos) < 100:
                break
            page += 1

    cache.set(user_id=user_id, repos=all_repos)
    return all_repos
```

- [ ] **Step 5: Run all API tests**

Run: `uv run pytest tests/test_web/test_api.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/d1ff/web/api.py src/d1ff/main.py tests/test_web/test_api.py
git commit -m "feat: add GET /api/repositories with in-memory cache"
```

---

## Task 6: Backend — Update Redirect URLs

**Files:**
- Modify: `src/d1ff/web/router.py:94,103`

- [ ] **Step 1: Change OAuth callback redirect**

In `src/d1ff/web/router.py` line 94, change:
```python
    return RedirectResponse(url="/settings", status_code=302)
```
to:
```python
    return RedirectResponse(url="/repositories", status_code=302)
```

- [ ] **Step 2: Change logout redirect**

In `src/d1ff/web/router.py` line 103, change:
```python
    return RedirectResponse(url=get_settings().GITHUB_APP_INSTALL_URL, status_code=302)
```
to:
```python
    return RedirectResponse(url="/login", status_code=302)
```

- [ ] **Step 3: Run web tests to verify no regression**

Run: `uv run pytest tests/test_web/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/d1ff/web/router.py
git commit -m "feat: update OAuth callback redirect to /repositories, logout to /login"
```

---

## Task 7: Backend — Add hasGlobalSettings to /api/me

**Files:**
- Modify: `src/d1ff/web/api.py:37-40`
- Modify: `tests/test_web/test_api.py`

- [ ] **Step 1: Write test**

Add to `tests/test_web/test_api.py`:

```python
async def test_get_me_includes_has_global_settings(session_cookie: str) -> None:
    with patch(
        "d1ff.web.api.GlobalSettingsRepository.has_settings",
        new=AsyncMock(return_value=True),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.get("/api/me")
    assert response.status_code == 200
    data = response.json()
    assert data["hasGlobalSettings"] is True
```

- [ ] **Step 2: Update GET /api/me to include hasGlobalSettings**

In `src/d1ff/web/api.py`, modify `get_me`:

```python
@router.get("/me")
async def get_me(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),
) -> dict[str, object]:
    """Return current authenticated user from session."""
    user = _get_session_user(request)
    repo = GlobalSettingsRepository(db)
    has_settings = await repo.has_settings(user_id=int(user["user_id"]))
    return {**user, "hasGlobalSettings": has_settings}
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_web/test_api.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/d1ff/web/api.py tests/test_web/test_api.py
git commit -m "feat: include hasGlobalSettings flag in GET /api/me response"
```

---

## Task 8: Frontend — Install react-router-dom

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install dependency**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npm install react-router-dom
```

- [ ] **Step 2: Verify installation**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npm ls react-router-dom
```
Expected: react-router-dom listed

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: add react-router-dom dependency"
```

---

## Task 9: Frontend — API Functions

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Update User type to include hasGlobalSettings**

In `frontend/src/api.ts`, modify the `User` interface:

```typescript
export interface User {
  login: string
  name: string | null
  github_id: number
  user_id: number
  hasGlobalSettings: boolean
}
```

- [ ] **Step 2: Add new API types**

Add to `frontend/src/api.ts`:

```typescript
export interface Repository {
  name: string
  full_name: string
  installation_id: number
  private: boolean
}

export interface GlobalSettings {
  provider: string
  model: string
  has_key: boolean
  custom_endpoint: string | null
}

export interface GlobalSettingsPayload {
  provider: string
  model: string
  api_key: string
  custom_endpoint: string
}
```

- [ ] **Step 3: Add new API functions**

Add to `frontend/src/api.ts`:

```typescript
export function getRepositories(): Promise<Repository[]> {
  return apiFetch<Repository[]>('/api/repositories')
}

export function getGlobalSettings(): Promise<GlobalSettings> {
  return apiFetch<GlobalSettings>('/api/global-settings')
}

export function saveGlobalSettings(payload: GlobalSettingsPayload): Promise<{ saved: boolean }> {
  return apiFetch<{ saved: boolean }>('/api/global-settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
```

- [ ] **Step 4: Update 401 redirect to /login**

In `apiFetch`, change the 401 handler:

```typescript
  if (res.status === 401) {
    window.location.href = '/login'
    throw new Error('Not authenticated')
  }
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add API types and functions for repositories and global settings"
```

---

## Task 10: Frontend — AuthContext

**Files:**
- Create: `frontend/src/contexts/AuthContext.tsx`

- [ ] **Step 1: Create AuthContext**

Create `frontend/src/contexts/AuthContext.tsx`:

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getMe, type User } from '../api'

interface AuthState {
  user: User | null
  loading: boolean
  hasGlobalSettings: boolean
  setHasGlobalSettings: (v: boolean) => void
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  hasGlobalSettings: false,
  setHasGlobalSettings: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [hasGlobalSettings, setHasGlobalSettings] = useState(false)

  useEffect(() => {
    getMe()
      .then((u) => {
        setUser(u)
        setHasGlobalSettings(u.hasGlobalSettings)
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, hasGlobalSettings, setHasGlobalSettings }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/contexts/AuthContext.tsx
git commit -m "feat: add AuthContext with user state and global settings check"
```

---

## Task 11: Frontend — ProtectedRoute

**Files:**
- Create: `frontend/src/components/ProtectedRoute.tsx`

- [ ] **Step 1: Create ProtectedRoute component**

Create `frontend/src/components/ProtectedRoute.tsx`:

```tsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <span className="font-mono text-sm text-fg-muted">Loading…</span>
      </div>
    )
  }

  return user ? <Outlet /> : <Navigate to="/login" replace />
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ProtectedRoute.tsx
git commit -m "feat: add ProtectedRoute auth guard component"
```

---

## Task 12: Frontend — Sidebar

**Files:**
- Create: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Create Sidebar component**

Create `frontend/src/components/Sidebar.tsx`:

```tsx
import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

function FolderIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 20h16a2 2 0 002-2V8a2 2 0 00-2-2h-7.93a2 2 0 01-1.66-.9l-.82-1.2A2 2 0 007.93 3H4a2 2 0 00-2 2v13a2 2 0 002 2z" />
    </svg>
  )
}

function GearIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  )
}

function UserIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  )
}

const NAV_ITEMS = [
  { to: '/repositories', label: 'Repositories', icon: FolderIcon },
  { to: '/settings', label: 'Settings', icon: GearIcon },
  { to: '/account', label: 'Account', icon: UserIcon },
]

export default function Sidebar() {
  const { user } = useAuth()

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-border bg-bg">
      {/* Logo + user */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <span className="font-mono text-sm font-bold text-fg">{user?.login}</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded px-3 py-2 font-mono text-sm transition-colors ${
                isActive
                  ? 'bg-green/10 text-fg'
                  : 'text-fg-muted hover:text-fg'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className={isActive ? 'text-green' : ''}>
                  <Icon />
                </span>
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat: add Sidebar navigation component"
```

---

## Task 13: Frontend — DashboardLayout + SettingsModal

**Files:**
- Create: `frontend/src/components/DashboardLayout.tsx`
- Create: `frontend/src/components/GlobalSettingsForm.tsx`
- Create: `frontend/src/components/SettingsModal.tsx`

- [ ] **Step 1: Create GlobalSettingsForm (shared form)**

Create `frontend/src/components/GlobalSettingsForm.tsx`:

```tsx
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
  const [model, setModel] = useState(initial?.model || '')
  const [apiKey, setApiKey] = useState('')
  const [endpoint, setEndpoint] = useState(initial?.custom_endpoint || '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await saveGlobalSettings({
        provider,
        model,
        api_key: apiKey,
        custom_endpoint: endpoint,
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
        <label className="mb-1.5 block font-mono text-xs text-fg-muted">Model</label>
        <input
          type="text"
          value={model}
          onChange={e => setModel(e.target.value)}
          placeholder="e.g. gpt-4o, claude-opus-4-5, gemini-pro"
          required
          className="w-full border border-border bg-bg-elevated px-4 py-2.5 font-mono text-sm text-fg placeholder:text-fg-dim outline-none transition-colors focus:border-green/50"
        />
      </div>
      <div>
        <label className="mb-1.5 block font-mono text-xs text-fg-muted">
          Custom LLM Endpoint <span className="ml-2 text-fg-dim">(optional)</span>
        </label>
        <input
          type="url"
          value={endpoint}
          onChange={e => setEndpoint(e.target.value)}
          placeholder="https://my-azure-openai.openai.azure.com"
          autoComplete="off"
          className="w-full border border-border bg-bg-elevated px-4 py-2.5 font-mono text-sm text-fg placeholder:text-fg-dim outline-none transition-colors focus:border-green/50"
        />
      </div>
      <div>
        <label className="mb-1.5 block font-mono text-xs text-fg-muted">API Key</label>
        <input
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder={initial?.has_key ? 'Key saved — enter new key to update' : 'Enter your API key'}
          required={!initial?.has_key}
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
```

- [ ] **Step 2: Create SettingsModal**

Create `frontend/src/components/SettingsModal.tsx`:

```tsx
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
```

- [ ] **Step 3: Create DashboardLayout**

Create `frontend/src/components/DashboardLayout.tsx`:

```tsx
import { Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from './Sidebar'
import SettingsModal from './SettingsModal'

export default function DashboardLayout() {
  const { hasGlobalSettings, setHasGlobalSettings } = useAuth()

  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      {!hasGlobalSettings && (
        <SettingsModal onSaved={() => setHasGlobalSettings(true)} />
      )}
    </div>
  )
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/GlobalSettingsForm.tsx frontend/src/components/SettingsModal.tsx frontend/src/components/DashboardLayout.tsx
git commit -m "feat: add DashboardLayout, GlobalSettingsForm, and SettingsModal components"
```

---

## Task 14: Frontend — LoginPage

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Delete: `frontend/src/pages/GetStartedPage.tsx` (after LoginPage is working)

- [ ] **Step 1: Create LoginPage**

Create `frontend/src/pages/LoginPage.tsx`. This is the current `GetStartedPage.tsx` with these changes:
1. Import `useSearchParams`, `Navigate` from react-router-dom
2. Import `useAuth` from AuthContext
3. If user is authenticated, `<Navigate to="/repositories" replace />`
4. Read `mode` from search params — if `signin`, show sign-in text; otherwise show sign-up text
5. Add toggle link at the bottom of the card
6. Keep all existing icons, BackgroundLines, hero section, and styling unchanged

The card text changes based on mode (see spec for exact strings). The hero section (left) stays the same.

Key additions to the card:
- Footer link: toggles between modes
- Text variations based on `mode === 'signin'`

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx
git commit -m "feat: add LoginPage with sign-up/sign-in mode toggle"
```

---

## Task 15: Frontend — RepositoriesPage

**Files:**
- Create: `frontend/src/pages/RepositoriesPage.tsx`

- [ ] **Step 1: Create RepositoriesPage**

Create `frontend/src/pages/RepositoriesPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { getRepositories, type Repository } from '../api'

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50]

export default function RepositoriesPage() {
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

  const filtered = repos
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
            href="https://github.com/apps/d1ff-app/installations/new"
            target="_blank"
            rel="noopener noreferrer"
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
              className="bg-transparent text-fg outline-none"
            >
              {ROWS_PER_PAGE_OPTIONS.map(n => <option key={n} value={n}>{n}</option>)}
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
```

Note: The "+ Add Repositories" button should link to the GitHub App install URL. Since this URL comes from backend config, we can either hardcode `https://github.com/apps/d1ff-app/installations/new` or fetch it from an API. For now, hardcode it — the spec says it links to `GITHUB_APP_INSTALL_URL`. If the app slug changes, update this link. Alternative: add a `/api/config` endpoint that returns public config. For MVP, hardcode is fine.

Update the `href` to: `https://github.com/apps/d1ff-app/installations/new`

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/RepositoriesPage.tsx
git commit -m "feat: add RepositoriesPage with search, sort, and pagination"
```

---

## Task 16: Frontend — SettingsPage Redesign

**Files:**
- Rewrite: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Rewrite SettingsPage**

Rewrite `frontend/src/pages/SettingsPage.tsx` to show:

1. **Global Default Settings section** — uses `GlobalSettingsForm` with data from `getGlobalSettings()`
2. **Per-Installation Overrides section** — list of installations from `getInstallations()`, each showing "Using default" badge or its custom config, with "Customize"/"Reset to default" buttons

The page layout:
- Top: `// SETTINGS` label, "Settings" title, subtitle
- Global settings card with `GlobalSettingsForm`
- Installations list below, each as a card showing account_login and config status

Keep the existing styling patterns (font-mono, border-border, bg-bg-card, etc.) and framer-motion animations.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: redesign SettingsPage with global defaults and per-installation overrides"
```

---

## Task 17: Frontend — AccountPage

**Files:**
- Create: `frontend/src/pages/AccountPage.tsx`

- [ ] **Step 1: Create AccountPage**

Create `frontend/src/pages/AccountPage.tsx`:

```tsx
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
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AccountPage.tsx
git commit -m "feat: add AccountPage with profile and sign out"
```

---

## Task 18: Frontend — App.tsx Router + Cleanup

**Files:**
- Rewrite: `frontend/src/App.tsx`
- Delete: `frontend/src/pages/GetStartedPage.tsx`

- [ ] **Step 1: Rewrite App.tsx with BrowserRouter**

Rewrite `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import DashboardLayout from './components/DashboardLayout'
import LoginPage from './pages/LoginPage'
import RepositoriesPage from './pages/RepositoriesPage'
import SettingsPage from './pages/SettingsPage'
import AccountPage from './pages/AccountPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<DashboardLayout />}>
              <Route path="/repositories" element={<RepositoriesPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/account" element={<AccountPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/repositories" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

- [ ] **Step 2: Delete GetStartedPage.tsx**

Delete `frontend/src/pages/GetStartedPage.tsx` — its functionality is now in `LoginPage.tsx`.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Verify build succeeds**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git rm frontend/src/pages/GetStartedPage.tsx
git commit -m "feat: rewrite App.tsx with BrowserRouter, delete GetStartedPage"
```

---

## Task 19: End-to-End Verification

- [ ] **Step 1: Run all backend tests**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff && uv run pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 2: Run frontend build**

```bash
cd /c/Users/mensh/OneDrive/Документы/GitHub/d1ff/frontend && npm run build
```
Expected: Build succeeds with no errors

- [ ] **Step 3: Manual smoke test (if dev server is available)**

Start backend: `uv run uvicorn d1ff.main:app --reload`
Start frontend: `cd frontend && npm run dev`

Verify:
1. `/login` shows login page with sign-up card
2. `/login?mode=signin` shows sign-in card text
3. Unauthenticated access to `/repositories` redirects to `/login`
4. After GitHub login, redirects to `/repositories`
5. Sidebar navigation works between all pages
6. First-time user sees SettingsModal overlay
7. After saving settings, modal closes

- [ ] **Step 4: Final commit if any fixes needed**
