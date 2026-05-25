from __future__ import annotations

import unittest

from app.core.config import Settings


REAL_DB = "postgresql+asyncpg://u:p@h:5432/db"
REAL_SUPABASE_URL = "https://realproject.supabase.co"
REAL_KEY = "real-secret-value-abc123"


class FailFastOnProductionPlaceholdersTests(unittest.TestCase):
    """Production refuses to boot with placeholder secrets; dev keeps working."""

    def _load(self, **overrides) -> Settings:
        # `_env_file=None` bypasses .env loading so each test is hermetic
        # against whatever real values may live in the dev .env.
        kwargs: dict = {
            "_env_file": None,
            "DATABASE_URL": REAL_DB,
            "SUPABASE_URL": REAL_SUPABASE_URL,
            "SUPABASE_SERVICE_ROLE_KEY": REAL_KEY,
            "SUPABASE_JWT_SECRET": REAL_KEY,
        }
        kwargs.update(overrides)
        return Settings(**kwargs)

    # --- dev passes regardless of placeholders -----------------------------

    def test_dev_with_all_real_values_loads(self):
        s = self._load(ENVIRONMENT="development")
        self.assertEqual(s.environment, "development")

    def test_dev_with_all_placeholder_values_loads(self):
        s = self._load(
            ENVIRONMENT="development",
            DATABASE_URL="postgresql://YOUR_DATABASE_PASSWORD@h/db",
            SUPABASE_URL="https://placeholder.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key-here",
            SUPABASE_JWT_SECRET="your-supabase-jwt-secret-here",
        )
        self.assertEqual(s.environment, "development")

    # --- prod with real values passes --------------------------------------

    def test_prod_with_all_real_values_loads(self):
        s = self._load(ENVIRONMENT="production")
        self.assertEqual(s.environment, "production")

    # --- prod with each placeholder type raises ----------------------------

    def test_prod_rejects_placeholder_database_url(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(
                ENVIRONMENT="production",
                DATABASE_URL="postgresql://YOUR_DATABASE_PASSWORD@h/db",
            )
        self.assertIn("DATABASE_URL", str(ctx.exception))

    def test_prod_rejects_placeholder_supabase_url(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(
                ENVIRONMENT="production",
                SUPABASE_URL="https://placeholder.supabase.co",
            )
        self.assertIn("SUPABASE_URL", str(ctx.exception))

    def test_prod_rejects_placeholder_service_role_key(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(
                ENVIRONMENT="production",
                SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key-here",
            )
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", str(ctx.exception))

    def test_prod_rejects_placeholder_jwt_secret(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(
                ENVIRONMENT="production",
                SUPABASE_JWT_SECRET="your-supabase-jwt-secret-here",
            )
        self.assertIn("SUPABASE_JWT_SECRET", str(ctx.exception))

    # --- error reports every offender, not just the first ------------------

    def test_prod_lists_every_offender_in_error(self):
        with self.assertRaises(ValueError) as ctx:
            self._load(
                ENVIRONMENT="production",
                SUPABASE_URL="https://placeholder.supabase.co",
                SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key-here",
                SUPABASE_JWT_SECRET="your-supabase-jwt-secret-here",
            )
        msg = str(ctx.exception)
        self.assertIn("SUPABASE_URL", msg)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", msg)
        self.assertIn("SUPABASE_JWT_SECRET", msg)

    # --- environment detection is robust to casing/whitespace --------------

    def test_prod_environment_uppercase_still_triggers(self):
        with self.assertRaises(ValueError):
            self._load(
                ENVIRONMENT="PRODUCTION",
                SUPABASE_JWT_SECRET="your-supabase-jwt-secret-here",
            )

    def test_prod_environment_with_whitespace_still_triggers(self):
        with self.assertRaises(ValueError):
            self._load(
                ENVIRONMENT="  production  ",
                SUPABASE_JWT_SECRET="your-supabase-jwt-secret-here",
            )

    def test_uppercase_dev_environment_does_not_trigger(self):
        # 'STAGING', 'TEST', 'DEVELOPMENT' should all be treated as non-prod.
        s = self._load(
            ENVIRONMENT="STAGING",
            SUPABASE_JWT_SECRET="your-supabase-jwt-secret-here",
        )
        self.assertEqual(s.environment, "STAGING")

    # --- documented contract: Groq placeholder is graceful, not fatal ------

    def test_prod_with_groq_placeholder_does_not_raise(self):
        # The existing field_validator on groq_api_key returns None and warns
        # so LLM-disabled deployments keep booting. Documenting that here so
        # nobody silently changes it.
        s = self._load(
            ENVIRONMENT="production",
            GROQ_API_KEY="your_groq_api_key_here",
        )
        self.assertEqual(s.environment, "production")
        self.assertIsNone(s.groq_api_key)


if __name__ == "__main__":
    unittest.main()
