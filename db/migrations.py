"""Execucao idempotente das migracoes SQL do CVJAPP."""

from pathlib import Path
from threading import Lock

from core.config import Settings, settings
from db.conn import get_conn


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_MIGRATION_LOCK = Lock()
_MIGRATED = False


def run_migrations(config: Settings = settings) -> None:
    """Executa, em ordem, todas as migracoes idempotentes do projeto."""

    global _MIGRATED
    if _MIGRATED:
        return

    with _MIGRATION_LOCK:
        if _MIGRATED:
            return
        paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not paths:
            raise RuntimeError("Nenhuma migracao SQL foi encontrada.")

        with get_conn(config) as connection:
            with connection.cursor() as cursor:
                # Impede dois processos do Render de migrarem simultaneamente.
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (2_026_080_702,))
                for path in paths:
                    cursor.execute(path.read_text(encoding="utf-8"))
        _MIGRATED = True
