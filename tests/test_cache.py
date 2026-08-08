import time
import unittest

from analytics.cache import CacheManager
from analytics.config import CacheConfig


class CacheManagerTest(unittest.TestCase):
    def test_set_get_and_expire(self):
        cache = CacheManager(CacheConfig(ttl_seconds=1))
        cache.set("a", 10)
        self.assertEqual(cache.get("a"), 10)
        time.sleep(1.05)
        self.assertIsNone(cache.get("a"))


if __name__ == "__main__":
    unittest.main()
