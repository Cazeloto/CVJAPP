from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from db.conn import get_conn
from db.audit import record_audit_event
from core.auth import require_admin


PORTUGUESE_MONTHS = (
    "", "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
)

# Mantem a ordem usada pelo arquivo de referencia. Tabelas novas sao
# exportadas depois destas, em ordem alfabetica.
REFERENCE_TABLE_ORDER = (
    "consulente", "tratamento", "giras", "retorno", "triagem",
    "triagempref", "retornopref", "mediuns", "prevgira", "registros",
    "frases", "acessos",
)


def export_filename(moment: datetime | None = None) -> str:
    moment = moment or datetime.now()
    return f"BaseDados_{moment.day}{PORTUGUESE_MONTHS[moment.month]}{moment.year}.txt"


def default_output_dir() -> Path:
    return Path.cwd() / "outputs"


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        text = value.isoformat(sep=" ")
    elif isinstance(value, (date, time)):
        text = value.isoformat()
    elif isinstance(value, (bytes, bytearray, memoryview)):
        return f"decode('{bytes(value).hex()}', 'hex')"
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    return "'" + text.replace("'", "''") + "'"


def _ordered_tables(cur) -> list[str]:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """
    )
    available = [row["table_name"] for row in cur.fetchall()]
    preferred = [name for name in REFERENCE_TABLE_ORDER if name in available]
    return preferred + sorted(set(available) - set(preferred))


def _columns(cur, table: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT a.attname AS column_name,
               pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
               a.attnotnull AS not_null,
               a.attidentity AS identity_kind,
               a.attgenerated AS generated_kind,
               pg_get_expr(ad.adbin, ad.adrelid) AS default_value
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_catalog.pg_attrdef ad
          ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
        WHERE n.nspname = 'public' AND c.relname = %s
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum;
        """,
        (table,),
    )
    return list(cur.fetchall())


def _constraints(cur, table: str) -> list[dict[str, str]]:
    cur.execute(
        """
        SELECT conname, contype, pg_get_constraintdef(oid, true) AS definition
        FROM pg_catalog.pg_constraint
        WHERE connamespace = 'public'::regnamespace
          AND conrelid = to_regclass('public.' || %s)
          AND contype IN ('p', 'u', 'c', 'f', 'x')
        ORDER BY CASE contype WHEN 'p' THEN 0 WHEN 'u' THEN 1
                                  WHEN 'c' THEN 2 ELSE 3 END,
                 conname;
        """,
        (table,),
    )
    return list(cur.fetchall())


def _serial_type(data_type: str, default_value: str | None) -> str | None:
    if not default_value or not re.match(r"^nextval\(", default_value):
        return None
    return {"smallint": "smallserial", "integer": "serial", "bigint": "bigserial"}.get(data_type)


def _write_schema(handle, table: str, columns: list[dict[str, Any]], constraints) -> None:
    handle.write(f"CREATE TABLE public.{_identifier(table)}(\n")
    definitions: list[str] = []
    for col in columns:
        serial_type = _serial_type(col["data_type"], col["default_value"])
        definition = f"  {_identifier(col['column_name'])} {serial_type or col['data_type']}"
        if col["identity_kind"]:
            generation = "ALWAYS" if col["identity_kind"] == "a" else "BY DEFAULT"
            definition += f" GENERATED {generation} AS IDENTITY"
        elif col["generated_kind"]:
            definition += f" GENERATED ALWAYS AS ({col['default_value']}) STORED"
        elif col["default_value"] and not serial_type:
            definition += f" DEFAULT {col['default_value']}"
        if col["not_null"]:
            definition += " NOT NULL"
        definitions.append(definition)
    for constraint in constraints:
        definitions.append(
            f"  CONSTRAINT {_identifier(constraint['conname'])} {constraint['definition']}"
        )
    handle.write(",\n".join(definitions))
    handle.write("\n);\n")


def _write_data(handle, cur, table: str, columns: list[dict[str, Any]]) -> int:
    insertable = [col for col in columns if not col["generated_kind"]]
    if not insertable:
        return 0
    names = [col["column_name"] for col in insertable]
    column_sql = ", ".join(_identifier(name) for name in names)
    table_sql = _identifier(table)
    cur.execute(f"SELECT {column_sql} FROM public.{table_sql};")
    count = 0
    identity_override = (
        " OVERRIDING SYSTEM VALUE" if any(col["identity_kind"] for col in insertable) else ""
    )
    for row in cur:
        handle.write(",\n" if count else f"INSERT INTO public.{table_sql} ({column_sql}){identity_override} VALUES\n")
        values = ", ".join(_literal(row[name]) for name in names)
        handle.write(f"({values})")
        count += 1
    if count:
        handle.write(";\n")
    return count


def _write_sequence_reset(handle, cur, table: str, columns) -> None:
    for col in columns:
        if not (_serial_type(col["data_type"], col["default_value"]) or col["identity_kind"]):
            continue
        cur.execute(
            "SELECT pg_get_serial_sequence(%s, %s) AS sequence_name;",
            (f"public.{table}", col["column_name"]),
        )
        sequence_name = cur.fetchone()["sequence_name"]
        if not sequence_name:
            continue
        table_sql, column_sql = _identifier(table), _identifier(col["column_name"])
        cur.execute(
            f"SELECT MAX({column_sql}) AS maximum, COUNT(*) AS total FROM public.{table_sql};"
        )
        info = cur.fetchone()
        value, called = ((int(info["maximum"]), "true") if info["total"] else (1, "false"))
        handle.write(f"SELECT setval({_literal(sequence_name)}, {value}, {called});\n")


def generate_database_export(
    actor_id: int,
    output_dir: str | os.PathLike[str] | None = None,
    *,
    moment: datetime | None = None,
    connection_factory: Callable = get_conn,
) -> Path:
    """Exporta estrutura e dados da base publica para um TXT SQL restauravel."""
    require_admin(actor_id)
    destination_dir = Path(output_dir) if output_dir else default_output_dir()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / export_filename(moment)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            prefix=".cvjapp_export_", suffix=".tmp", dir=destination_dir,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            generated_at = moment or datetime.now()
            handle.write("-- Exportacao da base CVJAPP\n")
            handle.write(f"-- Gerado em {generated_at.strftime('%d/%m/%Y %H:%M:%S')}\n\n")
            with connection_factory() as conn:
                with conn.cursor() as cur:
                    tables = _ordered_tables(cur)
                    metadata = {
                        table: (_columns(cur, table), _constraints(cur, table))
                        for table in tables
                    }
                    for table in reversed(tables):
                        handle.write(f"DROP TABLE IF EXISTS public.{_identifier(table)} CASCADE;\n")
                    handle.write("\n")
                    for table in tables:
                        columns, constraints = metadata[table]
                        _write_schema(handle, table, columns, constraints)
                        _write_data(handle, cur, table, columns)
                        _write_sequence_reset(handle, cur, table, columns)
                        handle.write("\n")
        os.replace(temporary_path, destination)
        record_audit_event(
            actor_id=actor_id,
            action="database.export",
            entity_type="database",
            details={"format": "sql_text"},
        )
        return destination.resolve()
    except Exception as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            record_audit_event(
                actor_id=actor_id,
                action="database.export",
                entity_type="database",
                outcome="failure",
                details={"error_type": type(error).__name__},
            )
        except Exception:
            pass
        raise
