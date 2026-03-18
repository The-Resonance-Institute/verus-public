"""
Root conftest.py — fixtures available to all tests.

Path management is handled by pyproject.toml [tool.pytest.ini_options] pythonpath = ["."]
No sys.path manipulation needed here.

NOTE ON DATABASE USERS:
  verus       — superuser, used for migrations and schema changes only
                (superusers bypass RLS — never use for application queries)
  verus_app   — non-superuser application role, used for all test queries
                (RLS policies are enforced for this role)

Database URLs are read from environment variables so they work in any
environment (local, Docker, CI). Defaults point at the local test database.
"""
import os

os.environ.setdefault("ENVIRONMENT", "test")

# Application database URL — uses non-superuser role so RLS is enforced
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://verus_app:verus_app@127.0.0.1:5432/verus_test"
)

# Migration database URL — uses superuser role
os.environ.setdefault(
    "DATABASE_MIGRATION_URL",
    "postgresql://verus:verus@127.0.0.1:5432/verus_test"
)
