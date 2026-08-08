"""Replica alteracoes operacionais do Neon para o PostgreSQL local."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from psycopg.rows import dict_row


LOGGER = logging.getLogger("cvjapp.sync")
SOURCE_KEY = "neon"
SYNC_LOCK_ID = 2_026_081_001
SYNC_TABLES = (
    "acessos",
    "frases",
    "mediuns",
    "giras",
    "prevgira",
    "registros",
    "consulente",
    "tratamento",
    "retorno",
    "retornopref",
    "triagem",
    "triagempref",
    "chamada_concluida",
)


@dataclass(frozen=True)
class DatabaseTarget:
    host: str
    port: str
    dbname: str
    user: str
    password: str
    sslmode: str = "prefer"

    def connect(self, *, autocommit: bool = False):
        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            sslmode=self.sslmode,
            connect_timeout=10,
            autocommit=autocommit,
            row_factory=dict_row,
        )


@dataclass(frozen=True)
class SyncConfig:
    source: DatabaseTarget
    target: DatabaseTarget
    poll_seconds: float = 5.0
    batch_size: int = 500

    @classmethod
    def load(cls, env_path: str | Path) -> "SyncConfig":
        values = dotenv_values(Path(env_path))

        def target(prefix: str) -> DatabaseTarget:
            required = {
                "host": values.get(prefix + "HOST"),
                "dbname": values.get(prefix + "DB"),
                "user": values.get(prefix + "USER"),
                "password": values.get(prefix + "PASSWORD"),
            }
            missing = [key for key, value in required.items() if not value]
            if missing:
                raise RuntimeError(
                    f"Configuracao {prefix} incompleta: " + ", ".join(missing)
                )
            return DatabaseTarget(
                host=str(required["host"]),
                port=str(values.get(prefix + "PORT") or "5432"),
                dbname=str(required["dbname"]),
                user=str(required["user"]),
                password=str(required["password"]),
                sslmode=str(values.get(prefix + "SSLMODE") or "prefer"),
            )

        return cls(
            source=target("PG_"),
            target=target("DB_"),
            poll_seconds=max(2.0, float(values.get("SYNC_POLL_SECONDS") or 5)),
            batch_size=max(1, min(5_000, int(values.get("SYNC_BATCH_SIZE") or 500))),
        )


def _ensure_state_table(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS public.cvjcura_sync_state (
                source_key TEXT PRIMARY KEY,
                last_event_id BIGINT NOT NULL DEFAULT 0,
                initial_sync_completed BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO public.cvjcura_sync_state (source_key)
            VALUES (%s)
            ON CONFLICT (source_key) DO NOTHING
            """,
            (SOURCE_KEY,),
        )


def _checkpoint(connection) -> tuple[int, bool]:
    _ensure_state_table(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT last_event_id, initial_sync_completed
              FROM public.cvjcura_sync_state
             WHERE source_key = %s
             FOR UPDATE
            """,
            (SOURCE_KEY,),
        )
        row = cursor.fetchone()
    return int(row["last_event_id"]), bool(row["initial_sync_completed"])


def _set_checkpoint(connection, event_id: int, *, initial: bool | None = None) -> None:
    initial_sql = (
        sql.SQL(", initial_sync_completed = {}")
        .format(sql.Literal(initial))
        if initial is not None
        else sql.SQL("")
    )
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                UPDATE public.cvjcura_sync_state
                   SET last_event_id = %s,
                       updated_at = CURRENT_TIMESTAMP
                       {}
                 WHERE source_key = %s
                """
            ).format(initial_sql),
            (event_id, SOURCE_KEY),
        )


def _table_metadata(connection, table: str) -> tuple[list[str], list[str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = %s
             ORDER BY ordinal_position
            """,
            (table,),
        )
        columns = [row["column_name"] for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT a.attname AS column_name
              FROM pg_index i
              JOIN pg_attribute a
                ON a.attrelid = i.indrelid
               AND a.attnum = ANY(i.indkey)
             WHERE i.indrelid = %s::regclass
               AND i.indisprimary
             ORDER BY array_position(i.indkey, a.attnum)
            """,
            (f"public.{table}",),
        )
        primary_key = [row["column_name"] for row in cursor.fetchall()]
    if not columns:
        raise RuntimeError(f"Tabela local ausente: public.{table}")
    if not primary_key:
        raise RuntimeError(f"Tabela local sem chave primaria: public.{table}")
    return columns, primary_key


def _upsert_row(
    cursor,
    table: str,
    row: dict[str, Any],
    columns: Iterable[str],
    primary_key: Iterable[str],
) -> None:
    allowed = set(columns)
    payload = {key: value for key, value in row.items() if key in allowed}
    if not payload:
        raise RuntimeError(f"Evento sem colunas reconhecidas para {table}")
    keys = list(payload)
    pk = list(primary_key)
    missing_pk = [key for key in pk if key not in payload]
    if missing_pk:
        raise RuntimeError(f"Evento de {table} sem chave: {', '.join(missing_pk)}")
    update_keys = [key for key in keys if key not in pk]
    conflict_action = (
        sql.SQL("DO UPDATE SET ")
        + sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(key), sql.Identifier(key))
            for key in update_keys
        )
        if update_keys
        else sql.SQL("DO NOTHING")
    )
    statement = sql.SQL(
        "INSERT INTO public.{} ({}) VALUES ({}) ON CONFLICT ({}) {}"
    ).format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, keys)),
        sql.SQL(", ").join(sql.Placeholder() for _ in keys),
        sql.SQL(", ").join(map(sql.Identifier, pk)),
        conflict_action,
    )
    cursor.execute(statement, [payload[key] for key in keys])


