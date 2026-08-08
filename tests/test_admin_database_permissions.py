from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from db.sql_exporter import generate_database_export
from db.sql_loader import execute_sql_file


class AdminDatabasePermissionsTest(TestCase):
    def test_export_rejects_non_admin_before_creating_files(self):
        with TemporaryDirectory() as directory:
            with patch(
                "db.sql_exporter.require_admin",
                side_effect=PermissionError("Somente administradores."),
            ) as authorize:
                with self.assertRaises(PermissionError):
                    generate_database_export(12, directory)

            authorize.assert_called_once_with(12)
            self.assertEqual(list(Path(directory).iterdir()), [])
    def test_sql_load_rejects_non_admin_before_reading_source(self):
        with TemporaryDirectory() as directory:
            missing_source = Path(directory) / "nao-deve-ser-lido.sql"
            with patch(
                "db.sql_loader.require_admin",
                side_effect=PermissionError("Somente administradores."),
            ) as authorize:
                with self.assertRaises(PermissionError):
                    execute_sql_file(
                        str(missing_source),
                        directory,
                        actor_id=18,
                    )

            authorize.assert_called_once_with(18)
            self.assertEqual(list(Path(directory).iterdir()), [])
