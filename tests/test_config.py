import unittest

from analytics.config import CacheConfig, DatabaseConfig


class ConfigTest(unittest.TestCase):
    def test_database_config(self):
        config = DatabaseConfig(url="postgresql+psycopg://user:pass@localhost/db")
        self.assertEqual(config.pool_size, 5)

    def test_cache_config_defaults(self):
        config = CacheConfig()
        self.assertTrue(config.enabled)
        self.assertGreater(config.ttl_seconds, 0)


if __name__ == "__main__":
    unittest.main()
