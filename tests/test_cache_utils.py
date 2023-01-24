import unittest

from dj_tracker.cache_utils import LRUCache


class LRUCacheTest(unittest.TestCase):
    def test(self):
        cache = LRUCache(maxsize=2)

        cache.set(1, 1)
        cache.set(2, 2)
        cache.set(3, 3)

        self.assertEqual(len(cache), 2)
        self.assertIsNone(cache.get(1))
        self.assertEqual(cache.get(2), 2)
        self.assertEqual(cache.get(3), 3)

        cache.get(2)
        cache.set(4, 4)
        self.assertEqual(len(cache), 2)
        self.assertIsNone(cache.get(3))
        self.assertEqual(cache.get(2), 2)
        self.assertEqual(cache.get(4), 4)

        cache.set(5, 5)
        self.assertEqual(len(cache), 2)
        self.assertIsNone(cache.get(2))
        self.assertEqual(cache.get(4), 4)
        self.assertEqual(cache.get(5), 5)
