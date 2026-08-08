"""Tela de entrada do CVJAPP."""

import asyncio
from collections.abc import Awaitable, Callable

import flet as ft

from core.auth import (
    AuthenticatedUser,
    LoginLockedError,
    authenticate_user,
    initialize_auth_database,
)
from core.config import settings


COLOR_BG = "#C9A3C8"
COLOR_HEADER = "#8B5A91"
COLOR_TEXT = "#503054"
COLOR_BORDER = "#D2B8D8"


async def show_login(
    page: ft.Page,
    on_authenticated: Callable[[AuthenticatedUser], Awaitable[None]],
    notice: str | None = None,
) -> None:
    """Exibe a barreira de autenticacao antes de montar as telas internas."""

    page.clean()
    page.title = f"{settings.app_name} - Acesso"
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.scroll = None
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    auth_ready = False
    error_message = ft.Text(
        "",
        color="#B42318",
        size=13,
        text_align=ft.TextAlign.CENTER,
        visible=False,
    )
    if notice:
        error_message.value = notice
        error_message.color = "#B54708"
        error_message.visible = True

    async def login(_event=None) -> None:
        if not auth_ready:
            error_message.value = "Servico de autenticacao indisponivel."
            error_message.visible = True
            page.update()
            return

        login_button.disabled = True
        error_message.visible = False
        page.update()
        try:
            user = await asyncio.to_thread(
                authenticate_user,
                username.value or "",
                password.value or "",
            )
        except LoginLockedError as error:
            minutes = max(1, (error.retry_after_seconds + 59) // 60)
            password.value = ""
            error_message.value = (
                f"Acesso bloqueado temporariamente. Tente novamente em {minutes} "
                f"minuto{'s' if minutes != 1 else ''}."
            )
            error_message.color = "#B42318"
            error_message.visible = True
            login_button.disabled = False
            page.update()
            return
        except Exception:
            password.value = ""
            error_message.value = "Servico de autenticacao indisponivel. Tente novamente."
            error_message.color = "#B42318"
            error_message.visible = True
            login_button.disabled = False
            page.update()
            return

        if user is not None:
            password.value = ""
            await on_authenticated(user)
            return

        password.value = ""
        error_message.value = "Usuario ou senha invalidos."
        error_message.color = "#B42318"
        error_message.visible = True
        login_button.disabled = False
        page.update()
        password.focus()

    username = ft.TextField(
        label="Usuario",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        autofocus=True,
        autocorrect=False,
        bgcolor=ft.Colors.WHITE,
        border_color=COLOR_BORDER,
        focused_border_color=COLOR_HEADER,
        on_submit=login,
    )
    password = ft.TextField(
        label="Senha",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        bgcolor=ft.Colors.WHITE,
        border_color=COLOR_BORDER,
        focused_border_color=COLOR_HEADER,
        on_submit=login,
    )
    login_button = ft.Button(
        "Entrar",
        icon=ft.Icons.LOGIN,
        height=50,
        disabled=True,
        style=ft.ButtonStyle(bgcolor=COLOR_HEADER, color=ft.Colors.WHITE),
        on_click=login,
    )

    page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=20,
            content=ft.Container(
                width=420,
                bgcolor=ft.Colors.WHITE,
                border=ft.Border.all(1, COLOR_BORDER),
                border_radius=20,
                padding=24,
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    spacing=14,
                    controls=[
                        ft.Image(src="Novologo.jpg", height=105, fit=ft.BoxFit.CONTAIN),
                        ft.Text(
                            "Acesso restrito",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            color=COLOR_TEXT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "Entre para acessar o CVJAPP.",
                            size=14,
                            color="#766177",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        username,
                        password,
                        error_message,
                        login_button,
                    ],
                ),
            ),
        )
    )

    try:
        await asyncio.to_thread(initialize_auth_database)
    except Exception:
        error_message.value = (
            "Nao foi possivel iniciar o acesso. Verifique o banco e as configuracoes."
        )
        error_message.visible = True
    else:
        auth_ready = True
        login_button.disabled = False
    page.update()
