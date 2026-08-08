from unittest import TestCase

from core.config import Settings


class CoreConfigTest(TestCase):
    def test_database_url_has_priority(self):
        config = Settings(database_url="postgresql://example/test")
        self.assertEqual(
            config.connection_kwargs(),
            {"conninfo": "postgresql://example/test"},
        )

    def test_individual_database_settings(self):
        config = Settings(
            database_url=None,
            pg_host="db.example",
            pg_db="cvj",
            pg_user="app",
            pg_password="secret",
        )
        kwargs = config.connection_kwargs()
        self.assertEqual(kwargs["host"], "db.example")
        self.assertEqual(kwargs["dbname"], "cvj")
