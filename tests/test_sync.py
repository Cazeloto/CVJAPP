import tempfile
import unittest
from pathlib import Path

from db.sync import SYNC_TABLES, SyncConfig, _delete_row, _upsert_row


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, statement, parameters=None):
        self.calls.append((statement, parameters))


class SyncConfigTest(unittest.TestCase):
    def test_loads_neon_and_local_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "\n".join(
                    [
                        "PG_HOST=neon.example",
                        "PG_DB=principal",
                        "PG_USER=neon_user",
                        "PG_PASSWORD=neon_secret",
                        "DB_HOST=localhost",
                        "DB_DB=local",
                        "DB_USER=local_user",
                        "DB_PASSWORD=local_secret",
                        "SYNC_POLL_SECONDS=1",
                        "SYNC_BATCH_SIZE=99999",
                    ]
                ),
                encoding="utf-8",
            )
            config = SyncConfig.load(path)

        self.assertEqual(config.source.host, "neon.example")
        self.assertEqual(config.target.host, "localhost")
        self.assertEqual(config.poll_seconds, 2.0)
        self.assertEqual(config.batch_size, 5_000)

    def test_all_operational_tables_are_explicitly_allowed(self):
        self.assertIn("consulente", SYNC_TABLES)
        self.assertIn("tratamento", SYNC_TABLES)
        self.assertNotIn("cvjcura_users", SYNC_TABLES)
        self.assertNotIn("cvjcura_audit_events", SYNC_TABLES)


class RowReplicationTest(unittest.TestCase):
    def test_upsert_uses_only_known_columns(self):
        cursor = RecordingCursor()
        _upsert_row(
            cursor,
            "consulente",
            {"con_codigo": 7, "con_nome": "MARIA", "unexpected": "ignored"},
            ["con_codigo", "con_nome"],
            ["con_codigo"],
        )
        self.assertEqual(cursor.calls[0][1], [7, "MARIA"])

    def test_delete_requires_primary_key(self):
        with self.assertRaisesRegex(RuntimeError, "sem chave"):
            _delete_row(RecordingCursor(), "consulente", {}, ["con_codigo"])


if __name__ == "__main__":
    unittest.main()
