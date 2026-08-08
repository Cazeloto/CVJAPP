import unittest

from analytics.charts import default_chart_path


class ChartsContractTest(unittest.TestCase):
    def test_default_chart_path(self):
        path = default_chart_path("exports", "Atendimentos por Tipo", "html")
        self.assertEqual(str(path), "exports\\Atendimentos_por_Tipo.html")


if __name__ == "__main__":
    unittest.main()
