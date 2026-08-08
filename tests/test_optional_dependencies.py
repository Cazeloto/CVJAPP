import unittest

from analytics.exceptions import DependencyMissingError
from analytics.utils import require_dependency


class OptionalDependenciesTest(unittest.TestCase):
    def test_missing_dependency_message(self):
        with self.assertRaises(DependencyMissingError):
            require_dependency("module_that_does_not_exist_analytics")


if __name__ == "__main__":
    unittest.main()
