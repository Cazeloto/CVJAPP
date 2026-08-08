from datetime import datetime
from unittest import TestCase

from db.sql_exporter import PORTUGUESE_MONTHS, _identifier, _literal, export_filename


class SqlExporterTest(TestCase):
    def test_filename_uses_reference_pattern(self):
        self.assertEqual(
            export_filename(datetime(2026, 8, 6, 12, 30)),
            "BaseDados_6ago2026.txt",
        )

    def test_all_months_have_a_name(self):
        self.assertEqual(len(PORTUGUESE_MONTHS), 13)
        self.assertTrue(all(PORTUGUESE_MONTHS[1:]))

    def test_sql_text_literal_escapes_quotes(self):
        self.assertEqual(_literal("D'Ávila"), "'D''Ávila'")

    def test_null_and_identifier(self):
        self.assertEqual(_literal(None), "NULL")
        self.assertEqual(_identifier('campo"teste'), '"campo""teste"')
