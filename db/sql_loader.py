from __future__ import annotations

import os
import re
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import psycopg
from dotenv import load_dotenv

from core.auth import require_admin
from db.audit import record_audit_event


@dataclass
class StatementResult:
    index: int
    kind: str
    preview: str
    ok: bool
    rowcount: Optional[int] = None
    elapsed_ms: int = 0
    error: str = ""


@dataclass
class LoadReport:
    started_at: str
    finished_at: str = ""
    elapsed_seconds: float = 0.0
    source_file: str = ""
    output_dir: str = ""
    host: str = ""
    port: str = ""
    dbname: str = ""
    user: str = ""
    total_statements: int = 0
    executed_statements: int = 0
    ok: bool = False
    error: str = ""
    log_file: str = ""
    details: List[StatementResult] = field(default_factory=list)


def strip_sql_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out = []
    in_single = False
    in_double = False
    i = 0

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if not in_double and ch == "'":
            out.append(ch)
            if in_single and nxt == "'":
                out.append(nxt)
                i += 2
                continue
            in_single = not in_single
            i += 1
            continue

        if not in_single and ch == '"':
            in_double = not in_double
            out.append(ch)
            i += 1
            continue

        if not in_single and not in_double and ch == "-" and nxt == "-":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def split_sql_statements(text: str) -> List[str]:
    cleaned = strip_sql_comments(text)
    statements: List[str] = []
    current: List[str] = []
    in_single = False
    in_double = False
    i = 0

    while i < len(cleaned):
        ch = cleaned[i]
        nxt = cleaned[i + 1] if i + 1 < len(cleaned) else ""

        if not in_double and ch == "'":
            current.append(ch)
            if in_single and nxt == "'":
                current.append(nxt)
                i += 2
                continue
            in_single = not in_single
            i += 1
            continue

        if not in_single and ch == '"':
            in_double = not in_double
            current.append(ch)
            i += 1
            continue

        if ch == ";" and not in_single and not in_double:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def statement_kind(sql: str) -> str:
    first = sql.lstrip().split(None, 1)
    return first[0].upper() if first else "SQL"


def preview_sql(sql: str, limit: int = 180) -> str:
    one_line = " ".join(sql.split())
    return one_line[:limit] + ("..." if len(one_line) > limit else "")


def build_connection_string() -> dict:
    load_dotenv()
    return {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": int(os.getenv("PG_PORT", "5432")),
        "dbname": os.getenv("PG_DB", ""),
        "user": os.getenv("PG_USER", ""),
        "password": os.getenv("PG_PASSWORD", ""),
        "connect_timeout": int(os.getenv("PG_TIMEOUT", "10")),
    }


