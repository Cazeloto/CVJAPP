from __future__ import annotations

import asyncio
import os
import unicodedata
from datetime import datetime

import flet as ft

from core.fila_rules import contar_tratamentos_indicados, tipo_fila_indicada
from core.config import get_pdf_dir
from db.repo import (
    atualizar_preferencial_consulente,
    atualizar_status_tratamentos,
    buscar_cliente_por_id,
    buscar_clientes,
    buscar_tratamentos_ativos,
    existe_retorno_hoje,
    existe_retorno_pref_hoje,
    existe_triagem_hoje,
    existe_triagem_pref_hoje,
    inserir_consulente,
    obter_senha_hoje,
    obter_senhas_hoje,
    registrar_retorno,
    registrar_retorno_pref,
    registrar_triagem,
    registrar_triagem_pref,
    registrar_uso_cirurgia,
    registrar_uso_cromo,
    registrar_uso_massagem,
    registrar_uso_passe,
    registrar_uso_ponto,
    remover_retorno,
    remover_retorno_pref,
    remover_triagem,
    remover_triagem_pref,
    reiniciar_tratamento,
)
from pdf.layout_a5 import gerar_pdf_plano_tratamento_a5
from print.win_print import imprimir_pdf_windows


COLOR_BG = "#F6EEF6"
COLOR_HEADER = "#8B5A91"
COLOR_TEXT = "#503054"


def _row_value(row, key: str, index: int, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[index]
    except (IndexError, TypeError):
        return default


def _normalizar_nome(value: str) -> str:
    value = " ".join((value or "").strip().split())
    value = unicodedata.normalize("NFD", value)
    return "".join(c for c in value if unicodedata.category(c) != "Mn").upper()


def _close_dialog(page: ft.Page, dialog):
    dialog.open = False
    page.update()


def _setup_mobile_page(page: ft.Page, title: str):
    page.title = title
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed=COLOR_HEADER,
        visual_density=ft.VisualDensity.COMFORTABLE,
    )


