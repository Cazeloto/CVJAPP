from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path

import flet as ft

from core.config import get_pdf_dir
from db.repo import apagar_chamada, concluir_chamada, listar_painel_chamadas
from pdf.fechamento_gira import gerar_pdf_fechamento_gira


COLOR_BG = "#C9A3C8"
COLOR_HEADER = "#8B5A91"
COLOR_TEXT = "#5B315E"

FILAS = (
    ("retorno", "Retorno", "RET", ft.Icons.REPLAY, "#E8F0FE", "#2855A6"),
    (
        "retornopref",
        "Retorno Preferencial",
        "RET. PREF.",
        ft.Icons.STAR,
        "#FFF3CD",
        "#7A5900",
    ),
    ("triagem", "Triagem", "TRI", ft.Icons.FACT_CHECK, "#E2F4EA", "#19623A"),
    (
        "triagempref",
        "Triagem Preferencial",
        "TRI. PREF.",
        ft.Icons.WORKSPACE_PREMIUM,
        "#F3E5F5",
        "#6A3472",
    ),
)

PREFIXOS_FILA = {
    "retorno": "RT",
    "retornopref": "RTP",
    "triagem": "T",
    "triagempref": "TP",
}


def _padding_only(**kwargs):
    helper = getattr(ft.padding, "only", None)
    return helper(**kwargs) if helper else ft.Padding.only(**kwargs)


def _padding_symmetric(**kwargs):
    helper = getattr(ft.padding, "symmetric", None)
    return helper(**kwargs) if helper else ft.Padding.symmetric(**kwargs)


def _alignment_center():
    return getattr(ft.alignment, "center", None) or ft.Alignment.CENTER


def _border_all(width, color):
    helper = getattr(ft.border, "all", None)
    return helper(width, color) if helper else ft.Border.all(width, color)


def _rota_eh_chamada(rota: str | None) -> bool:
    caminho = (rota or "").split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return caminho.lower() in ("/chamada", "/celular/chamada")


