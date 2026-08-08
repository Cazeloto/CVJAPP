import unittest

from analytics.exports_pdf import PDFReport
from analytics.models import KPIResult


class PDFContractTest(unittest.TestCase):
    def test_pdf_report_payload(self):
        report = PDFReport(title="BI", kpis=[KPIResult(name="total", value=10)])
        self.assertEqual(report.title, "BI")
        self.assertEqual(report.kpis[0].value, 10)


if __name__ == "__main__":
    unittest.main()
