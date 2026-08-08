import tempfile
from pathlib import Path
from unittest import TestCase

from ui.main_view import _caminho_local_existente


class FilePickerPathTest(TestCase):
    def test_browser_filename_is_not_treated_as_server_path(self):
        self.assertIsNone(_caminho_local_existente("BaseDados_6ago2026.txt"))
        self.assertIsNone(
            _caminho_local_existente(r"C:\fakepath\BaseDados_6ago2026.txt")
        )

    def test_existing_absolute_server_path_is_accepted(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as selected:
            expected = str(Path(selected.name).resolve())
            self.assertEqual(_caminho_local_existente(selected.name), expected)
