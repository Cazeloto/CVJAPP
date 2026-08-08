import importlib.util
import unittest

from analytics import indicadores


@unittest.skipIf(importlib.util.find_spec("pandas") is None, "pandas não instalado")
class IndicadoresTest(unittest.TestCase):
    def setUp(self):
        import pandas as pd

        self.df = pd.DataFrame(
            [
                {"status": "A", "valor": 10, "data": "2026-01-01"},
                {"status": "F", "valor": 20, "data": "2026-01-02"},
                {"status": "A", "valor": 30, "data": "2026-01-02"},
            ]
        )

    def test_total_records(self):
        self.assertEqual(indicadores.total_records(self.df).value, 3)

    def test_active_records(self):
        self.assertEqual(indicadores.active_records(self.df, "status", "A").value, 2)

    def test_top_n(self):
        result = indicadores.top_n(self.df, "status", n=1)
        self.assertEqual(result.iloc[0]["status"], "A")


if __name__ == "__main__":
    unittest.main()
