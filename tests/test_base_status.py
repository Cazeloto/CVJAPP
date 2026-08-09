from datetime import date
from unittest import TestCase

from core.base_status import BaseUpdateStatus, format_treatment_start, status_presentation


class BaseStatusTest(TestCase):
    def test_formats_treatment_start(self):
        self.assertEqual(format_treatment_start(date(2026, 8, 9)), "09/08/2026")
        self.assertEqual(format_treatment_start("2026-08-09"), "09/08/2026")

    def test_red_when_latest_diagnosis_is_empty(self):
        updated, label, _tooltip = status_presentation(
            BaseUpdateStatus(diagnosis_filled=False, treatment_start=date(2026, 8, 9))
        )
        self.assertFalse(updated)
        self.assertEqual(label, "")

    def test_green_with_treatment_start_when_diagnosis_is_filled(self):
        updated, label, _tooltip = status_presentation(
            BaseUpdateStatus(diagnosis_filled=True, treatment_start=date(2026, 8, 9))
        )
        self.assertTrue(updated)
        self.assertEqual(label, "Início: 09/08/2026")
