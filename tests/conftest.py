"""Shared pytest fixtures for the d1ff test suite."""

import os

import pytest
from testcontainers.postgres import PostgresContainer

# Disable Ryuk reaper container (known issues on Windows)
os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"


@pytest.fixture(scope="session")
def _postgres_container():
    """Start a disposable PostgreSQL container for the entire test session."""
    with PostgresContainer(
        image="pgvector/pgvector:pg17",
        username="test",
        password="test",
        dbname="d1ff_test",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def postgres_url(_postgres_container) -> str:
    """Return asyncpg-compatible connection URL for the test PostgreSQL container."""
    url = _postgres_container.get_connection_url()
    # Replace driver: postgresql+psycopg2 -> postgresql+asyncpg
    url = url.replace("psycopg2", "asyncpg")
    return url