def _header(page: ft.Page, title: str, back_route: str | None = None):
    controls = []
    if back_route:
        controls.append(
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                icon_color=ft.Colors.WHITE,
                tooltip="Voltar",
                on_click=lambda e: page.go(back_route),
            )
        )
    controls.extend(
        [
            ft.Image(
                src="Novologo.jpg",
                width=46,
                height=42,
                fit=(
                    ft.ImageFit.CONTAIN
                    if hasattr(ft, "ImageFit")
                    else ft.BoxFit.CONTAIN
                ),
            ),
            ft.Text(
                title,
                expand=True,
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ),
        ]
    )
    return ft.Container(
        bgcolor=COLOR_HEADER,
        padding=ft.Padding(left=8, top=10, right=12, bottom=10),
        content=ft.Row(controls, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )


def build_mobile_home(page: ft.Page):
    _setup_mobile_page(page, "CVJAPP no celular")

    def menu_card(title, subtitle, icon, color, route):
        return ft.Container(
            ink=True,
            on_click=lambda e: page.go(route),
            bgcolor=ft.Colors.WHITE,
            border_radius=16,
            padding=20,
            content=ft.Row(
                [
                    ft.Container(
                        width=58,
                        height=58,
                        border_radius=16,
                        bgcolor=color,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=32, color=ft.Colors.WHITE),
                    ),
                    ft.Column(
                        [
                            ft.Text(title, size=21, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                            ft.Text(subtitle, size=13, color=ft.Colors.GREY_700),
                        ],
                        spacing=3,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=COLOR_HEADER),
                ],
                spacing=14,
            ),
        )

    page.add(
        _header(page, "CVJAPP — Celular"),
        ft.Container(
            padding=16,
            content=ft.Column(
                [
                    ft.Text(
                        "O que você deseja fazer?",
                        size=16,
                        color=COLOR_TEXT,
                        weight=ft.FontWeight.W_600,
                    ),
                    menu_card(
                        "Cadastro",
                        "Buscar, cadastrar e encaminhar às filas",
                        ft.Icons.PERSON_ADD_ALT_1,
                        "#6E4A75",
                        "/Celular/cadastro",
                    ),
                    menu_card(
                        "Chamada",
                        "Acompanhar e concluir os atendimentos",
                        ft.Icons.CAMPAIGN,
                        "#2E7D5B",
                        "/Celular/chamada",
                    ),
                    ft.TextButton(
                        "Abrir versão completa",
                        icon=ft.Icons.DESKTOP_WINDOWS,
                        on_click=lambda e: page.go("/"),
                    ),
                ],
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        ),
    )


def build_mobile_cadastro(page: ft.Page):
    _setup_mobile_page(page, "Cadastro — CVJAPP")
    selected = {"cid": None}
    search_version = {"value": 0}

    status = ft.Text("Busque um consulente ou faça um novo cadastro.", color=COLOR_TEXT)
    search_results = ft.Column(spacing=8)
    detail_area = ft.Column(spacing=12)

    def notify(message: str, success: bool = True):
        page.snack_bar = ft.SnackBar(
            ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.GREEN_700 if success else ft.Colors.RED_700,
        )
        page.snack_bar.open = True
        page.update()

    async def load_person(cid: int):
        selected["cid"] = cid
        status.value = "Carregando cadastro..."
        page.update()
        try:
            data, treatments, queue_state, queue_passwords = await asyncio.gather(
                asyncio.to_thread(buscar_cliente_por_id, cid),
                asyncio.to_thread(buscar_tratamentos_ativos, cid),
                asyncio.to_thread(_queue_state, cid),
                asyncio.to_thread(obter_senhas_hoje, cid),
            )
            render_person(data, treatments, queue_state, queue_passwords)
        except Exception as ex:
            status.value = f"Não foi possível abrir o cadastro: {ex}"
            page.update()

    def queue_recommendation(data, treatments):
        quantities = (
            int(_row_value(data, "con_passe", 6, 0) or 0),
            int(_row_value(data, "con_cromoterapia", 19, 0) or 0),
            int(_row_value(data, "con_massagem", 20, 0) or 0),
            int(_row_value(data, "con_cirurgia", 21, 0) or 0),
            int(_row_value(data, "con_pontos", 24, 0) or 0),
        )
        preferred = str(_row_value(data, "con_preferencial", 4, "") or "").strip().upper()
        preferred = preferred in ("X", "P", "S", "1", "SIM", "TRUE")
        queue_type = tipo_fila_indicada(quantities, treatments)
        queue = f"{queue_type}{'pref' if preferred else ''}"
        labels = {
            "retorno": "Retorno",
            "retornopref": "Retorno Preferencial",
            "triagem": "Triagem",
            "triagempref": "Triagem Preferencial",
        }
        count = contar_tratamentos_indicados(quantities, treatments)
        return queue, labels[queue], count

    def queue_button(key, label, active):
        return ft.ElevatedButton(
            ("Remover de " if active else "Enviar para ") + label,
            icon=ft.Icons.REMOVE_CIRCLE if active else ft.Icons.ADD_CIRCLE,
            height=50,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_700 if active else COLOR_HEADER,
                color=ft.Colors.WHITE,
            ),
            on_click=lambda e: page.run_task(toggle_queue, key, active),
        )

    async def register_treatment_use(func, label: str):
        cid = selected["cid"]
        if not cid:
            return
        try:
            result = await asyncio.to_thread(func, int(cid))
            if result:
                notify(f"{label} lançado com sucesso.")
            else:
                notify(f"Sem saldo disponível de {label}.", False)
            await load_person(int(cid))
        except Exception as ex:
            notify(f"Erro ao lançar {label}: {ex}", False)

    def treatment_button(label, authorized, completed, func):
        available = authorized > completed
        return ft.ElevatedButton(
            f"{label}: {completed}/{authorized}",
            icon=ft.Icons.ADD_TASK,
            height=48,
            style=ft.ButtonStyle(
                bgcolor="#4CAF50" if available else "#E8E8E8",
                color=ft.Colors.WHITE if available else ft.Colors.BLACK,
            ),
            on_click=lambda e: page.run_task(register_treatment_use, func, label),
        )

    async def toggle_preferred(value: bool, control):
        cid = selected["cid"]
        if not cid:
            return
        control.disabled = True
        page.update()
        try:
            updated = await asyncio.to_thread(
                atualizar_preferencial_consulente, int(cid), bool(value)
            )
            if not updated:
                raise RuntimeError("O banco não confirmou a alteração.")
            notify(
                "Consulente marcado como preferencial."
                if value
                else "Consulente marcado como normal."
            )
            await load_person(int(cid))
        except Exception as ex:
            control.disabled = False
            control.value = not value
            notify(f"Erro ao alterar preferencial: {ex}", False)
            page.update()

    async def print_treatment(data, treatments):
        cid = int(_row_value(data, "con_codigo", 0, 0) or 0)
        if not cid:
            notify("Não foi possível identificar o consulente.", False)
            return
        status.value = "Preparando impressão..."
        page.update()

        def generate_and_print():
            pdf_dir = get_pdf_dir()
            os.makedirs(pdf_dir, exist_ok=True)
            queue_type, queue_number = obter_senha_hoje(cid)
            path = os.path.join(
                str(pdf_dir),
                f"plano_trat_{cid}_{datetime.now():%Y%m%d_%H%M%S}.pdf",
            )
            gerar_pdf_plano_tratamento_a5(
                path,
                data,
                treatments,
                logo_path=None,
                senha_tipo=queue_type,
                senha_numero=queue_number,
            )
            imprimir_pdf_windows(path)
            return path

        try:
            await asyncio.to_thread(generate_and_print)
            status.value = "Plano enviado para impressão."
            notify("Plano enviado para impressão.")
        except Exception as ex:
            status.value = "Falha na impressão."
            notify(f"Erro ao imprimir: {ex}", False)
        page.update()

    async def execute_plan_action(action: str, dialog):
        cid = selected["cid"]
        if not cid:
            return
        dialog.open = False
        status.value = "Processando..."
        page.update()
        try:
            if action == "desistir":
                count = await asyncio.to_thread(
                    atualizar_status_tratamentos, int(cid), "D", "A"
                )
                message = f"{count} tratamento(s) marcado(s) como desistência."
            elif action == "finalizar":
                count = await asyncio.to_thread(
                    atualizar_status_tratamentos, int(cid), "F", "A"
                )
                message = f"{count} tratamento(s) finalizado(s)."
            else:
                result = await asyncio.to_thread(reiniciar_tratamento, int(cid))
                if str(result).strip().lower() == "tratamento em aberto":
                    notify("Existe tratamento em aberto. Não é possível reiniciar.", False)
                    await load_person(int(cid))
                    return
                message = "Tratamento reiniciado com sucesso."
            notify(message)
            await load_person(int(cid))
        except Exception as ex:
            status.value = "Falha ao atualizar o tratamento."
            notify(f"Erro: {ex}", False)

    def confirm_plan_action(action: str):
        settings = {
            "desistir": (
                "Confirmar desistência",
                "Deseja marcar todos os tratamentos em aberto como desistência?",
            ),
            "finalizar": (
                "Confirmar finalização",
                "Deseja finalizar todos os tratamentos em aberto?",
            ),
            "reiniciar": (
                "Confirmar reinício",
                "Deseja reiniciar o tratamento? O diagnóstico atual será movido para o anterior e o atual será limpo.",
            ),
        }
        title, message = settings[action]
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: _close_dialog(page, dialog),
                ),
                ft.ElevatedButton(
                    "Confirmar",
                    on_click=lambda e: page.run_task(
                        execute_plan_action, action, dialog
                    ),
                ),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def render_person(data, treatments, states, queue_passwords):
        if not data:
            detail_area.controls = [ft.Text("Cadastro não encontrado.")]
            page.update()
            return
        name = str(_row_value(data, "con_nome", 1, "") or "")
        birth = _row_value(data, "con_nascim", 3, "")
        birth_text = birth.strftime("%d/%m/%Y") if hasattr(birth, "strftime") else str(birth or "-")
        preferred_raw = str(
            _row_value(data, "con_preferencial", 4, "") or ""
        ).strip().upper()
        is_preferred = preferred_raw in ("X", "P", "S", "1", "SIM", "TRUE")
        recommended_key, recommended_label, count = queue_recommendation(data, treatments)
        treatment_values = _treatment_values(data)
        treatment_functions = {
            "Passe": registrar_uso_passe,
            "Cromo": registrar_uso_cromo,
            "Massagem": registrar_uso_massagem,
            "Cirurgia": registrar_uso_cirurgia,
            "Ponto": registrar_uso_ponto,
        }
        treatment_buttons = [
            treatment_button(
                label,
                authorized,
                completed,
                treatment_functions[label],
            )
            for label, authorized, completed in treatment_values
            if authorized > 0
        ]
        queue_labels = {
            "retorno": "Retorno",
            "retornopref": "Retorno Preferencial",
            "triagem": "Triagem",
            "triagempref": "Triagem Preferencial",
        }
        current_queue_controls = []
        if queue_passwords:
            current_queue_controls = [
                ft.Container(
                    bgcolor="#E8F0FE",
                    border_radius=10,
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Fila associada hoje",
                                weight=ft.FontWeight.BOLD,
                                color="#2855A6",
                            ),
                            *[
                                ft.Container(
                                    height=46,
                                    padding=ft.Padding(left=14, right=14),
                                    alignment=ft.Alignment.CENTER,
                                    bgcolor=ft.Colors.GREEN_700,
                                    border=ft.Border.all(3, "#173A63"),
                                    border_radius=8,
                                    content=ft.Text(
                                        f"{item['fila']} • Senha "
                                        f"{item['prefixo']}-{int(item['numero']):03d}",
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                )
                                for item in queue_passwords
                            ],
                        ],
                        spacing=4,
                    ),
                )
            ]
        detail_area.controls = [
            ft.Container(
                bgcolor=ft.Colors.WHITE,
                border_radius=14,
                padding=16,
                content=ft.Column(
                    [
                        ft.Text(name, size=21, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                        ft.Text(f"Nascimento: {birth_text}", color=ft.Colors.GREY_700),
                        ft.Switch(
                            label="Preferencial",
                            value=is_preferred,
                            active_color="#006B2E",
                            active_track_color="#BFE8CC",
                            on_change=lambda e: page.run_task(
                                toggle_preferred, bool(e.control.value), e.control
                            ),
                        ),
                        ft.Container(
                            bgcolor="#F3E5F5",
                            border_radius=10,
                            padding=10,
                            content=ft.Text(
                                f"Fila indicada: {recommended_label} ({count} tratamento(s))",
                                weight=ft.FontWeight.BOLD,
                                color=COLOR_HEADER,
                            ),
                        ),
                        *current_queue_controls,
                        _diagnosis_card(data),
                        _performed_treatments_card(treatments),
                        queue_button(
                            recommended_key,
                            recommended_label,
                            states[recommended_key],
                        ),
                        ft.ExpansionTile(
                            title=ft.Text("Outras filas (exceção)"),
                            controls=[
                                ft.Container(
                                    padding=ft.Padding(left=8, right=8, bottom=10),
                                    content=ft.Column(
                                        [
                                            queue_button(key, label, states[key])
                                            for key, label in queue_labels.items()
                                            if key != recommended_key
                                        ],
                                        spacing=8,
                                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                    ),
                                )
                            ],
                        ),
                        ft.Text(
                            "Tratamentos",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=COLOR_TEXT,
                        ),
                        ft.Row(
                            treatment_buttons
                            or [
                                ft.Text(
                                    "Nenhum tratamento associado.",
                                    color=ft.Colors.GREY_700,
                                )
                            ],
                            wrap=True,
                            spacing=7,
                            run_spacing=7,
                        ),
                        ft.ElevatedButton(
                            "Imprimir plano",
                            icon=ft.Icons.PRINT,
                            height=50,
                            style=ft.ButtonStyle(
                                bgcolor="#2855A6",
                                color=ft.Colors.WHITE,
                            ),
                            on_click=lambda e: page.run_task(
                                print_treatment, data, treatments
                            ),
                        ),
                        ft.Divider(),
                        ft.Text(
                            "Situação do tratamento",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=COLOR_TEXT,
                        ),
                        ft.ElevatedButton(
                            "Desistiu",
                            icon=ft.Icons.CANCEL,
                            height=48,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.RED_600,
                                color=ft.Colors.WHITE,
                            ),
                            on_click=lambda e: confirm_plan_action("desistir"),
                        ),
                        ft.ElevatedButton(
                            "Finalizar",
                            icon=ft.Icons.DONE_ALL,
                            height=48,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.BLUE_700,
                                color=ft.Colors.WHITE,
                            ),
                            on_click=lambda e: confirm_plan_action("finalizar"),
                        ),
                        ft.ElevatedButton(
                            "Reiniciar",
                            icon=ft.Icons.LOCK if treatments else ft.Icons.REPLAY,
                            height=48,
                            disabled=bool(treatments),
                            tooltip=(
                                "Existe tratamento em aberto."
                                if treatments
                                else "Reiniciar tratamento"
                            ),
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.PURPLE_700,
                                color=ft.Colors.WHITE,
                            ),
                            on_click=lambda e: confirm_plan_action("reiniciar"),
                        ),
                    ],
                    spacing=10,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            )
        ]
        status.value = "Cadastro carregado."
        page.update()

    async def toggle_queue(key: str, active: bool):
        cid = selected["cid"]
        if not cid:
            return
        add = {
            "retorno": registrar_retorno,
            "retornopref": registrar_retorno_pref,
            "triagem": registrar_triagem,
            "triagempref": registrar_triagem_pref,
        }
        remove = {
            "retorno": remover_retorno,
            "retornopref": remover_retorno_pref,
            "triagem": remover_triagem,
            "triagempref": remover_triagem_pref,
        }
        queue_labels = {
            "retorno": ("Retorno", "RT"),
            "retornopref": ("Retorno Preferencial", "RTP"),
            "triagem": ("Triagem", "T"),
            "triagempref": ("Triagem Preferencial", "TP"),
        }
        try:
            result = await asyncio.to_thread((remove if active else add)[key], cid)
            label, prefix = queue_labels[key]
            if active:
                notify(f"Consulente removido da fila {label}.")
            else:
                notify(
                    f"Consulente associado à fila {label}. "
                    f"Senha: {prefix}-{int(result):03d}."
                )
            await load_person(cid)
        except Exception as ex:
            notify(f"Erro ao atualizar a fila: {ex}", False)

    def select_search_result(cid, name):
        search_version["value"] += 1
        search_results.controls.clear()
        search_field.value = str(name or "")
        page.update()
        page.run_task(load_person, int(cid))

    def result_card(cid, name):
        return ft.Container(
            ink=True,
            on_click=lambda e: select_search_result(cid, name),
            bgcolor=ft.Colors.WHITE,
            border_radius=12,
            padding=14,
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.PERSON_OUTLINE, color=COLOR_HEADER),
                    ft.Text(str(name), expand=True, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=COLOR_HEADER),
                ]
            ),
        )

    async def run_search(text: str, version: int):
        await asyncio.sleep(0.25)
        if version != search_version["value"]:
            return
        text = (text or "").strip()
        if not text:
            search_results.controls.clear()
            page.update()
            return
        try:
            rows = await asyncio.to_thread(buscar_clientes, text)
            if version != search_version["value"]:
                return
            search_results.controls = [
                result_card(
                    _row_value(row, "con_codigo", 0),
                    _row_value(row, "con_nome", 1, ""),
                )
                for row in rows
            ] or [ft.Text("Nenhum consulente encontrado.", color=ft.Colors.GREY_700)]
            page.update()
        except Exception as ex:
            notify(f"Erro na busca: {ex}", False)

    def search_changed(e):
        search_version["value"] += 1
        page.run_task(run_search, e.control.value or "", search_version["value"])

    def clear_search(_event=None):
        search_version["value"] += 1
        selected["cid"] = None
        search_field.value = ""
        search_results.controls.clear()
        detail_area.controls.clear()
        status.value = "Busque um consulente ou faça um novo cadastro."
        page.update()
        page.run_task(search_field.focus)

    name_field = ft.TextField(
        label="Nome completo",
        hint_text="Ex.: MARIA DA SILVA",
        autocorrect=False,
    )
    sex_field = ft.Dropdown(
        label="Sexo",
        value="M",
        options=[ft.dropdown.Option("M"), ft.dropdown.Option("F")],
    )

    def format_birth(e):
        digits = "".join(character for character in (e.control.value or "") if character.isdigit())[:8]
        parts = [digits[:2]]
        if len(digits) > 2:
            parts.append(digits[2:4])
        if len(digits) > 4:
            parts.append(digits[4:8])
        formatted = "/".join(parts)
        if formatted != e.control.value:
            e.control.value = formatted
            try:
                position = len(formatted)
                e.control.selection = ft.TextSelection(position, position)
            except Exception:
                pass
            e.control.update()

    birth_field = ft.TextField(
        label="Nascimento",
        hint_text="DD/MM/AAAA",
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(
            allow=True,
            regex_string=r"[0-9/]",
            replacement_string="",
        ),
        max_length=10,
        on_change=format_birth,
    )
    preferred_field = ft.Switch(label="Preferencial", value=False)

    def close_dialog(e=None):
        new_dialog.open = False
        page.update()

    async def save_new(e=None):
        try:
            name = _normalizar_nome(name_field.value)
            if not name:
                raise ValueError("Informe o nome.")
            birth = datetime.strptime((birth_field.value or "").strip(), "%d/%m/%Y").date()
            cid = await asyncio.to_thread(
                inserir_consulente,
                name,
                sex_field.value or "M",
                birth,
                "X" if preferred_field.value else "",
            )
            close_dialog()
            notify("Consulente cadastrado com sucesso.")
            await load_person(int(cid))
        except ValueError as ex:
            message = str(ex)
            normalized_message = _normalizar_nome(message)
            if "JA EXISTE UM CONSULENTE" in normalized_message:
                message = (
                    f"O consulente “{_normalizar_nome(name_field.value)}” já está "
                    "cadastrado. Pesquise o nome existente antes de criar outro."
                )
            elif "TIME DATA" in message.upper() or "DOES NOT MATCH FORMAT" in message.upper():
                message = "Nascimento inválido. Informe uma data no formato DD/MM/AAAA."
            notify(message, False)
        except Exception as ex:
            notify(f"Erro ao cadastrar: {ex}", False)

    new_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Novo consulente"),
        content=ft.Container(
            width=420,
            content=ft.Column(
                [
                    name_field,
                    sex_field,
                    birth_field,
                    preferred_field,
                ],
                tight=True,
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=close_dialog),
            ft.ElevatedButton("Salvar", icon=ft.Icons.SAVE, on_click=save_new),
        ],
    )
    page.overlay.append(new_dialog)

    def open_new(e=None):
        name_field.value = ""
        sex_field.value = "M"
        birth_field.value = ""
        preferred_field.value = False
        new_dialog.open = True
        page.update()

    search_field = ft.TextField(
        label="Buscar consulente",
        hint_text="Digite o nome",
        prefix_icon=ft.Icons.SEARCH,
        suffix=ft.IconButton(
            icon=ft.Icons.CANCEL,
            icon_color=ft.Colors.RED_600,
            tooltip="Limpar busca",
            on_click=clear_search,
        ),
        on_change=search_changed,
        autofocus=True,
    )

    page.add(
        _header(page, "Cadastro", "/Celular"),
        ft.Container(
            padding=12,
            content=ft.Column(
                [
                    ft.ElevatedButton(
                        "Novo consulente",
                        icon=ft.Icons.PERSON_ADD_ALT_1,
                        height=52,
                        style=ft.ButtonStyle(bgcolor=COLOR_HEADER, color=ft.Colors.WHITE),
                        on_click=open_new,
                    ),
                    search_field,
                    search_results,
                    ft.Divider(),
                    status,
                    detail_area,
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        ),
    )


def _queue_state(cid: int):
    return {
        "retorno": bool(existe_retorno_hoje(cid)),
        "retornopref": bool(existe_retorno_pref_hoje(cid)),
        "triagem": bool(existe_triagem_hoje(cid)),
        "triagempref": bool(existe_triagem_pref_hoje(cid)),
    }


def _treatment_values(data):
    specs = (
        ("Passe", "con_passe", 6, "con_npasse", 7),
        ("Cromo", "con_cromoterapia", 19, "con_ncromo", 25),
        ("Massagem", "con_massagem", 20, "con_nmass", 26),
        ("Cirurgia", "con_cirurgia", 21, "con_ncirur", 27),
        ("Ponto", "con_pontos", 24, "con_nponto", 28),
    )
    return [
        (
            label,
            int(_row_value(data, authorized_key, authorized_index, 0) or 0),
            int(_row_value(data, completed_key, completed_index, 0) or 0),
        )
        for label, authorized_key, authorized_index, completed_key, completed_index in specs
    ]


def _treatment_mediums(treatment) -> str:
    names = [
        str(_row_value(treatment, "tra_medium", 0, "") or "").strip(),
        str(_row_value(treatment, "tra_medium2", 0, "") or "").strip(),
        str(_row_value(treatment, "tra_medium3", 0, "") or "").strip(),
    ]
    return " / ".join(name for name in names if name)


def _performed_treatments_card(treatments):
    performed = []
    for treatment in treatments or []:
        treatment_date = _row_value(treatment, "tra_data", 0)
        treatment_code = int(_row_value(treatment, "tra_codtra", 0, 0) or 0)
        if not treatment_date or treatment_code not in (1, 2, 3, 4, 5):
            continue
        description = str(
            _row_value(treatment, "tra_descricao", 0, "Tratamento") or "Tratamento"
        ).strip()
        date_text = (
            treatment_date.strftime("%d/%m/%Y")
            if hasattr(treatment_date, "strftime")
            else str(treatment_date)
        )
        mediums = _treatment_mediums(treatment) or "Médium não informado"
        performed.append(
            ft.Container(
                padding=ft.Padding(left=0, top=6, right=0, bottom=6),
                border=ft.Border(
                    bottom=ft.BorderSide(1, ft.Colors.GREY_300)
                ),
                content=ft.Column(
                    [
                        ft.Text(
                            f"{description} • {date_text}",
                            weight=ft.FontWeight.W_600,
                            color=COLOR_TEXT,
                        ),
                        ft.Text(
                            f"Médium(ns): {mediums}",
                            size=13,
                            color=ft.Colors.BLUE_800,
                            selectable=True,
                        ),
                    ],
                    spacing=2,
                ),
            )
        )
        if len(performed) == 10:
            break

    return ft.Container(
        bgcolor="#FAF7FB",
        border_radius=11,
        padding=12,
        content=ft.Column(
            [
                ft.Text(
                    "Tratamentos já realizados",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=COLOR_TEXT,
                ),
                *(
                    performed
                    or [
                        ft.Text(
                            "Nenhum tratamento realizado neste plano.",
                            color=ft.Colors.GREY_700,
                        )
                    ]
                ),
            ],
            spacing=4,
        ),
    )


def _diagnosis_card(data):
    diagnosis = str(_row_value(data, "con_diagnostico", 17, "") or "").strip()
    previous_diagnosis = str(
        _row_value(data, "con_diagnant", 18, "") or ""
    ).strip()
    return ft.Container(
        bgcolor="#FAF7FB",
        border_radius=11,
        padding=12,
        content=ft.Column(
            [
                ft.Text(
                    "Diagnóstico atual",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=COLOR_TEXT,
                ),
                ft.Text(
                    diagnosis or "Não informado.",
                    size=18,
                    weight=ft.FontWeight.W_500,
                    color=COLOR_TEXT,
                    selectable=True,
                ),
                ft.Divider(height=12, color=ft.Colors.GREY_300),
                ft.Text(
                    "Diagnóstico anterior",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=COLOR_TEXT,
                ),
                ft.Text(
                    previous_diagnosis or "Não informado.",
                    size=16,
                    weight=ft.FontWeight.W_500,
                    color=COLOR_TEXT,
                    selectable=True,
                ),
            ],
            spacing=6,
        ),
    )
