from __future__ import annotations

import unittest

from app.db.session import normalize_database_url_for_asyncpg


class DatabaseUrlNormalizationTests(unittest.TestCase):
    def test_accepts_supabase_pooler_postgres_scheme(self):
        clean_url, ssl_mode = normalize_database_url_for_asyncpg(
            "postgres://postgres.projectref:secret@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require"
        )

        self.assertEqual(
            clean_url,
            "postgresql+asyncpg://postgres.projectref:secret@aws-0-ap-south-1.pooler.supabase.com:5432/postgres",
        )
        self.assertEqual(ssl_mode, "require")

    def test_accepts_existing_asyncpg_scheme(self):
        clean_url, ssl_mode = normalize_database_url_for_asyncpg(
            "postgresql+asyncpg://postgres:secret@db.projectref.supabase.co:5432/postgres?sslmode=require"
        )

        self.assertEqual(
            clean_url,
            "postgresql+asyncpg://postgres:secret@db.projectref.supabase.co:5432/postgres",
        )
        self.assertEqual(ssl_mode, "require")


if __name__ == "__main__":
    unittest.main()
