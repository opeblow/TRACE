"""Test-wide isolation from a developer's local configuration.

Environment variables take precedence over .env files, so blanking DATABASE_URL here keeps
every test (and every subprocess it starts) away from any local database. PostgreSQL tests
opt in with TRACE_TEST_DATABASE_URL instead.
"""
import os

os.environ["DATABASE_URL"] = ""
