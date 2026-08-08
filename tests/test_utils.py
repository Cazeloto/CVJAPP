import unittest

from analytics.utils import format_percent, safe_filename, stable_hash


class UtilsTest(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(safe_filename("Relatório BI 01"), "Relat_rio_BI_01")

    def test_stable_hash(self):
        self.assertEqual(stable_hash({"b": 2, "a": 1}), stable_hash({"a": 1, "b": 2}))

    def test_format_percent(self):
        self.assertEqual(format_percent(12.3456, 1), "12.3%")


if __name__ == "__main__":
    unittest.main()
