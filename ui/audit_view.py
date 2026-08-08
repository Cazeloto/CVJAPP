"""Consulta administrativa da trilha de auditoria."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import flet as ft

from core.auth import AuthenticatedUser
from db.audit import AuditEvent, list_audit_events


COLOR_BG = "#F6EEF6"
COLOR_HEADER = "#8B5A91"
COLOR_TEXT = "#503054"
COLOR_BORDER = "#D2B8D8"
LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")

ACTION_LABELS = {
    "auth.login": "Entrada no sistema",
    "auth.logout": "Saida do sistema",
    "auth.session_expired": "Sessao expirada",
    "auth.session_revoked": "Sessao revogada",
    "user.bootstrap": "Administrador inicial criado",
    "user.create": "Usuario criado",
    "user.password_reset": "Senha redefinida",
    "user.activate": "Usuario ativado",
    "user.deactivate": "Usuario desativado",
    "user.unlock": "Usuario desbloqueado",
    "database.export": "Base exportada",
    "database.load": "Carga de base executada",
    "system.migration": "Estrutura do sistema atualizada",
    "print.enqueue": "Impressao solicitada",
    "print.complete": "Impressao concluida",
    "print.fail": "Falha de impressao",
    "print.cancel": "Impressao cancelada",
}
OUTCOME_LABELS = {
    "success": ("Sucesso", "#067647", "#ECFDF3"),
    "denied": ("Negado", "#B54708", "#FFFAEB"),
    "failure": ("Falha", "#B42318", "#FEF3F2"),
}


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(LOCAL_TIMEZONE)
    return value.strftime("%d/%m/%Y %H:%M:%S")


def _details_text(event: AuditEvent) -> str:
    values = []
    if event.entity_id:
        values.append(f"Referencia: {event.entity_id}")
    for key, value in event.details.items():
        label = {
            "username": "Usuario",
            "role": "Perfil",
            "job_type": "Tipo",
            "retry": "Nova tentativa",
            "error": "Erro",
            "error_type": "Tipo de erro",
            "format": "Formato",
            "statements": "Comandos",
            "executed": "Executados",
            "locked": "Bloqueio aplicado",
        }.get(key, key.replace("_", " ").title())
        if isinstance(value, bool):
            value = "Sim" if value else "Nao"
        values.append(f"{label}: {value}")
    return " | ".join(values)


async def show_audit_log(
    page: ft.Page,
    current_user: AuthenticatedUser,
    on_back: Callable[[], Awaitable[None]],
    on_logout: Callable[[], Awaitable[None]],
) -> None:
    page.clean()
    page.title = "CVJAPP - Auditoria"
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

    status = ft.Text("", size=13, visible=False)
    progress = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)
    events_area = ft.Column(spacing=9)
    refresh_button = ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Atualizar")

    def event_card(event: AuditEvent) -> ft.Container:
        outcome_label, outcome_color, outcome_bg = OUTCOME_LABELS.get(
            event.outcome, (event.outcome, "#667085", "#F2F4F7")
        )
        details = _details_text(event)
        controls = [
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, color=COLOR_HEADER),
                    ft.Column(
                        expand=True,
                        spacing=1,
                        controls=[
                            ft.Text(
                                ACTION_LABELS.get(event.action, event.action),
                                weight=ft.FontWeight.BOLD,
                                color=COLOR_TEXT,
                            ),
                            ft.Text(
                                f"{event.actor_label} - {_format_datetime(event.occurred_at)}",
                                size=11,
                                color="#667085",
                            ),
                        ],
                    ),
                    ft.Container(
                        bgcolor=outcome_bg,
                        border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=9, vertical=4),
                        content=ft.Text(
                            outcome_label,
                            size=11,
                            color=outcome_color,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ),
                ]
            )
        ]
        if details:
            controls.append(ft.Text(details, size=11, color="#475467"))
        return ft.Container(
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, COLOR_BORDER),
            border_radius=12,
            padding=12,
            content=ft.Column(spacing=5, controls=controls),
        )

    async def reload_events(_event=None) -> None:
        progress.visible = True
        refresh_button.disabled = True
        page.update()
        try:
            events = await asyncio.to_thread(list_audit_events, current_user.id, 200)
            events_area.controls = [event_card(event) for event in events]
            if not events:
                events_area.controls = [ft.Text("Nenhum evento de auditoria registrado.")]
            status.visible = False
        except Exception as error:
            status.value = f"Nao foi possivel consultar a auditoria: {error}"
            status.color = "#B42318"
            status.visible = True
        finally:
            progress.visible = False
            refresh_button.disabled = False
            page.update()

    refresh_button.on_click = reload_events
    page.add(
        ft.Container(
            bgcolor=COLOR_HEADER,
            padding=ft.Padding.symmetric(horizontal=8, vertical=10),
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: page.run_task(on_back),
                    ),
                    ft.Text(
                        "Auditoria",
                        expand=True,
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT,
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: page.run_task(on_logout),
                    ),
                ]
            ),
        ),
        ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            padding=14,
            content=ft.Container(
                width=820,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Column(
                                    expand=True,
                                    spacing=2,
                                    controls=[
                                        ft.Text(
                                            "Historico de seguranca",
                                            size=22,
                                            weight=ft.FontWeight.BOLD,
                                            color=COLOR_TEXT,
                                        ),
                                        ft.Text(
                                            "Ultimos 200 eventos. Senhas e documentos nao sao registrados.",
                                            size=12,
                                            color="#667085",
                                        ),
                                    ],
                                ),
                                progress,
                                refresh_button,
                            ]
                        ),
                        status,
                        events_area,
                    ]
                ),
            ),
        ),
    )
    await reload_events()
