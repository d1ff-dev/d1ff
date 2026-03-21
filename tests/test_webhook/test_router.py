"""Integration tests for the POST /webhook/github endpoint."""

import hashlib
import hmac
import json
from pathlib import Path

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from d1ff.config import get_settings
from d1ff.main import app
from d1ff.storage.database import get_db_connection, init_db

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "webhooks"

WEBHOOK_SECRET = "test-secret-router"


def _make_sig(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _load_fixture(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


@pytest.fixture
async def db_conn(tmp_path):  # type: ignore[no-untyped-def]
    """In-memory aiosqlite connection with schema initialized."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test_router.db"
    await init_db(db_url)
    async with aiosqlite.connect(f"{tmp_path}/test_router.db") as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


@pytest.fixture
def override_settings(monkeypatch):  # type: ignore[no-untyped-def]
    """Override AppSettings so the webhook secret matches our test constant."""
    get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "fake-pem-key")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldA==")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret-key-32-bytes!!")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_client(override_settings, db_conn):  # type: ignore[no-untyped-def]
    """AsyncClient wired to the FastAPI app with DI overrides."""
    async def _get_db_override() -> aiosqlite.Connection:  # type: ignore[return]
        yield db_conn

    app.dependency_overrides[get_db_connection] = _get_db_override
    yield
    app.dependency_overrides.clear()


async def test_valid_webhook_returns_202(test_client, db_conn) -> None:  # type: ignore[no-untyped-def]
    payload = b'{"action": "ping"}'
    sig = _make_sig(payload, WEBHOOK_SECRET)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-001",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 202


async def test_invalid_signature_returns_401(test_client, db_conn) -> None:  # type: ignore[no-untyped-def]
    payload = b'{"action": "ping"}'
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": "sha256=badhash",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-002",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 401


async def test_missing_signature_returns_401(test_client, db_conn) -> None:  # type: ignore[no-untyped-def]
    payload = b'{"action": "ping"}'
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload,
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-003",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 401


async def test_installation_event_stored(test_client, db_conn, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """POST installation.created event → installation ID persisted in DB."""
    payload_bytes = _load_fixture("installation_created.json")
    sig = _make_sig(payload_bytes, WEBHOOK_SECRET)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload_bytes,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "installation",
                "X-GitHub-Delivery": "test-delivery-004",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 202

    # Verify installation was persisted
    async with db_conn.execute(
        "SELECT installation_id FROM installations WHERE installation_id = ?", (42000001,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None
    assert int(row[0]) == 42000001


async def test_ping_event_returns_pong(test_client, db_conn) -> None:  # type: ignore[no-untyped-def]
    payload = json.dumps({"zen": "Keep it logically awesome.", "hook_id": 99}).encode()
    sig = _make_sig(payload, WEBHOOK_SECRET)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "ping",
                "X-GitHub-Delivery": "test-delivery-005",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "pong"}
