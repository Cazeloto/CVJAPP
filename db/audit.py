"""Trilha de auditoria para operacoes sensiveis do CVJAPP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from db.conn import get_conn


OUTCOMES = frozenset({"success", "denied", "failure"})
SAFE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{1,79}$")
SENSITIVE_DETAIL_PARTS = ("password", "senha", "token", "secret", "hash", "pdf")
MAX_DETAILS_BYTES = 8_192


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: int
    occurred_at: datetime
    actor_label: str
    action: str
    entity_type: str
    entity_id: str | None
    outcome: str
    details: dict[str, Any]


def _safe_name(value: str, field: str) -> str:
    clean = value.strip().lower()
    if not SAFE_NAME_PATTERN.fullmatch(clean):
        raise ValueError(f"Identificador de auditoria invalido: {field}.")
    return clean


def _safe_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    clean = dict(details or {})
    for key in clean:
        normalized = str(key).strip().lower()
        if any(part in normalized for part in SENSITIVE_DETAIL_PARTS):
            raise ValueError("Detalhe sensivel nao pode ser gravado na auditoria.")
    encoded = json.dumps(clean, ensure_ascii=False, default=str)
    if len(encoded.encode("utf-8")) > MAX_DETAILS_BYTES:
        raise ValueError("Detalhes de auditoria excedem o limite permitido.")
    return clean


def record_audit_event(
    *,
    action: str,
    entity_type: str,
    actor_id: int | None = None,
    actor_label: str | None = None,
    entity_id: str | int | None = None,
    outcome: str = "success",
    details: Mapping[str, Any] | None = None,
    cursor=None,
) -> int:
    """Registra um evento; com cursor, participa da mesma transacao da acao."""

    safe_action = _safe_name(action, "action")
    safe_entity = _safe_name(entity_type, "entity_type")
    if outcome not in OUTCOMES:
        raise ValueError("Resultado de auditoria invalido.")
    safe_label = " ".join((actor_label or "").strip().split())[:120]
    safe_entity_id = None if entity_id is None else str(entity_id).strip()[:120]
    safe_payload = _safe_details(details)

    statement = """
        INSERT INTO public.cvjapp_audit_events
            (actor_id, actor_label, action, entity_type, entity_id, outcome, details)
        VALUES (
            %s,
            COALESCE(
                NULLIF(%s, ''),
                (SELECT username FROM public.cvjcura_users WHERE user_id = %s),
                'sistema'
            ),
            %s, %s, %s, %s, %s
        )
        RETURNING event_id
    """
    params = (
        actor_id,
        safe_label,
        actor_id,
        safe_action,
        safe_entity,
        safe_entity_id or None,
        outcome,
        Jsonb(safe_payload),
    )

    if cursor is not None:
        cursor.execute(statement, params)
        return int(cursor.fetchone()["event_id"])

    with get_conn() as connection:
        with connection.cursor() as own_cursor:
            own_cursor.execute(statement, params)
            return int(own_cursor.fetchone()["event_id"])


def list_audit_events(actor_id: int, limit: int = 200) -> list[AuditEvent]:
    """Lista eventos recentes somente para um administrador ativo."""

    safe_limit = max(1, min(int(limit), 500))
    with get_conn() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM public.cvjcura_users
                 WHERE user_id = %s AND role = 'admin' AND active
                """,
                (actor_id,),
            )
            if cursor.fetchone() is None:
                raise PermissionError("Acao permitida somente para administradores.")
            cursor.execute(
                """
                SELECT event_id, occurred_at, actor_label, action,
                       entity_type, entity_id, outcome, details
                  FROM public.cvjapp_audit_events
                 ORDER BY occurred_at DESC, event_id DESC
                 LIMIT %s
                """,
                (safe_limit,),
            )
            return [
                AuditEvent(
                    id=row["event_id"],
                    occurred_at=row["occurred_at"],
                    actor_label=row["actor_label"],
                    action=row["action"],
                    entity_type=row["entity_type"],
                    entity_id=row["entity_id"],
                    outcome=row["outcome"],
                    details=dict(row["details"] or {}),
                )
                for row in cursor
            ]
