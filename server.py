"""Aplicacao local protegida do CVJAPP."""

import asyncio
import logging
import multiprocessing
import os
import secrets
import threading
import time
import webbrowser

import flet as ft
import uvicorn

from core.auth import AuthenticatedUser, get_active_user
from core.base_status import BaseUpdateStatus, status_presentation
from core.config import settings
from core.paths import resource_path, sql_upload_dir
from db.audit import record_audit_event
from db.repo import obter_status_atualizacao_base
from ui.audit_view import show_audit_log
from ui.chamada_view import build_chamada
from ui.login_view import show_login
from ui.mobile_view import build_mobile_cadastro, build_mobile_home
from ui.main_view import build_main
from ui.users_view import show_user_management


def configurar_chave_upload() -> str:
    """Garante a chave usada pelo Flet para assinar uploads do navegador."""

    if not os.environ.get("FLET_SECRET_KEY"):
        os.environ["FLET_SECRET_KEY"] = secrets.token_urlsafe(32)
    return os.environ["FLET_SECRET_KEY"]


class WebSocketDisconnectFilter(logging.Filter):
    def filter(self, record):
        exc_info = record.exc_info
        if not exc_info:
            return True
        exc = exc_info[1]
        while exc:
            if exc.__class__.__name__ in {
                "WebSocketDisconnect",
                "ClientDisconnected",
                "ConnectionClosedError",
                "ConnectionClosedOK",
            } or isinstance(exc, ConnectionAbortedError):
                return False
            exc = exc.__cause__ or exc.__context__
        return True


def configurar_logs() -> None:
    filtro = WebSocketDisconnectFilter()
    for nome in ("uvicorn.error", "uvicorn", "starlette", ""):
        logging.getLogger(nome).addFilter(filtro)