def _delete_row(
    cursor,
    table: str,
    row: dict[str, Any],
    primary_key: Iterable[str],
) -> None:
    pk = list(primary_key)
    missing = [key for key in pk if key not in row]
    if missing:
        raise RuntimeError(f"Exclusao de {table} sem chave: {', '.join(missing)}")
    where = sql.SQL(" AND ").join(
        sql.SQL("{} = {}").format(sql.Identifier(key), sql.Placeholder()) for key in pk
    )
    cursor.execute(
        sql.SQL("DELETE FROM public.{} WHERE ").format(sql.Identifier(table)) + where,
        [row[key] for key in pk],
    )


def _sync_sequences(connection, tables: Iterable[str]) -> None:
    with connection.cursor() as cursor:
        for table in sorted(set(tables)):
            _, primary_key = _table_metadata(connection, table)
            if len(primary_key) != 1:
                continue
            key = primary_key[0]
            cursor.execute(
                "SELECT pg_get_serial_sequence(%s, %s) AS sequence_name",
                (f"public.{table}", key),
            )
            sequence_name = cursor.fetchone()["sequence_name"]
            if not sequence_name:
                continue
            cursor.execute(
                sql.SQL("SELECT MAX({}) AS maximum FROM public.{}").format(
                    sql.Identifier(key), sql.Identifier(table)
                )
            )
            maximum = cursor.fetchone()["maximum"]
            if maximum is not None:
                cursor.execute("SELECT setval(%s, %s, TRUE)", (sequence_name, maximum))


class NeonToLocalSynchronizer:
    def __init__(self, config: SyncConfig):
        self.config = config

    def check(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        with self.config.source.connect() as source, self.config.target.connect() as target:
            with source.cursor() as cursor:
                cursor.execute("SELECT version() AS version")
                result["source_version"] = cursor.fetchone()["version"].split(",")[0]
                cursor.execute("SELECT to_regclass('public.cvjcura_sync_outbox') AS name")
                if cursor.fetchone()["name"] is None:
                    raise RuntimeError("A fila de sincronizacao ainda nao existe no Neon.")
            metadata = {}
            for table in SYNC_TABLES:
                source_columns, _ = _table_metadata(source, table)
                target_columns, target_pk = _table_metadata(target, table)
                if source_columns != target_columns:
                    raise RuntimeError(f"Estrutura diferente entre Neon e local: {table}")
                metadata[table] = (target_columns, target_pk)
            _ensure_state_table(target)
            with target.cursor() as cursor:
                cursor.execute("SELECT version() AS version")
                result["target_version"] = cursor.fetchone()["version"].split(",")[0]
            target.commit()
        result["tables"] = len(metadata)
        return result

    def initial_sync(self) -> int:
        """Faz upsert do retrato do Neon sem apagar historico existente local."""

        total = 0
        with self.config.source.connect() as source, self.config.target.connect() as target:
            source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            with source.cursor() as cursor:
                cursor.execute(
                    "SELECT COALESCE(MAX(event_id), 0) AS marker FROM public.cvjcura_sync_outbox"
                )
                marker = int(cursor.fetchone()["marker"])
            _ensure_state_table(target)
            with target.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s) AS locked", (SYNC_LOCK_ID,))
                if not cursor.fetchone()["locked"]:
                    raise RuntimeError("Outro processo de sincronizacao esta em execucao.")
                cursor.execute("SELECT set_config('cvjcura.sync_suppressed', 'on', TRUE)")
                for table in SYNC_TABLES:
                    columns, primary_key = _table_metadata(target, table)
                    with source.cursor() as source_cursor:
                        source_cursor.execute(
                            sql.SQL("SELECT * FROM public.{}").format(sql.Identifier(table))
                        )
                        for row in source_cursor:
                            _upsert_row(cursor, table, dict(row), columns, primary_key)
                            total += 1
                _sync_sequences(target, SYNC_TABLES)
                _set_checkpoint(target, marker, initial=True)
        LOGGER.info("Carga inicial concluida: %s registros, marcador %s", total, marker)
        return total

    def sync_once(self) -> int:
        with self.config.source.connect() as source, self.config.target.connect() as target:
            last_event_id, initialized = _checkpoint(target)
            if not initialized:
                raise RuntimeError("Execute a carga inicial antes da sincronizacao continua.")
            with source.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_id, table_name, operation, row_data, old_data
                      FROM public.cvjcura_sync_outbox
                     WHERE event_id > %s
                     ORDER BY event_id
                     LIMIT %s
                    """,
                    (last_event_id, self.config.batch_size),
                )
                events = list(cursor.fetchall())
            if not events:
                target.commit()
                return 0

            metadata: dict[str, tuple[list[str], list[str]]] = {}
            touched: set[str] = set()
            with target.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s) AS locked", (SYNC_LOCK_ID,))
                if not cursor.fetchone()["locked"]:
                    raise RuntimeError("Outro processo de sincronizacao esta em execucao.")
                cursor.execute("SELECT set_config('cvjcura.sync_suppressed', 'on', TRUE)")
                for event in events:
                    table = str(event["table_name"])
                    if table not in SYNC_TABLES:
                        raise RuntimeError(f"Tabela nao autorizada na fila: {table}")
                    if table not in metadata:
                        metadata[table] = _table_metadata(target, table)
                    columns, primary_key = metadata[table]
                    if event["operation"] == "D":
                        _delete_row(cursor, table, dict(event["old_data"]), primary_key)
                    else:
                        _upsert_row(
                            cursor,
                            table,
                            dict(event["row_data"]),
                            columns,
                            primary_key,
                        )
                    touched.add(table)
                _sync_sequences(target, touched)
                _set_checkpoint(target, int(events[-1]["event_id"]))
            LOGGER.info(
                "Sincronizados %s eventos ate %s",
                len(events),
                events[-1]["event_id"],
            )
            return len(events)

