import unittest

from analytics.exports_excel import ExcelSheet


class ExcelContractTest(unittest.TestCase):
    def test_excel_sheet_name(self):
        sheet = ExcelSheet(name="Dados", dataframe=object())
        self.assertEqual(sheet.name, "Dados")


if __name__ == "__main__":
    unittest.main()
