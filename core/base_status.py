"""Estado da atualizacao da base exibido na barra de acesso."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class BaseUpdateStatus:
    diagnosis_filled: bool
    treatment_start: object = None
    available: bool = True


def format_treatment_start(value: object) -> str:
    """Formata a data do banco sem depender do tipo retornado pelo driver."""

    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return text


def status_presentation(status: BaseUpdateStatus) -> tuple[bool, str, str]:
    """Retorna cor logica, texto curto e explicacao do indicador."""

    if not status.available:
        return False, "", "Não foi possível verificar a atualização da base."
    if not status.diagnosis_filled:
        return False, "", "O último consulente está sem diagnóstico."
    start = format_treatment_start(status.treatment_start)
    label = f"Início: {start}" if start else "Início: não informado"
    return True, label, "O último consulente está com diagnóstico preenchido."
