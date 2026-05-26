from __future__ import annotations

import unittest

from app.core.config import Settings

REAL_DB = "postgresql+asyncpg://u:p@h:5432/db"
REAL_ISSUER = "https://real-app.clerk.accounts.dev"
REAL_AUDIENCE = "https://app.example.com"


class FailFastOnProductionPlaceholdersTests(unittest.TestCase):
    """Production refuses to boot with a placeholder DB URL or unconfigured auth;
    development keeps working regardless (current config contract — Clerk-based,
    no Supabase/JWT secret fields)."""

    def _load(self, **overrides) -> Settings:
        # `_env_file=None` bypasses .env so each test is hermetic against the dev .env.
        kwargs: dict = {
            "_env_file": None,
            "DATABASE_URL": REAL_DB,
            "CLERK_ISSUER": REAL_ISSUER,
            "CLERK_AUDIENCE": REAL_AUDIENCE,
        }
        kwargs.update(overrides)
        return Settings(**kwargs)

    # --- dev passes regardless of placeholders / missing auth --------------

    def test_dev_with_all_real_values_loads(self):
        self.assertEqual(self._load(ENVIRONMENT="development").environment, "development")

    def test_dev_with_placeholders_and_no_auth_loads(self):
        s = self._load(
            ENVIRONMENT="development",
            DATABASE_URL="postgresql://YOUR_DATABASE_PASSWORD@h/db",
            CLERK_ISSUER="",
            CLERK_AUDIENCE="",
        )
        self.assertEqual(s.environment, "development")

    # --- prod with real values passes --------------------------------------

    def test_prod_with_all_real_values_loads(self):
        self.assertEqual(self._load(ENVIRONMENT="production").environment, "production")

    # --- prod fail-fast cases ----------------------------------------------

    def test_prod_rejects_placeholder_database_url(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(ENVIRONMENT="production", DATABASE_URL="postgresql://YOUR_DATABASE_PASSWORD@h/db")
        self.assertIn("DATABASE_URL", str(ctx.exception))

    def test_prod_rejects_missing_clerk_issuer(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(ENVIRONMENT="production", CLERK_ISSUER="")
        self.assertIn("CLERK_ISSUER", str(ctx.exception))

    def test_prod_rejects_missing_clerk_audience(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(ENVIRONMENT="production", CLERK_AUDIENCE="")
        self.assertIn("CLERK_AUDIENCE", str(ctx.exception))

    def test_prod_error_lists_every_offender(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(
                ENVIRONMENT="production",
                DATABASE_URL="postgresql://YOUR_DATABASE_PASSWORD@h/db",
                CLERK_ISSUER="",
                CLERK_AUDIENCE="",
            )
        msg = str(ctx.exception)
        self.assertIn("DATABASE_URL", msg)
        self.assertIn("CLERK_ISSUER", msg)
        self.assertIn("CLERK_AUDIENCE", msg)

    # --- environment detection robustness ----------------------------------

    def test_prod_environment_uppercase_still_triggers(self):
        with self.assertRaises(ValueError):
            self._load(ENVIRONMENT="PRODUCTION", CLERK_ISSUER="")

    def test_prod_environment_with_whitespace_still_triggers(self):
        with self.assertRaises(ValueError):
            self._load(ENVIRONMENT="  production  ", CLERK_ISSUER="")

    def test_non_prod_environment_does_not_trigger(self):
        s = self._load(ENVIRONMENT="STAGING", CLERK_ISSUER="")
        self.assertEqual(s.environment, "STAGING")

    # --- Groq placeholder is graceful, not fatal ---------------------------

    def test_prod_with_groq_placeholder_does_not_raise(self):
        s = self._load(ENVIRONMENT="production", GROQ_API_KEY="your_groq_api_key_here")
        self.assertEqual(s.environment, "production")
        self.assertIsNone(s.groq_api_key)

    # --- platform superadmin bootstrap is FAIL-CLOSED ----------------------

    def test_platform_superadmins_empty_by_default(self):
        # Empty allowlist => zero auto-granted admins (never all).
        self.assertEqual(self._load().platform_superadmin_set, set())

    def test_platform_superadmins_parsed_and_normalized(self):
        s = self._load(PLATFORM_SUPERADMINS="User_ABC, admin@Example.com ")
        self.assertEqual(s.platform_superadmin_set, {"user_abc", "admin@example.com"})


if __name__ == "__main__":
    unittest.main()
