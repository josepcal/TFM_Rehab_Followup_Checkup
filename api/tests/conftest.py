"""Shared pytest configuration for isolated API unit tests.

The default test suite must not require a running PostgreSQL instance.
Tests that need persistence should provide their own explicit fake/session.
"""

import pytest


@pytest.fixture
def db():
    class NoDatabaseSession:
        def __getattr__(self, name):
            raise AssertionError(f"Unexpected database access in isolated unit test: {name}")

    return NoDatabaseSession()