def write_report_file(report: LoadReport) -> str:
    output_dir = Path(report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = output_dir / f"carga_sql_{ts}.log"

    lines: List[str] = [
        "=" * 90,
        "RELATORIO DE CARGA SQL",
        "=" * 90,
        f"Inicio.............: {report.started_at}",
        f"Fim................: {report.finished_at}",
        f"Duracao............: {report.elapsed_seconds:.2f}s",
        f"Arquivo origem.....: {report.source_file}",
        f"Pasta relatorio....: {report.output_dir}",
        f"Host...............: {report.host}",
        f"Porta..............: {report.port}",
        f"Banco..............: {report.dbname}",
        f"Usuario............: {report.user}",
        f"Total de comandos..: {report.total_statements}",
        f"Executados.........: {report.executed_statements}",
        f"Status geral.......: {'SUCESSO' if report.ok else 'FALHA'}",
    ]

    if report.error:
        lines.append(f"Erro geral.........: {report.error}")

    lines.extend(["", "-" * 90, "DETALHAMENTO DOS COMANDOS", "-" * 90])

    for item in report.details:
        lines.append(
            f"[{item.index:04d}] "
            f"{'OK' if item.ok else 'ERRO'} | "
            f"{item.kind:<10} | "
            f"{item.elapsed_ms:>6} ms | "
            f"rowcount={item.rowcount}"
        )
        lines.append(f"SQL: {item.preview}")
        if item.error:
            lines.append(f"ERRO: {item.error}")
        lines.append("")

    log_path.write_text("\n".join(lines), encoding="utf-8")
    return str(log_path)


def execute_sql_file(
    sql_file: str,
    output_dir: str,
    *,
    actor_id: int,
    source_name: Optional[str] = None,
) -> LoadReport:
    require_admin(actor_id)
    started_dt = datetime.now()
    report = LoadReport(
        started_at=started_dt.strftime("%d/%m/%Y %H:%M:%S"),
        source_file=source_name or sql_file,
        output_dir=output_dir,
    )

    conn_cfg = build_connection_string()
    report.host = str(conn_cfg["host"])
    report.port = str(conn_cfg["port"])
    report.dbname = str(conn_cfg["dbname"])
    report.user = str(conn_cfg["user"])

    try:
        sql_text = Path(sql_file).read_text(encoding="utf-8-sig", errors="replace")
        statements = split_sql_statements(sql_text)
        report.total_statements = len(statements)

        if not statements:
            raise RuntimeError("O arquivo nao contem comandos SQL validos.")

        with psycopg.connect(**conn_cfg) as conn:
            with conn.cursor() as cur:
                cur.execute("SET datestyle TO ISO, DMY")

                for idx, stmt in enumerate(statements, start=1):
                    item_start = time.perf_counter()
                    kind = statement_kind(stmt)
                    preview = preview_sql(stmt)

                    try:
                        cur.execute(stmt)
                        elapsed_ms = int((time.perf_counter() - item_start) * 1000)
                        report.details.append(
                            StatementResult(
                                index=idx,
                                kind=kind,
                                preview=preview,
                                ok=True,
                                rowcount=cur.rowcount,
                                elapsed_ms=elapsed_ms,
                            )
                        )
                        report.executed_statements += 1
                    except Exception as ex:
                        conn.rollback()
                        elapsed_ms = int((time.perf_counter() - item_start) * 1000)
                        report.details.append(
                            StatementResult(
                                index=idx,
                                kind=kind,
                                preview=preview,
                                ok=False,
                                elapsed_ms=elapsed_ms,
                                error=f"{type(ex).__name__}: {ex}",
                            )
                        )
                        raise

            conn.commit()

        report.ok = True

    except Exception as ex:
        report.ok = False
        tb = traceback.format_exc(limit=5)
        report.error = f"{type(ex).__name__}: {ex}\n{tb}"

    finally:
        finished_dt = datetime.now()
        report.finished_at = finished_dt.strftime("%d/%m/%Y %H:%M:%S")
        report.elapsed_seconds = (finished_dt - started_dt).total_seconds()
        report.log_file = write_report_file(report)

    try:
        record_audit_event(
            actor_id=actor_id,
            action="database.load",
            entity_type="database",
            outcome="success" if report.ok else "failure",
            details={
                "statements": report.total_statements,
                "executed": report.executed_statements,
            },
        )
    except Exception:
        # A carga pode ter substituido a propria estrutura de auditoria.
        # O relatorio da operacao continua sendo devolvido ao administrador.
        pass

    return report


def build_summary_text(report: LoadReport) -> str:
    status = "SUCESSO" if report.ok else "FALHA"
    lines = [
        f"Status: {status}",
        f"Arquivo: {report.source_file}",
        f"Relatorio: {report.log_file}",
        f"Banco: {report.dbname} @ {report.host}:{report.port}",
        f"Comandos encontrados: {report.total_statements}",
        f"Comandos executados: {report.executed_statements}",
        f"Duracao: {report.elapsed_seconds:.2f}s",
    ]

    if report.details:
        ok_count = sum(1 for d in report.details if d.ok)
        err_count = sum(1 for d in report.details if not d.ok)
        lines.append(f"Detalhes: {ok_count} OK / {err_count} erro(s)")

    if report.error:
        lines.extend(["", "Erro:", report.error[:5000]])

    return "\n".join(lines)