def _access_bar(
    page: ft.Page,
    user: AuthenticatedUser,
    logout,
    base_status_badge: ft.Control,
    compact: bool = False,
) -> ft.Container:
    if compact:
        controls = [
            ft.Icon(ft.Icons.VERIFIED_USER_OUTLINED, color=ft.Colors.WHITE),
            ft.Text(
                user.display_name,
                color=ft.Colors.WHITE,
                expand=True,
                weight=ft.FontWeight.BOLD,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            base_status_badge,
        ]
        if user.is_admin:
            controls.append(
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    icon_color=ft.Colors.WHITE,
                    tooltip="Menu administrativo",
                    items=[
                        ft.PopupMenuItem(
                            content="Auditoria",
                            icon=ft.Icons.HISTORY,
                            on_click=lambda _: page.go("/auditoria"),
                        ),
                        ft.PopupMenuItem(
                            content="Usuarios",
                            icon=ft.Icons.MANAGE_ACCOUNTS,
                            on_click=lambda _: page.go("/usuarios"),
                        ),
                    ],
                )
            )
        controls.append(
            ft.IconButton(
                icon=ft.Icons.LOGOUT,
                icon_color=ft.Colors.WHITE,
                tooltip="Sair",
                on_click=lambda _: page.run_task(logout),
            )
        )
        return ft.Container(
            bgcolor="#6B3F6B",
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            content=ft.Row(
                controls=controls,
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    controls = [
        ft.Icon(ft.Icons.VERIFIED_USER_OUTLINED, color=ft.Colors.WHITE),
        ft.Text(
            f"{user.display_name} ({'Administrador' if user.is_admin else 'Operador'})",
            color=ft.Colors.WHITE,
            expand=True,
            weight=ft.FontWeight.BOLD,
        ),
        base_status_badge,
    ]
    if user.is_admin:
        controls.append(
            ft.TextButton(
                "Auditoria",
                icon=ft.Icons.HISTORY,
                style=ft.ButtonStyle(color=ft.Colors.WHITE),
                on_click=lambda _: page.go("/auditoria"),
            )
        )
        controls.append(
            ft.TextButton(
                "Usuarios",
                icon=ft.Icons.MANAGE_ACCOUNTS,
                style=ft.ButtonStyle(color=ft.Colors.WHITE),
                on_click=lambda _: page.go("/usuarios"),
            )
        )
    controls.append(
        ft.IconButton(
            icon=ft.Icons.LOGOUT,
            icon_color=ft.Colors.WHITE,
            tooltip="Sair",
            on_click=lambda _: page.run_task(logout),
        )
    )
    return ft.Container(
        bgcolor="#6B3F6B",
        padding=ft.Padding.symmetric(horizontal=12, vertical=5),
        content=ft.Row(controls=controls),
    )


async def build_app(page: ft.Page) -> None:
    """Cria uma sessao Flet protegida por autenticacao."""

    current_user: AuthenticatedUser | None = None
    requested_route = page.route or "/"
    session_started_at: float | None = None
    session_version = 0
    login_notice: str | None = None
    base_status_dot = ft.Container(
        width=12,
        height=12,
        border_radius=6,
        bgcolor=ft.Colors.RED_600,
    )
    base_status_label = ft.Text(
        "",
        size=12,
        color=ft.Colors.WHITE,
        visible=False,
        no_wrap=True,
    )
    base_status_badge = ft.Container(
        tooltip="Verificando a atualizacao da base...",
        content=ft.Row(
            [base_status_dot, base_status_label],
            spacing=5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    async def refresh_base_status() -> None:
        try:
            status = await asyncio.to_thread(obter_status_atualizacao_base)
        except Exception:
            logging.exception("Nao foi possivel verificar a atualizacao da base.")
            status = BaseUpdateStatus(diagnosis_filled=False, available=False)
        updated, label, tooltip = status_presentation(status)
        base_status_dot.bgcolor = (
            ft.Colors.GREEN_600 if updated else ft.Colors.RED_600
        )
        base_status_label.value = label
        base_status_label.visible = bool(label)
        base_status_badge.tooltip = tooltip
        if current_user is not None:
            page.update()

    async def end_session(
        action: str,
        *,
        notice: str | None = None,
        outcome: str = "success",
    ) -> None:
        nonlocal current_user, session_started_at, session_version, login_notice
        departing_user = current_user
        current_user = None
        session_started_at = None
        session_version += 1
        login_notice = notice
        if departing_user is not None:
            try:
                await asyncio.to_thread(
                    record_audit_event,
                    actor_id=departing_user.id,
                    action=action,
                    entity_type="session",
                    outcome=outcome,
                )
            except Exception:
                logging.exception("Nao foi possivel registrar o fim da sessao.")
        page.go("/login")

    async def logout() -> None:
        await end_session("auth.logout")

    async def validate_session(expected_version: int | None = None) -> bool:
        nonlocal current_user
        if current_user is None:
            return False
        if expected_version is not None and expected_version != session_version:
            return False
        if session_started_at is None or (
            time.monotonic() - session_started_at
            >= settings.session_max_minutes * 60
        ):
            await end_session(
                "auth.session_expired",
                notice="Sua sessao expirou. Entre novamente.",
            )
            return False
        try:
            refreshed_user = await asyncio.to_thread(
                get_active_user,
                current_user.id,
                current_user.auth_version,
            )
        except Exception:
            logging.exception("Nao foi possivel revalidar a sessao.")
            await end_session(
                "auth.session_revoked",
                notice="Nao foi possivel validar sua sessao. Entre novamente.",
                outcome="failure",
            )
            return False
        if refreshed_user is None:
            await end_session(
                "auth.session_revoked",
                notice="Seu acesso foi encerrado por um administrador.",
                outcome="denied",
            )
            return False
        current_user = refreshed_user
        return True

    async def session_guard(version: int) -> None:
        while current_user is not None and version == session_version:
            await asyncio.sleep(settings.session_recheck_seconds)
            if not await validate_session(version):
                return

    async def base_status_guard(version: int) -> None:
        while current_user is not None and version == session_version:
            await asyncio.sleep(30)
            if current_user is None or version != session_version:
                return
            await refresh_base_status()

    async def render_authenticated_route() -> None:
        route = (page.route or "/").split("?", 1)[0].rstrip("/").lower() or "/"
        page.clean()
        if route == "/usuarios" and current_user and current_user.is_admin:
            await show_user_management(
                page,
                current_user,
                on_back=go_home,
                on_logout=logout,
            )
            return
        if route == "/auditoria" and current_user and current_user.is_admin:
            await show_audit_log(
                page,
                current_user,
                on_back=go_home,
                on_logout=logout,
            )
            return
        if route == "/chamada":
            build_chamada(page)
        elif route == "/celular/chamada":
            build_chamada(page, back_route="/Celular")
        elif route == "/celular/cadastro":
            build_mobile_cadastro(page)
        elif route == "/celular":
            build_mobile_home(page)
        else:
            build_main(page, current_user)

        if current_user:
            page.controls.insert(
                0,
                _access_bar(
                    page,
                    current_user,
                    logout,
                    base_status_badge,
                    compact=route.startswith("/celular"),
                ),
            )
            page.update()

    async def go_home() -> None:
        page.go("/")

    async def authenticated(user: AuthenticatedUser) -> None:
        nonlocal current_user, session_started_at, session_version
        current_user = user
        session_started_at = time.monotonic()
        session_version += 1
        await refresh_base_status()
        page.run_task(session_guard, session_version)
        page.run_task(base_status_guard, session_version)
        target = requested_route if requested_route != "/login" else "/"
        if (page.route or "/") == target:
            await render_authenticated_route()
        else:
            page.go(target)

    async def route_changed(_event=None) -> None:
        nonlocal requested_route, login_notice
        route = (page.route or "/").split("?", 1)[0].rstrip("/").lower() or "/"
        if current_user is None:
            if route != "/login":
                requested_route = route
            notice = login_notice
            login_notice = None
            await show_login(page, authenticated, notice=notice)
            return
        if not await validate_session():
            return
        await render_authenticated_route()

    page.on_route_change = route_changed
    await route_changed()


configurar_logs()
configurar_chave_upload()
app = ft.run(
    build_app,
    export_asgi_app=True,
    assets_dir=resource_path("assets"),
    upload_dir=str(sql_upload_dir()),
)


def abrir_browser_local() -> None:
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8550", new=2)


def main() -> None:
    threading.Thread(target=abrir_browser_local, daemon=True).start()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8550")),
        log_level="info",
        log_config=None,
        access_log=settings.app_env != "production",
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
