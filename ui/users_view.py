"""Administracao de usuarios do CVJAPP."""

import asyncio
from collections.abc import Awaitable, Callable

import flet as ft

from core.auth import (
    AuthenticatedUser,
    UserRecord,
    create_user,
    list_users,
    reset_user_password,
    set_user_active,
    unlock_user,
)


COLOR_BG = "#F6EEF6"
COLOR_HEADER = "#8B5A91"
COLOR_TEXT = "#503054"
COLOR_BORDER = "#D2B8D8"


async def show_user_management(
    page: ft.Page,
    current_user: AuthenticatedUser,
    on_back: Callable[[], Awaitable[None]],
    on_logout: Callable[[], Awaitable[None]],
) -> None:
    page.clean()
    page.title = "CVJAPP - Usuarios"
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.vertical_alignment = ft.MainAxisAlignment.START

    status = ft.Text("", size=13, color=COLOR_TEXT, visible=False)
    progress = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)
    users_column = ft.Column(spacing=10)

    def close_dialog(dialog: ft.AlertDialog) -> None:
        dialog.open = False
        page.update()

    async def reload_users() -> None:
        progress.visible = True
        page.update()
        try:
            records = await asyncio.to_thread(list_users, current_user.id)
            users_column.controls = [user_card(record) for record in records]
        except Exception:
            status.value = "Nao foi possivel carregar os usuarios."
            status.color = "#B42318"
            status.visible = True
        finally:
            progress.visible = False
            page.update()

    async def toggle_user(event) -> None:
        target_id, new_state = event.control.data
        try:
            await asyncio.to_thread(
                set_user_active, current_user.id, target_id, new_state
            )
        except Exception as error:
            status.value = str(error) or "Nao foi possivel alterar o usuario."
            status.color = "#B42318"
            status.visible = True
            page.update()
        else:
            status.value = "Acesso atualizado com sucesso."
            status.color = "#067647"
            status.visible = True
            await reload_users()

    async def unlock_access(event) -> None:
        target_id = int(event.control.data)
        event.control.disabled = True
        page.update()
        try:
            await asyncio.to_thread(unlock_user, current_user.id, target_id)
        except Exception as error:
            status.value = str(error) or "Nao foi possivel desbloquear o usuario."
            status.color = "#B42318"
            status.visible = True
            page.update()
        else:
            status.value = "Usuario desbloqueado com sucesso."
            status.color = "#067647"
            status.visible = True
            await reload_users()

    def user_card(record: UserRecord) -> ft.Container:
        role_label = "Administrador" if record.role == "admin" else "Operador"
        if record.is_locked:
            state_label = f"Bloqueado ate {record.locked_until}"
        else:
            state_label = "Ativo" if record.active else "Inativo"
        action_controls = [
            ft.TextButton(
                "Redefinir senha",
                icon=ft.Icons.PASSWORD,
                data=record.id,
                on_click=open_reset_dialog,
            )
        ]
        if record.is_locked:
            action_controls.append(
                ft.TextButton(
                    "Desbloquear",
                    icon=ft.Icons.LOCK_OPEN,
                    data=record.id,
                    on_click=unlock_access,
                )
            )
        action_controls.append(
            ft.Button(
                "Desativar" if record.active else "Ativar",
                data=(record.id, not record.active),
                disabled=record.id == current_user.id,
                on_click=toggle_user,
            )
        )
        return ft.Container(
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, COLOR_BORDER),
            border_radius=14,
            padding=14,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ACCOUNT_CIRCLE_OUTLINED, color=COLOR_HEADER),
                            ft.Column(
                                expand=True,
                                spacing=1,
                                controls=[
                                    ft.Text(record.display_name, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"@{record.username} - {role_label}", size=12),
                                ],
                            ),
                            ft.Text(
                                state_label,
                                color=(
                                    "#B42318"
                                    if record.is_locked or not record.active
                                    else "#067647"
                                ),
                            ),
                        ]
                    ),
                    ft.Text(f"Ultimo acesso: {record.last_login}", size=11),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        wrap=True,
                        controls=action_controls,
                    ),
                ],
            ),
        )

    create_name = ft.TextField(label="Nome de exibicao")
    create_username = ft.TextField(label="Usuario", autocorrect=False)
    create_password = ft.TextField(
        label="Senha inicial",
        hint_text="Minimo de 6 caracteres",
        password=True,
        can_reveal_password=True,
    )
    create_role = ft.Dropdown(
        label="Perfil",
        value="operador",
        options=[
            ft.DropdownOption(key="operador", text="Operador"),
            ft.DropdownOption(key="admin", text="Administrador"),
        ],
    )
    create_error = ft.Text("", color="#B42318", size=12, visible=False)

    async def save_new_user(_event=None) -> None:
        create_save.disabled = True
        create_error.visible = False
        page.update()
        try:
            await asyncio.to_thread(
                create_user,
                current_user.id,
                create_username.value or "",
                create_name.value or "",
                create_password.value or "",
                create_role.value or "operador",
            )
        except Exception as error:
            create_error.value = str(error) or "Nao foi possivel criar o usuario."
            create_error.visible = True
            create_save.disabled = False
            page.update()
        else:
            create_dialog.open = False
            status.value = "Usuario criado com sucesso."
            status.color = "#067647"
            status.visible = True
            await reload_users()

    create_save = ft.Button("Criar usuario", on_click=save_new_user)
    create_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Novo usuario"),
        content=ft.Container(
            width=380,
            content=ft.Column(
                tight=True,
                controls=[
                    create_name,
                    create_username,
                    create_password,
                    create_role,
                    create_error,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: close_dialog(create_dialog)),
            create_save,
        ],
    )

    def open_create_dialog(_event=None) -> None:
        create_name.value = ""
        create_username.value = ""
        create_password.value = ""
        create_role.value = "operador"
        create_error.visible = False
        create_save.disabled = False
        create_dialog.open = True
        page.update()

    reset_target_id = 0
    reset_password = ft.TextField(
        label="Nova senha",
        hint_text="Minimo de 6 caracteres",
        password=True,
        can_reveal_password=True,
    )
    reset_error = ft.Text("", color="#B42318", size=12, visible=False)

    async def save_reset(_event=None) -> None:
        reset_save.disabled = True
        reset_error.visible = False
        page.update()
        try:
            await asyncio.to_thread(
                reset_user_password,
                current_user.id,
                reset_target_id,
                reset_password.value or "",
            )
        except Exception as error:
            reset_error.value = str(error) or "Nao foi possivel redefinir a senha."
            reset_error.visible = True
            reset_save.disabled = False
            page.update()
        else:
            reset_dialog.open = False
            status.value = "Senha redefinida com sucesso."
            status.color = "#067647"
            status.visible = True
            page.update()

    reset_save = ft.Button("Salvar senha", on_click=save_reset)
    reset_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Redefinir senha"),
        content=ft.Column(tight=True, controls=[reset_password, reset_error]),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: close_dialog(reset_dialog)),
            reset_save,
        ],
    )

    def open_reset_dialog(event) -> None:
        nonlocal reset_target_id
        reset_target_id = int(event.control.data)
        reset_password.value = ""
        reset_error.visible = False
        reset_save.disabled = False
        reset_dialog.open = True
        page.update()

    page.overlay.extend([create_dialog, reset_dialog])
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
                        "Usuarios",
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
                width=620,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(
                                    "Gerenciar acessos",
                                    size=23,
                                    weight=ft.FontWeight.BOLD,
                                    color=COLOR_TEXT,
                                ),
                                progress,
                            ],
                        ),
                        ft.Button(
                            "Novo usuario",
                            icon=ft.Icons.PERSON_ADD,
                            on_click=open_create_dialog,
                        ),
                        status,
                        users_column,
                    ]
                ),
            ),
        ),
    )
    await reload_users()