def build_chamada(page: ft.Page, back_route: str = "/"):
    page.title = "Chamada da Gira - CVJ"
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.scroll = ft.ScrollMode.HIDDEN
    page.theme_mode = ft.ThemeMode.LIGHT

    state = {
        "carregando": False,
        "ativo": True,
        "falhas_update": 0,
        "erro_atualizacao_mostrado": False,
    }
    listas = {}
    contadores = {}
    contadores_abas = {}
    compartilhamento = ft.Share()

    def atualizar_pagina():
        try:
            page.update()
            state["falhas_update"] = 0
            return True
        except Exception:
            state["falhas_update"] += 1
            if state["falhas_update"] >= 3:
                state["ativo"] = False
            return False

    def aviso(texto: str, sucesso: bool = True):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(texto, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.GREEN_700 if sucesso else ft.Colors.RED_700,
        )
        page.snack_bar.open = True
        atualizar_pagina()

    dialogo_atual = {"controle": None}

    def fechar_dialogo(e=None):
        dialogo = dialogo_atual["controle"]
        if dialogo:
            dialogo.open = False
            atualizar_pagina()

    def executar_exclusao(fila: str, item: dict):
        fechar_dialogo()
        try:
            if apagar_chamada(fila, int(item["fila_codigo"])):
                aviso("Consulente apagado da fila.")
            else:
                aviso("Este item já foi removido em outro aparelho.", False)
            carregar()
        except Exception as ex:
            aviso(f"Erro ao apagar: {ex}", False)

    def confirmar_exclusao(fila: str, item: dict):
        nome = (item.get("con_nome") or "este consulente").strip()
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Apagar da fila?"),
            content=ft.Text(
                f"{nome} será removido sem entrar na contagem de chamados."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar_dialogo),
                ft.TextButton(
                    "Apagar",
                    icon=ft.Icons.DELETE_OUTLINE,
                    style=ft.ButtonStyle(color=ft.Colors.RED_700),
                    on_click=lambda e: executar_exclusao(fila, item),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dialogo_atual["controle"] = dialogo
        try:
            page.show_dialog(dialogo)
        except AttributeError:
            if dialogo not in page.overlay:
                page.overlay.append(dialogo)
            dialogo.open = True
            atualizar_pagina()

    def concluir(fila: str, item: dict):
        try:
            if concluir_chamada(fila, int(item["fila_codigo"])):
                aviso(f"{item.get('con_nome', 'Consulente')} concluído.")
            else:
                aviso("Este item já foi concluído ou removido em outro aparelho.", False)
            carregar()
        except Exception as ex:
            aviso(f"Erro ao concluir: {ex}", False)

    def card_consulente(fila: str, item: dict, fundo: str, destaque: str):
        numero = int(item.get("numero") or 0)
        nome = (item.get("con_nome") or "Sem nome").strip()
        senha = f"{PREFIXOS_FILA[fila]}-{numero:03d}"
        return ft.Container(
            bgcolor=ft.Colors.WHITE,
            border=_border_all(1, ft.Colors.GREY_300),
            border_radius=12,
            padding=12,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=92,
                                height=52,
                                alignment=_alignment_center(),
                                bgcolor=fundo,
                                border_radius=9,
                                content=ft.Text(
                                    senha,
                                    size=19,
                                    weight=ft.FontWeight.BOLD,
                                    color=destaque,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ),
                            ft.Text(
                                nome,
                                expand=True,
                                size=19,
                                weight=ft.FontWeight.BOLD,
                                color=COLOR_TEXT,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.ElevatedButton(
                                "Concluir",
                                icon=ft.Icons.CHECK_CIRCLE,
                                expand=True,
                                height=44,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.GREEN_700,
                                    color=ft.Colors.WHITE,
                                ),
                                on_click=lambda e, f=fila, i=item: concluir(f, i),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_700,
                                tooltip="Apagar da fila",
                                width=46,
                                height=44,
                                on_click=lambda e, f=fila, i=item: confirmar_exclusao(
                                    f, i
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        )

    def painel_fila(fila, titulo, icone, fundo, destaque):
        chamados = ft.Text("0", size=18, weight=ft.FontWeight.BOLD, color=destaque)
        faltam = ft.Text("0", size=18, weight=ft.FontWeight.BOLD, color=destaque)
        contadores[fila] = (chamados, faltam)

        lista = ft.ListView(expand=True, spacing=10, padding=_padding_only(bottom=18))
        listas[fila] = lista

        return ft.Container(
            expand=True,
            padding=_padding_only(left=12, top=12, right=12),
            content=ft.Column(
                expand=True,
                spacing=10,
                controls=[
                    ft.Container(
                        bgcolor=fundo,
                        border_radius=12,
                        padding=12,
                        content=ft.Column(
                            spacing=8,
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(icone, color=destaque, size=25),
                                        ft.Text(
                                            titulo,
                                            expand=True,
                                            size=19,
                                            weight=ft.FontWeight.BOLD,
                                            color=destaque,
                                        ),
                                    ]
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                                    controls=[
                                        ft.Column(
                                            spacing=0,
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                            controls=[
                                                chamados,
                                                ft.Text("Chamados", size=12, color=destaque),
                                            ],
                                        ),
                                        ft.Container(
                                            width=1, height=38, bgcolor=ft.Colors.GREY_400
                                        ),
                                        ft.Column(
                                            spacing=0,
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                            controls=[
                                                faltam,
                                                ft.Text("Faltam", size=12, color=destaque),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    lista,
                ],
            ),
        )

    paineis = {}
    for fila, titulo, titulo_curto, icone, fundo, destaque in FILAS:
        paineis[fila] = painel_fila(fila, titulo, icone, fundo, destaque)

    conteudo_fila = ft.Container(expand=True, content=paineis["retorno"])
    botoes_abas = {}

    def selecionar_fila(fila: str, atualizar: bool = True):
        state["fila_ativa"] = fila
        conteudo_fila.content = paineis[fila]
        for chave, controle in botoes_abas.items():
            selecionada = chave == fila
            controle.bgcolor = "#D9BAD8" if selecionada else "#C9A3C8"
            controle.border = ft.Border(
                bottom=ft.BorderSide(
                    width=4 if selecionada else 1,
                    color=COLOR_HEADER if selecionada else "#D9C4D8",
                )
            )
        if atualizar:
            atualizar_pagina()

    controles_navegacao = []
    for fila, _, titulo_curto, icone, _, _ in FILAS:
        contador_aba = ft.Text(
            "0",
            size=11,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
            text_align=ft.TextAlign.CENTER,
        )
        contadores_abas[fila] = contador_aba
        botao_aba = ft.Container(
            expand=True,
            height=76,
            padding=_padding_symmetric(horizontal=3, vertical=7),
            ink=True,
            on_click=lambda e, f=fila: selecionar_fila(f),
            content=ft.Column(
                spacing=3,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(icone, size=24, color="#433C49"),
                    ft.Row(
                        spacing=4,
                        tight=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                titulo_curto,
                                size=11,
                                color="#433C49",
                                weight=ft.FontWeight.BOLD,
                                no_wrap=True,
                            ),
                            ft.Container(
                                width=21,
                                height=21,
                                alignment=_alignment_center(),
                                border_radius=11,
                                bgcolor=COLOR_HEADER,
                                content=contador_aba,
                            ),
                        ],
                    ),
                ],
            ),
        )
        botoes_abas[fila] = botao_aba
        controles_navegacao.append(botao_aba)

    navegacao_filas = ft.Row(spacing=0, controls=controles_navegacao)
    selecionar_fila("retorno", atualizar=False)

    indicador_atualizacao = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)
    texto_atualizacao = ft.Text(
        "Carregando filas...",
        size=12,
        color=getattr(ft.Colors, "WHITE70", ft.Colors.WHITE),
    )

    def aplicar_dados(dados):
        estilos = {
            fila: (fundo, destaque)
            for fila, _, _, _, fundo, destaque in FILAS
        }
        for fila, info in dados.items():
            pendentes = info["pendentes"]
            contadores[fila][0].value = str(info["concluidos"])
            contadores[fila][1].value = str(len(pendentes))
            contadores_abas[fila].value = str(len(pendentes))
            fundo, destaque = estilos[fila]
            listas[fila].controls = [
                card_consulente(fila, item, fundo, destaque)
                for item in pendentes
            ]
            if not pendentes:
                listas[fila].controls = [
                    ft.Container(
                        padding=30,
                        alignment=_alignment_center(),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_OUTLINE,
                                    size=44,
                                    color=ft.Colors.GREEN_700,
                                ),
                                ft.Text(
                                    "Ninguém aguardando",
                                    color=COLOR_TEXT,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),
                    )
                ]
        texto_atualizacao.value = f"Atualizado às {datetime.now():%H:%M:%S}"
        state["erro_atualizacao_mostrado"] = False

    def carregar(e=None):
        if state["carregando"] or not state["ativo"]:
            return
        state["carregando"] = True
        indicador_atualizacao.visible = True
        atualizar_pagina()
        try:
            aplicar_dados(listar_painel_chamadas())
        except Exception as ex:
            aviso(f"Não foi possível carregar as filas: {ex}", False)
        finally:
            state["carregando"] = False
            indicador_atualizacao.visible = False
            atualizar_pagina()

    async def atualizacao_automatica():
        while state["ativo"] and _rota_eh_chamada(page.route):
            await asyncio.sleep(3)
            if not state["ativo"] or not _rota_eh_chamada(page.route):
                break
            if state["carregando"]:
                continue

            state["carregando"] = True
            try:
                dados = await asyncio.to_thread(listar_painel_chamadas)
                aplicar_dados(dados)
                atualizar_pagina()
            except Exception as ex:
                if not state["erro_atualizacao_mostrado"]:
                    state["erro_atualizacao_mostrado"] = True
                    aviso(f"Falha na atualização automática: {ex}", False)
            finally:
                state["carregando"] = False

    def resumo_fechamento(dados):
        return {
            fila: {
                "chamados": int(info.get("concluidos") or 0),
                "faltam": len(info.get("pendentes") or []),
            }
            for fila, info in dados.items()
        }

    def criar_pdf_fechamento(resumo):
        pasta = get_pdf_dir()
        nome = f"fechamento_gira_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        return gerar_pdf_fechamento_gira(
            pasta / nome,
            resumo,
            data_ref=date.today(),
        )

    def gerar_somente_pdf(resumo):
        fechar_dialogo()
        try:
            caminho = criar_pdf_fechamento(resumo)
            aviso(f"Fechamento salvo em: {caminho}")
        except Exception as ex:
            aviso(f"Erro ao gerar fechamento: {ex}", False)

    async def gerar_e_compartilhar(resumo):
        fechar_dialogo()
        if state.get("compartilhando"):
            return
        state["compartilhando"] = True
        indicador_atualizacao.visible = True
        atualizar_pagina()
        try:
            caminho = criar_pdf_fechamento(resumo)
            arquivo = Path(caminho)
            await compartilhamento.share_files(
                [
                    ft.ShareFile.from_bytes(
                        arquivo.read_bytes(),
                        mime_type="application/pdf",
                        name=arquivo.name,
                    )
                ],
                title="Fechamento da Gira",
                subject=f"Fechamento da gira - {date.today():%d/%m/%Y}",
                text=(
                    "Fechamento da gira da Casa da Vovó Joaquina "
                    f"- {date.today():%d/%m/%Y}"
                ),
                download_fallback_enabled=True,
                mail_to_fallback_enabled=False,
            )
            aviso(
                "PDF pronto. Escolha o WhatsApp; se o menu não abrir, use o arquivo baixado."
            )
        except Exception as ex:
            aviso(f"Erro ao compartilhar o fechamento: {ex}", False)
        finally:
            state["compartilhando"] = False
            indicador_atualizacao.visible = False
            atualizar_pagina()

    def abrir_fechamento(e=None):
        try:
            dados = listar_painel_chamadas()
            resumo = resumo_fechamento(dados)
        except Exception as ex:
            aviso(f"Erro ao calcular o fechamento: {ex}", False)
            return

        nomes = {fila: titulo for fila, titulo, *_ in FILAS}
        linhas = []
        total_chamados = 0
        total_faltam = 0
        for fila, _, _, _, fundo, destaque in FILAS:
            chamados = resumo[fila]["chamados"]
            faltam = resumo[fila]["faltam"]
            total_chamados += chamados
            total_faltam += faltam
            linhas.append(
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=fundo,
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                nomes[fila],
                                expand=True,
                                weight=ft.FontWeight.BOLD,
                                color=destaque,
                            ),
                            ft.Text(
                                f"{chamados} chamados",
                                size=12,
                                color=destaque,
                            ),
                            ft.Text(
                                f"{faltam} faltam",
                                size=12,
                                color=destaque,
                            ),
                        ]
                    ),
                )
            )

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Fechar gira"),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    tight=True,
                    spacing=8,
                    controls=[
                        ft.Text(
                            f"Total: {total_chamados} chamados e {total_faltam} aguardando.",
                            weight=ft.FontWeight.BOLD,
                        ),
                        *linhas,
                        ft.Text(
                            "Escolha o WhatsApp e os contatos. Se o navegador não abrir "
                            "o menu, o PDF será baixado automaticamente.",
                            size=11,
                            color=ft.Colors.GREY_700,
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar_dialogo),
                ft.OutlinedButton(
                    "Gerar PDF",
                    icon=ft.Icons.PICTURE_AS_PDF,
                    on_click=lambda e: gerar_somente_pdf(resumo),
                ),
                ft.ElevatedButton(
                    "Compartilhar",
                    icon=ft.Icons.SHARE,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.GREEN_700,
                        color=ft.Colors.WHITE,
                    ),
                    on_click=lambda e: page.run_task(
                        gerar_e_compartilhar, resumo
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dialogo_atual["controle"] = dialogo
        try:
            page.show_dialog(dialogo)
        except AttributeError:
            if dialogo not in page.overlay:
                page.overlay.append(dialogo)
            dialogo.open = True
            atualizar_pagina()

    cabecalho = ft.Container(
        bgcolor=COLOR_HEADER,
        padding=_padding_symmetric(horizontal=10, vertical=9),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    icon_color=ft.Colors.WHITE,
                    tooltip="Voltar ao cadastro",
                    on_click=lambda e: page.go(back_route),
                ),
                ft.Image(
                    src="Novologo.jpg",
                    width=45,
                    height=38,
                    fit=(
                        ft.ImageFit.CONTAIN
                        if hasattr(ft, "ImageFit")
                        else ft.BoxFit.CONTAIN
                    ),
                ),
                ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        ft.Text(
                            "Chamada da Gira",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        texto_atualizacao,
                    ],
                ),
                indicador_atualizacao,
                ft.TextButton(
                    "Fechar",
                    icon=ft.Icons.FLAG,
                    tooltip="Fechar gira e gerar totalizadores",
                    style=ft.ButtonStyle(color=ft.Colors.WHITE),
                    on_click=abrir_fechamento,
                ),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color=ft.Colors.WHITE,
                    tooltip="Atualizar filas",
                    on_click=carregar,
                ),
            ],
        ),
    )

    page.add(
        ft.Column(
            expand=True,
            spacing=0,
            controls=[cabecalho, navegacao_filas, conteudo_fila],
        )
    )
    carregar()
    page.run_task(atualizacao_automatica)
