import unittest

from analytics.dashboard import DashboardDefinition, DashboardSection
from analytics.models import KPIResult


class DashboardTest(unittest.TestCase):
    def test_all_kpis(self):
        dashboard = DashboardDefinition(
            title="BI",
            sections=[DashboardSection(title="Resumo", kpis=[KPIResult("total", 10)])],
        )
        self.assertEqual(len(dashboard.all_kpis()), 1)


if __name__ == "__main__":
    unittest.main()
