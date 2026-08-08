# ui/main_view.py
import asyncio
import os
import inspect
import socket
import tempfile
import time
import threading
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

import flet as ft


def _habilitar_file_picker_bytes_compat():
    """Aceita respostas de clientes novos quando o servidor usa Flet anterior ao 0.85."""
    try:
        parametros = inspect.signature(ft.FilePickerFile).parameters
        if "bytes" in parametros:
            return

        original_init = ft.FilePickerFile.__init__

        def compatible_init(self, id, name, size, path=None, bytes=None):
            original_init(self, id=id, name=name, size=size, path=path)
            self.bytes = bytes

        ft.FilePickerFile.__init__ = compatible_init
    except Exception:
        # Não impede a inicialização da tela caso a API mude novamente.
        pass


_habilitar_file_picker_bytes_compat()


def border_all(width, color):
    side = ft.BorderSide(width=width, color=color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def margin_only(left=0, top=0, right=0, bottom=0):
    return ft.Margin(left=left, top=top, right=right, bottom=bottom)


def _caminho_local_existente(caminho: str | None) -> str | None:
    """Aceita o path do FilePicker somente quando existe neste servidor."""
    if not caminho:
        return None
    try:
        arquivo = Path(caminho)
        return str(arquivo.resolve()) if arquivo.is_absolute() and arquivo.is_file() else None
    except (OSError, ValueError):
        return None


from db.repo import (
    buscar_clientes,
    buscar_cliente_por_id,
    buscar_tratamentos_ativos,
    # retorno
    registrar_retorno,
    registrar_retorno_pref,
    remover_retorno,
    remover_retorno_pref,
    existe_retorno_hoje,
    existe_retorno_pref_hoje,
    # triagem
    existe_triagem_hoje,
    existe_triagem_pref_hoje,
    registrar_triagem,
    registrar_triagem_pref,
    remover_triagem,
    remover_triagem_pref,
    # novo consulente
    inserir_consulente,
    # listas
    listar_chamada_retorno,
    listar_chamada_retorno_pref,
    listar_chamada_triagem,
    listar_chamada_triagem_pref,
    # senha do dia
    obter_senha_hoje,
    obter_senhas_hoje,
    # --- TRATAMENTOS ---
    registrar_uso_passe,
    registrar_uso_cromo,
    registrar_uso_massagem,
    registrar_uso_cirurgia,
    registrar_uso_ponto,
    # --- AÇÕES EM LOTE (DETAILS) ---
    atualizar_preferencial_consulente,
    atualizar_status_tratamentos,
    reiniciar_tratamento,
)


from pdf.layout_a5 import gerar_pdf_plano_tratamento_a5
from ui.details import montar_detalhes_modelo
from print.win_print import abrir_pdf_windows, imprimir_pdf_windows
from core.config import get_pdf_dir
from core.fila_rules import contar_tratamentos_indicados, tipo_fila_indicada
from core.paths import resource_path, sql_upload_dir
from db.sql_loader import build_summary_text, execute_sql_file
from db.sql_exporter import generate_database_export

logo = ft.Image(
    src=("Novologo.jpg"),
    width=160,
    height=55,
    fit="contain",
)

# watcher (auto-impressão) - opcional
try:
    from print.pdf_watcher import PdfAutoPrinter, WatchConfig
except Exception:
    PdfAutoPrinter = None
    WatchConfig = None


COLOR_BG = "#C9A3C8"
COLOR_HEADER = "#b894c4"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#6B3F6B"
COLOR_AVAILABLE = "#4CAF50"  # Verde para tratamento disponível
COLOR_DEFAULT = "#E8E8E8"  # Cinza claro para esgotado ou igual


def obter_ip_local() -> str:
    """Retorna o IP local mais provável para acesso na rede."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def build_main(page: ft.Page, current_user=None):
    page.title = "Casa da Vovó Joaquina - Gira de Cura"
    # Info do servidor (IP + porta) para o operador informar aos clientes
    ip_local = obter_ip_local()
    url_servidor = f"http://{ip_local}:8550"
    url_celular = f"{url_servidor}/Celular"
    info_servidor = ft.Container(
        content=ft.Text(
            f"Servidor: {url_servidor}  |  Celular: {url_celular}",
            size=15,
            color=ft.Colors.PURPLE_900,
            weight=ft.FontWeight.BOLD,
            selectable=True,
        ),
        bgcolor=ft.Colors.PURPLE_50,
        border=border_all(1, ft.Colors.PURPLE_200),
        border_radius=8,
        padding=8,
    )

    page.bgcolor = COLOR_BG
    page.padding = 10
    page.scroll = "auto"

    # helper thread-safe
    def ui(fn):
        try:
            if hasattr(page, "call_from_thread"):
                page.call_from_thread(fn)
                return
        except Exception:
            pass
        fn()

    logo_img = ft.Image(src="Novologo.jpg", width=145, height=50, fit="contain")

    txt_busca = ft.TextField(
        label="Buscar consulente",
        hint_text="Digite o nome (ex.: MARIA)",
        autofocus=True,
        bgcolor="#FFFFFF",
        suffix=ft.IconButton(
            icon=ft.Icons.CANCEL,
            icon_color=ft.Colors.RED_600,
            icon_size=16,
            tooltip="Limpar busca",
            width=28,
            height=28,
            padding=0,
            on_click=lambda e: limpar_busca(),
        ),
    )

    status = ft.Text(
        "Pronto.",
        color=COLOR_TEXT,
        weight="bold",
        size=12,
        expand=True,
    )
    status_busca = ft.Text("", color=COLOR_TEXT, weight="bold", size=12)
    status_box = ft.Container(
        expand=True,
        bgcolor=ft.Colors.PURPLE_50,
        border=border_all(1, "#D2B8D8"),
        border_radius=8,
        padding=8,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=COLOR_TEXT),
                status,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    lista = ft.ListView(expand=True, spacing=2, padding=10)
    resultados_busca_box = ft.Container(
        visible=False,
        height=220,
        bgcolor=ft.Colors.WHITE,
        border=border_all(1, "#C8A9CF"),
        border_radius=8,
        padding=6,
        content=ft.Column(
            [
                status_busca,
                ft.Divider(height=1),
                lista,
            ],
            spacing=3,
            expand=True,
        ),
    )

    acoes_col = ft.Column(
        [
            ft.Text(
                "Selecione um consulente para exibir as indicações e filas.",
                size=13,
                color=ft.Colors.GREY_600,
            )
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
    detalhes_col = ft.Column([], expand=True, scroll=ft.ScrollMode.AUTO)
    detalhes_card = ft.Container(
        bgcolor=COLOR_CARD,
        border_radius=12,
        padding=12,
        content=ft.Column(
            [
                ft.Text("Detalhes", size=18, weight="bold", color=COLOR_TEXT),
                ft.Divider(),
                detalhes_col,
            ],
            expand=True,
        ),
        expand=True,
    )

    selecionado = {
        "dados": None,
        "tratamentos": [],
        "cid": None,
        "mostrar_todas_filas": False,
    }

    # ==========================================================
    # POPUP "TRATAMENTO TERMINADO"
    # ==========================================================
    dlg_trat_terminado = ft.AlertDialog(
        modal=True,
        bgcolor=ft.Colors.WHITE,
        title=ft.Text(
            "Aviso", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK
        ),
        content=ft.Container(
            width=460,
            padding=18,
            bgcolor=ft.Colors.WHITE,
            border_radius=12,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE,
                                size=32,
                                color=ft.Colors.GREEN_700,
                            ),
                            ft.Text(
                                "Tratamento Terminado",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.BLACK,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        "Todos os tratamentos disponíveis já foram executados para este consulente.",
                        size=16,
                        color=ft.Colors.BLACK,
                    ),
                ],
                tight=True,
                spacing=6,
            ),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _fechar_popup(ev=None):
        dlg_trat_terminado.open = False
        page.update()

    dlg_trat_terminado.actions = [
        ft.ElevatedButton(
            "OK",
            on_click=_fechar_popup,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PURPLE_600,
                color=ft.Colors.WHITE,
            ),
        )
    ]

    if dlg_trat_terminado not in page.overlay:
        page.overlay.append(dlg_trat_terminado)

    def _mostrar_popup_tratamento_terminado():
        dlg_trat_terminado.open = True
        page.update()

    def pasta_pdf():
        p = str(get_pdf_dir())
        os.makedirs(p, exist_ok=True)
        return p

    # ==========================================================
    # DEFINIÇÕES DO HEADER (Botões e Switches)
    # ==========================================================

    # --- NOVO CONSULENTE ---
    nome_tf = ft.TextField(label="Nome", autofocus=True)
    sexo_dd = ft.Dropdown(
        label="Sexo",
        options=[
            ft.dropdown.Option("M"),
            ft.dropdown.Option("F"),
        ],
        value="M",
        width=160,
    )

    def mascara_data(e):
        valor = "".join(filter(str.isdigit, e.control.value))
        if len(valor) > 8:
            valor = valor[:8]
        novo_texto = ""
        for i, char in enumerate(valor):
            if i == 2 or i == 4:
                novo_texto += "/"
            novo_texto += char
        e.control.value = novo_texto
        e.control.update()

    nasc_tf = ft.TextField(
        label="Nascimento",
        hint_text="Ex.: 31/12/1990",
        width=200,
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=mascara_data,
        input_filter=ft.InputFilter(
            allow=True, regex_string=r"[0-9/]", replacement_string=""
        ),
    )

    pref_sw = ft.Switch(label="Preferencial", value=False)

    def normalizar_nome_consulente(valor: str) -> str:
        valor = " ".join((valor or "").strip().split())
        valor = unicodedata.normalize("NFD", valor)
        valor = "".join(ch for ch in valor if unicodedata.category(ch) != "Mn")
        return valor.upper()

    def normalizar_nome_digitando(valor: str) -> str:
        valor = unicodedata.normalize("NFD", valor or "")
        valor = "".join(ch for ch in valor if unicodedata.category(ch) != "Mn")
        return valor.upper()

    def caps(ev):
        v = ev.control.value or ""
        up = normalizar_nome_digitando(v)
        if up != v:
            cursor_pos = len(up)
            ev.control.value = up
            try:
                ev.control.selection = ft.TextSelection(cursor_pos, cursor_pos)
            except Exception:
                pass
            ev.control.update()

    nome_tf.on_change = caps

    dlg_novo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Novo Consulente"),
        content=ft.Container(
            padding=10,
            content=ft.Column(
                [nome_tf, sexo_dd, nasc_tf, pref_sw], tight=True, spacing=10
            ),
        ),
        actions_alignment="end",
    )
    page.overlay.append(dlg_novo)

    dlg_aviso_cadastro = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.ORANGE_700),
                ft.Text("Consulente já cadastrado"),
            ],
            spacing=8,
        ),
        content=ft.Text("Já existe um consulente cadastrado com este nome."),
    )

    def fechar_aviso_cadastro(ev=None):
        dlg_aviso_cadastro.open = False
        page.update()

    dlg_aviso_cadastro.actions = [
        ft.ElevatedButton("Entendi", on_click=fechar_aviso_cadastro)
    ]
    page.overlay.append(dlg_aviso_cadastro)

    def fechar_novo(ev=None):
        dlg_novo.open = False
        page.update()

    def salvar_novo(ev=None):
        try:
            nm = normalizar_nome_consulente(nome_tf.value or "")
            if not nm:
                raise ValueError("Informe o nome.")

            sx = (sexo_dd.value or "M").strip().upper()

            nasc_txt = (nasc_tf.value or "").strip()
            if not nasc_txt:
                raise ValueError("Informe o nascimento (DD/MM/AAAA).")

            try:
                nasc_dt = datetime.strptime(nasc_txt, "%d/%m/%Y").date()
            except Exception:
                raise ValueError(
                    "Nascimento inválido. Use DD/MM/AAAA (ex.: 31/12/1990)."
                )

            pr = "X" if bool(pref_sw.value) else ""

            novo_id = inserir_consulente(
                nome=nm, sexo=sx, nascimento=nasc_dt, preferencial=pr
            )

            dlg_novo.open = False
            search_token["v"] += 1
            txt_busca.value = nm
            lista.controls.clear()

            status.value = f"Consulente criado: {nm}"
            page.update()

            render_detalhes(novo_id)

        except Exception as ex:
            status.value = f"Erro ao salvar: {ex}"
            erro_normalizado = normalizar_nome_consulente(str(ex))
            if "JA EXISTE UM CONSULENTE" in erro_normalizado:
                dlg_novo.open = False
                dlg_aviso_cadastro.content = ft.Text(
                    f"O consulente “{normalizar_nome_consulente(nome_tf.value or '')}” "
                    "já está cadastrado. Pesquise o nome existente antes de criar "
                    "um novo registro."
                )
                dlg_aviso_cadastro.open = True
            page.update()

    dlg_novo.actions = [
        ft.TextButton("Cancelar", on_click=fechar_novo),
        ft.ElevatedButton("Salvar", on_click=salvar_novo),
    ]

    def abrir_novo_consulente(e=None):
        nome_tf.value = ""
        sexo_dd.value = "M"
        nasc_tf.value = ""
        pref_sw.value = False
        dlg_novo.open = True
        page.update()

    btn_novo = ft.ElevatedButton(
        "Novo",
        ft.Icons.ADD,
        tooltip="Incluir Novo Consulente",
        on_click=abrir_novo_consulente,
    )

    # --- BOTÃO EDITAR ---
    def abrir_editor(e):
        print("DEBUG: Botão Editar clicado!")

        if not selecionado["dados"]:
            status.value = "Selecione um consulente primeiro"
            page.update()
            return

        try:
            from ui.edit_consulente import EditorConsulente
            from db.repo import atualizar_consulente

            def salvar_edicao(dados_atualizados):
                print(f"DEBUG: Salvando dados: {dados_atualizados}")

                cid = (
                    selecionado["dados"][0]
                    if isinstance(selecionado["dados"], (list, tuple))
                    else selecionado["dados"].get("con_codigo")
                )

                sucesso = atualizar_consulente(cid, dados_atualizados)

                if sucesso:
                    status.value = f"Dados atualizados para ID {cid}"
                    render_detalhes(cid)
                    page.snack_bar = ft.SnackBar(
                        ft.Text("Dados salvos no banco com sucesso!")
                    )
                else:
                    status.value = f"Erro ao salvar dados para ID {cid}"
                    page.snack_bar = ft.SnackBar(ft.Text("Erro ao salvar no banco!"))

                page.snack_bar.open = True
                page.update()

            def fechar_editor():
                status.value = "Editor fechado"
                page.update()

            editor = EditorConsulente(
                page=page,
                dados_atuais=selecionado["dados"],
                on_save_callback=salvar_edicao,
                on_cancel_callback=fechar_editor,
            )

            editor.abrir()

        except Exception as ex:
            status.value = f"Erro: {ex}"
            page.update()

    btn_editar = ft.ElevatedButton(
        "Editar",
        ft.Icons.EDIT,
        tooltip="Editar dados do consulente",
        on_click=abrir_editor,
        disabled=True,
    )

    # --- PREVIEW / IMPRIMIR (PDF) ---
    modo_preview = {"value": True}

    def gerar_pdf_selecionado():
        """Gera PDF e retorna o caminho se sucesso, ou None se falhar"""
        if not selecionado["dados"]:
            status.value = "Selecione um consulente."
            page.update()
            return None

        try:
            dados_row = selecionado["dados"]
            cid = (
                dados_row[0]
                if isinstance(dados_row, (list, tuple))
                else dados_row.get("con_codigo")
            )

            if not cid:
                status.value = "Erro: ID do consulente não encontrado"
                page.update()
                return None

            # Garante que a pasta existe
            pdf_dir = pasta_pdf()

            senha_tipo, senha_numero = obter_senha_hoje(cid)
            nome_arquivo = f"plano_trat_{cid}_{datetime.now():%Y%m%d_%H%M%S}.pdf"
            caminho = os.path.join(pdf_dir, nome_arquivo)

            print(f"DEBUG: Gerando PDF em: {caminho}")
            print(
                f"DEBUG: Dados: {type(selecionado['dados'])}, Tratamentos: {len(selecionado['tratamentos'])}"
            )

            # Gera o PDF
            gerar_pdf_plano_tratamento_a5(
                caminho,
                selecionado["dados"],
                selecionado["tratamentos"],
                logo_path=None,
                senha_tipo=senha_tipo,
                senha_numero=senha_numero,
            )

            # Verifica se o arquivo foi realmente criado
            if os.path.exists(caminho):
                print(f"DEBUG: PDF criado com sucesso: {caminho}")
                return caminho
            else:
                status.value = "Erro: Arquivo PDF não foi criado"
                page.update()
                return None

        except Exception as ex:
            print(f"DEBUG: Erro ao gerar PDF: {ex}")
            import traceback

            traceback.print_exc()
            status.value = f"Erro ao gerar PDF: {str(ex)}"
            page.update()
            return None

    def acao_pdf_preview(e):
        caminho = gerar_pdf_selecionado()
        if not caminho:
            return
        try:
            abrir_pdf_windows(caminho)
            status.value = f"PDF aberto: {os.path.basename(caminho)}"
        except Exception as ex:
            status.value = f"Erro ao abrir PDF: {ex}"
        page.update()

    def acao_pdf_imprimir(e):
        caminho = gerar_pdf_selecionado()
        if not caminho:
            return
        try:
            imprimir_pdf_windows(caminho)
            status.value = "Enviado para impressão."
        except Exception as ex:
            status.value = f"Erro ao imprimir: {ex}"
        page.update()

    btn_pdf = ft.ElevatedButton(
        "Baixar PDF",
        ft.Icons.FILE_DOWNLOAD,
        tooltip="Abrir o Arquivo",
        on_click=acao_pdf_preview,
    )
    btn_imprimir = ft.ElevatedButton(
        "Imprime", ft.Icons.PRINT, tooltip="Imprimir", on_click=acao_pdf_imprimir
    )

    # --- FORMULÁRIO VAZIO A5 ---
    def imprimir_formulario_vazio(e):
        """Gera formulário A5 em branco para preenchimento manual"""
        try:
            pdf_dir = pasta_pdf()
            nome_arquivo = f"formulario_vazio_{datetime.now():%Y%m%d_%H%M%S}.pdf"
            caminho = os.path.join(pdf_dir, nome_arquivo)

            # Dados vazios/minimais para o formulário
            dados_vazios = {
                "con_nome": "",
                "con_nascim": None,
                "con_datainicial": datetime.now().strftime("%Y-%m-%d"),
                "con_endereco": "",
                "con_bairro": "",
                "con_cidade": "",
                "con_estado": "",
                "con_cep": "",
                "con_fonecel": "",
                "con_celular2": "",
                "con_email": "",
                "con_diagnostico": "",
                "con_diagnant": "",
                "con_passe": 0,
                "con_cromoterapia": 0,
                "con_massagem": 0,
                "con_cirurgia": 0,
                "con_pontos": 0,
                "con_npasse": 0,
                "con_ncromo": 0,
                "con_nmass": 0,
                "con_ncirur": 0,
                "con_nponto": 0,
            }

            gerar_pdf_plano_tratamento_a5(
                caminho,
                dados_vazios,
                [],  # sem tratamentos
                logo_path=None,
                senha_tipo=None,
                senha_numero=None,
            )

            if os.path.exists(caminho):
                abrir_pdf_windows(caminho)
                status.value = f"Formulário vazio gerado: {nome_arquivo}"
            else:
                status.value = "Erro: Formulário não foi criado"
            page.update()

        except Exception as ex:
            print(f"DEBUG: Erro ao gerar formulário vazio: {ex}")
            import traceback

            traceback.print_exc()
            status.value = f"Erro ao gerar formulário: {ex}"
            page.update()

    btn_form_vazio = ft.ElevatedButton(
        "Branco",
        ft.Icons.DESCRIPTION,
        tooltip="Imprimir formulário A5 em branco",
        on_click=imprimir_formulario_vazio,
    )

    # --- LISTAS ---
    def gerar_listas_hoje():
        try:
            rows_normal = listar_chamada_retorno()
            rows_pref = listar_chamada_retorno_pref()
            rows_tri = listar_chamada_triagem()
            rows_tri_pref = listar_chamada_triagem_pref()

            nome = f"listas_{datetime.now():%Y%m%d_%H%M%S}.pdf"
            caminho = os.path.join(pasta_pdf(), nome)

            from pdf import chamada_a4 as ch

            if not hasattr(ch, "gerar_pdf_chamada_4paginas"):
                ui(
                    lambda: (
                        setattr(status, "value", "Função chamada_a4 não encontrada"),
                        page.update(),
                    )
                )
                return

            ch.gerar_pdf_chamada_4paginas(
                caminho,
                rows_normal=rows_normal,
                rows_pref=rows_pref,
                rows_triagem=rows_tri,
                rows_triagem_pref=rows_tri_pref,
                data_ref=datetime.now().strftime("%d/%m/%Y"),
                logo_path=resource_path("assets/logopb.jpg"),
            )
            status_text = f"Lista A4 gerada: {caminho}"

            # ---------- ABRIR OU IMPRIMIR ----------
            if modo_preview["value"]:
                try:
                    abrir_pdf_windows(caminho)
                    ui(
                        lambda: (
                            setattr(status, "value", "Lista A4 aberta"),
                            page.update(),
                        )
                    )
                except Exception:
                    ui(lambda: (setattr(status, "value", status_text), page.update()))
            else:
                imprimir_pdf_windows(caminho)
                ui(
                    lambda: (
                        setattr(status, "value", "Lista A4 impressa"),
                        page.update(),
                    )
                )

        except Exception as ex:
            ui(
                lambda: (
                    setattr(status, "value", f"Erro ao gerar lista: {ex}"),
                    page.update(),
                )
            )

    btn_listas = ft.ElevatedButton(
        "Gera lista",
        icon=ft.Icons.LINE_STYLE,
        tooltip="Gerar listas de presença em A4",
        on_click=lambda e: threading.Thread(target=gerar_listas_hoje, daemon=True).start(),
    )

    btn_chamada = ft.ElevatedButton(
        "Iniciar gira",
        icon=ft.Icons.PLAY_CIRCLE,
        tooltip="Abrir o módulo de chamada",
        on_click=lambda e: page.go("/chamada"),
    )

    # --- ATUALIZAR BASE POR TXT/SQL ---
    sql_file_tf = ft.TextField(
        label="Arquivo TXT/SQL",
        hint_text="Selecione um arquivo ou informe um caminho do servidor",
        width=520,
    )
    sql_dir_tf = ft.TextField(
        label="Pasta do relatório",
        value=pasta_pdf(),
        hint_text=r"Ex.: C:\pasta\relatorios",
        width=520,
    )
    sql_status = ft.Text("Selecione o arquivo e execute a carga.", size=12)
    sql_result = ft.TextField(
        multiline=True,
        read_only=True,
        min_lines=9,
        max_lines=12,
        width=680,
        text_style=ft.TextStyle(font_family="Consolas", size=11),
    )
    sql_progress = ft.ProgressBar(visible=False, value=None, width=680)

    selected_sql = {
        "name": "",
        "bytes": None,
        "path": None,
        "temporary": False,
        "uploading": False,
        "upload_name": "",
    }

    def reset_selected_sql(remove_temporary=False):
        temporary_path = selected_sql["path"] if selected_sql["temporary"] else None
        selected_sql.update(
            name="",
            bytes=None,
            path=None,
            temporary=False,
            uploading=False,
            upload_name="",
        )
        if remove_temporary and temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass

    def sql_upload_progress(e):
        if e.error:
            reset_selected_sql(remove_temporary=True)
            sql_status.value = f"Erro ao enviar arquivo: {e.error}"
            btn_sql_run.disabled = True
        elif e.progress is not None and e.progress >= 1:
            uploaded_path = sql_upload_dir() / selected_sql["upload_name"]
            if uploaded_path.is_file():
                selected_sql["path"] = str(uploaded_path.resolve())
                selected_sql["temporary"] = True
                selected_sql["uploading"] = False
                sql_file_tf.value = selected_sql["path"]
                btn_sql_run.disabled = False
                sql_status.value = f"Arquivo pronto: {selected_sql['name']}."
            else:
                reset_selected_sql(remove_temporary=True)
                btn_sql_run.disabled = True
                sql_status.value = "O upload terminou, mas o arquivo não foi encontrado."
        elif e.progress is not None:
            sql_status.value = f"Enviando arquivo: {e.progress * 100:.0f}%"
        page.update()

    sql_file_picker = ft.FilePicker(on_upload=sql_upload_progress)

    def sql_file_changed(e=None):
        informado = (sql_file_tf.value or "").strip()
        arquivo_selecionado = {
            selected_sql["name"],
            selected_sql["path"],
        }
        if informado in arquivo_selecionado and informado:
            return
        # Mantem o suporte ao caminho completo informado manualmente, mas
        # nunca tenta executar um nome relativo que veio do navegador.
        btn_sql_run.disabled = _caminho_local_existente(informado) is None

    sql_file_tf.on_change = sql_file_changed

    async def escolher_sql_file(e=None):
        try:
            reset_selected_sql(remove_temporary=True)
            sql_file_tf.value = ""
            btn_sql_run.disabled = True
            picker_args = dict(
                dialog_title="Selecione o arquivo TXT/SQL",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["sql", "txt"],
                allow_multiple=False,
            )
            # No desktop o seletor pode retornar um caminho local real. No
            # navegador o caminho pode ser apenas o nome (ou um fake path),
            # caso em que o fluxo abaixo envia o arquivo por upload.
            files = await sql_file_picker.pick_files(**picker_args)
            if not files:
                sql_status.value = "Seleção de arquivo cancelada."
            else:
                picked = files[0]
                suffix = Path(picked.name).suffix.lower()
                if suffix not in {".sql", ".txt"}:
                    raise ValueError("Selecione um arquivo com extensão .sql ou .txt.")
                selected_sql["name"] = picked.name
                sql_file_tf.value = picked.name
                picked_bytes = getattr(picked, "bytes", None)
                caminho_local = _caminho_local_existente(picked.path)
                if picked_bytes is not None:
                    selected_sql["bytes"] = picked_bytes
                    btn_sql_run.disabled = False
                    sql_status.value = (
                        f"Arquivo selecionado: {picked.name} "
                        f"({picked.size / 1024:.1f} KB)."
                    )
                elif caminho_local:
                    selected_sql["path"] = caminho_local
                    sql_file_tf.value = caminho_local
                    btn_sql_run.disabled = False
                    sql_status.value = f"Arquivo selecionado: {picked.name}."
                else:
                    upload_name = f"{uuid.uuid4().hex}{suffix}"
                    selected_sql["upload_name"] = upload_name
                    selected_sql["uploading"] = True
                    sql_status.value = "Enviando arquivo ao servidor..."
                    page.update()
                    await sql_file_picker.upload(
                        [
                            ft.FilePickerUploadFile(
                                upload_url=page.get_upload_url(upload_name, 600),
                                id=picked.id,
                                name=picked.name,
                            )
                        ]
                    )
        except Exception as ex:
            reset_selected_sql(remove_temporary=True)
            btn_sql_run.disabled = True
            sql_status.value = f"Erro ao selecionar arquivo: {ex}"
        page.update()

    btn_sql_file = ft.ElevatedButton(
        "Arquivo...",
        icon=ft.Icons.DESCRIPTION,
        on_click=escolher_sql_file,
    )
    btn_sql_run = ft.ElevatedButton(
        "Executar", icon=ft.Icons.PLAY_ARROW, disabled=True
    )

    dlg_sql_loader = ft.AlertDialog(
        modal=True,
        title=ft.Text("Atualizar Base"),
        content=ft.Container(
            width=720,
            content=ft.Column(
                [
                    ft.Row([sql_file_tf, btn_sql_file], wrap=True),
                    sql_dir_tf,
                    sql_progress,
                    sql_status,
                    sql_result,
                ],
                tight=True,
                spacing=10,
            ),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def fechar_sql_loader(e=None):
        dlg_sql_loader.open = False
        page.update()

    def executar_sql_loader(e=None):
        sql_file = (sql_file_tf.value or "").strip()
        sql_dir = (sql_dir_tf.value or "").strip()
        picked_name = selected_sql["name"]
        picked_bytes = selected_sql["bytes"]
        picked_path = selected_sql["path"]
        picked_temporary = selected_sql["temporary"]
        uses_selected_file = bool(picked_name) and sql_file in {
            picked_name,
            picked_path,
        }

        if not sql_file:
            sql_status.value = "Informe ou selecione o arquivo TXT/SQL."
            page.update()
            return
        if not sql_dir:
            sql_status.value = "Informe ou selecione a pasta do relatório."
            page.update()
            return
        if selected_sql["uploading"]:
            sql_status.value = "Aguarde o envio do arquivo terminar."
            page.update()
            return
        if uses_selected_file and picked_bytes is None and not picked_path:
            sql_status.value = "O arquivo selecionado ainda não está disponível no servidor."
            btn_sql_run.disabled = True
            page.update()
            return
        if not uses_selected_file and _caminho_local_existente(sql_file) is None:
            sql_status.value = (
                "Arquivo não encontrado. Selecione novamente e aguarde "
                "a mensagem 'Arquivo pronto'."
            )
            btn_sql_run.disabled = True
            page.update()
            return

        btn_sql_run.disabled = True
        btn_sql_file.disabled = True
        sql_file_tf.disabled = True
        sql_dir_tf.disabled = True
        sql_progress.visible = True
        sql_result.value = ""
        sql_status.value = "Executando carga SQL..."
        page.update()

        def _run():
            temporary_path = None
            report = None
            unexpected_error = None
            try:
                source_path = sql_file
                source_name = None
                if picked_bytes is not None and uses_selected_file:
                    suffix = Path(picked_name).suffix.lower()
                    with tempfile.NamedTemporaryFile(
                        mode="wb", suffix=suffix, prefix="cvjapp_sql_", delete=False
                    ) as temporary:
                        temporary.write(picked_bytes)
                        temporary_path = temporary.name
                    source_path = temporary_path
                    source_name = picked_name
                elif picked_path and uses_selected_file:
                    source_path = picked_path
                    source_name = picked_name
                    if picked_temporary:
                        temporary_path = picked_path

                if current_user is None:
                    raise PermissionError("Entre novamente para executar a carga.")
                report = execute_sql_file(
                    source_path,
                    sql_dir,
                    actor_id=current_user.id,
                    source_name=source_name,
                )
            except Exception as ex:
                unexpected_error = f"{type(ex).__name__}: {ex}"
            finally:
                if temporary_path:
                    try:
                        os.unlink(temporary_path)
                    except OSError:
                        pass

            def _done():
                btn_sql_run.disabled = False
                btn_sql_file.disabled = False
                sql_file_tf.disabled = False
                sql_dir_tf.disabled = False
                sql_progress.visible = False
                if report is None:
                    sql_result.value = unexpected_error or "Falha inesperada na carga."
                    sql_status.value = "Não foi possível executar a carga."
                else:
                    sql_result.value = build_summary_text(report)
                    sql_status.value = (
                        "Carga concluída com sucesso."
                        if report.ok
                        else "Carga concluída com erro."
                    )
                if picked_bytes is not None or picked_temporary:
                    reset_selected_sql()
                    sql_file_tf.value = ""
                status.value = sql_status.value
                page.update()

            ui(_done)

        threading.Thread(target=_run, daemon=True).start()

    btn_sql_run.on_click = executar_sql_loader
    dlg_sql_loader.actions = [
        ft.TextButton("Fechar", on_click=fechar_sql_loader),
        btn_sql_run,
    ]
    page.overlay.append(dlg_sql_loader)

    def abrir_sql_loader(e=None):
        sql_result.value = ""
        sql_status.value = "Selecione o arquivo e execute a carga."
        dlg_sql_loader.open = True
        page.update()

    btn_sql_loader = ft.ElevatedButton(
        "Atualiza base",
        icon=ft.Icons.STORAGE,
        tooltip="Executar arquivo TXT/SQL de atualização da base",
        on_click=abrir_sql_loader,
    )

    # --- EXPORTAR BASE PARA TXT/SQL ---
    compartilhamento_base = ft.Share()

    async def compartilhar_arquivo_base(arquivo: Path, dialogo):
        dialogo.open = False
        status.value = "Preparando compartilhamento da base..."
        page.update()
        try:
            conteudo = await asyncio.to_thread(arquivo.read_bytes)
            await compartilhamento_base.share_files(
                [
                    ft.ShareFile.from_bytes(
                        conteudo,
                        mime_type="text/plain",
                        name=arquivo.name,
                    )
                ],
                title="Base de dados CVJAPP",
                subject=f"Base de dados CVJAPP - {datetime.now():%d/%m/%Y}",
                text=f"Arquivo de atualização da base CVJAPP: {arquivo.name}",
                download_fallback_enabled=True,
                mail_to_fallback_enabled=False,
            )
            mensagem = (
                "Arquivo pronto. Escolha o WhatsApp; se o menu não abrir, "
                "use o arquivo baixado."
            )
            sucesso = True
        except Exception as ex:
            mensagem = f"Erro ao compartilhar a base: {ex}"
            sucesso = False

        status.value = mensagem
        page.snack_bar = ft.SnackBar(
            ft.Text(mensagem),
            bgcolor=ft.Colors.GREEN_700 if sucesso else ft.Colors.RED_700,
        )
        page.snack_bar.open = True
        page.update()

    def mostrar_exportacao_concluida(arquivo: Path):
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Base exportada com sucesso"),
            content=ft.Column(
                [
                    ft.Text("O arquivo foi salvo em:"),
                    ft.Text(str(arquivo), selectable=True, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Para enviar, toque em Compartilhar e escolha o WhatsApp.",
                        size=12,
                        color=ft.Colors.GREY_700,
                    ),
                ],
                tight=True,
                spacing=8,
            ),
            actions=[
                ft.TextButton(
                    "Fechar",
                    on_click=lambda e: (
                        setattr(dialogo, "open", False),
                        page.update(),
                    ),
                ),
                ft.ElevatedButton(
                    "Compartilhar",
                    icon=ft.Icons.SHARE,
                    on_click=lambda e: page.run_task(
                        compartilhar_arquivo_base, arquivo, dialogo
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialogo)
        dialogo.open = True

    def exportar_base(e=None):
        btn_exportar_base.disabled = True
        status.value = "Gerando arquivo da base..."
        page.update()

        def _run():
            arquivo = None
            try:
                if current_user is None:
                    raise PermissionError("Entre novamente para exportar a base.")
                arquivo = generate_database_export(current_user.id)
                mensagem = f"Base exportada com sucesso: {arquivo}"
                cor = ft.Colors.GREEN_700
            except Exception as ex:
                mensagem = f"Erro ao exportar a base: {ex}"
                cor = ft.Colors.RED_700

            def _done():
                btn_exportar_base.disabled = False
                status.value = mensagem
                page.snack_bar = ft.SnackBar(ft.Text(mensagem), bgcolor=cor)
                page.snack_bar.open = True
                if arquivo is not None:
                    mostrar_exportacao_concluida(Path(arquivo))
                page.update()

            ui(_done)

        threading.Thread(target=_run, daemon=True).start()

    btn_exportar_base = ft.ElevatedButton(
        "Exporta base",
        icon=ft.Icons.DOWNLOAD,
        tooltip="Gerar arquivo TXT/SQL da base atual na pasta outputs",
        on_click=exportar_base,
    )

    # --- AUTO IMPRESSÃO ---
    IS_SERVER = os.getenv("CVJ_SERVER", "0") == "1"
    auto_state = {"running": False, "watcher": None, "thread": None}

    def on_auto_switch(e):
        if not IS_SERVER:
            e.control.value = False
            status.value = "Auto-impressão só no servidor."
            page.update()
            return
        status.value = "Auto-impressão alterada."
        page.update()

    sw_auto = ft.Switch(
        label="Auto",
        tooltip="Impressão Automática",
        value=False,
        on_change=on_auto_switch,
        disabled=(not IS_SERVER),
    )

    # ==========================================================
    # DETALHES / AÇÕES DO CONSULENTE
    # ==========================================================

    def render_detalhes(cid: int):
        if selecionado.get("cid") != cid:
            selecionado["cid"] = cid
            selecionado["mostrar_todas_filas"] = False

        dados = buscar_cliente_por_id(cid)
        if not dados:
            acoes_col.controls = [
                ft.Text("Registro não encontrado.", color=COLOR_TEXT)
            ]
            detalhes_col.controls = [
                ft.Text("Registro não encontrado.", color=COLOR_TEXT)
            ]
            page.update()
            return

        tratamentos = buscar_tratamentos_ativos(cid)
        senhas_fila = obter_senhas_hoje(cid)
        selecionado["dados"] = dados
        selecionado["tratamentos"] = tratamentos

        btn_editar.disabled = False
        btn_editar.update()

        ja_normal = bool(existe_retorno_hoje(cid))
        ja_pref = bool(existe_retorno_pref_hoje(cid))
        ja_tri = bool(existe_triagem_hoje(cid))
        ja_tri_pref = bool(existe_triagem_pref_hoje(cid))

        pref_raw = (
            str(
                dados[4]
                if isinstance(dados, (list, tuple))
                else dados.get("con_preferencial", "")
            )
            .strip()
            .upper()
        )
        is_pref_cadastro = pref_raw in ("X", "P", "S", "1", "SIM", "TRUE")

        borda_fila_normal = ft.BorderSide(width=4, color="#173A63")
        style_remove = ft.ButtonStyle(
            bgcolor="#009440",
            color="#000000",
            side=borda_fila_normal,
        )
        style_ok = ft.ButtonStyle(
            bgcolor="#FFFFFF",
            color="#000000",
            side=borda_fila_normal,
        )
        style_pref_hi = ft.ButtonStyle(
            bgcolor="#F6D36B",
            color="#000000",
            side=ft.BorderSide(width=4, color="#006B2E"),
        )
        style_pref_remove = ft.ButtonStyle(
            bgcolor="#009440",
            color="#000000",
            side=ft.BorderSide(width=4, color="#F6D36B"),
        )

        style_available = ft.ButtonStyle(
            bgcolor=COLOR_AVAILABLE,
            color="#FFFFFF",
            text_style=ft.TextStyle(size=12),
        )
        style_default = ft.ButtonStyle(
            bgcolor=COLOR_DEFAULT,
            color="#000000",
            text_style=ft.TextStyle(size=12),
        )

        def registrar_uso_e_atualizar(func_repo, label):
            try:
                resultado = func_repo(cid)
                if resultado:
                    ui(
                        lambda: (
                            render_detalhes(cid),
                            setattr(status, "value", f"Sucesso: {label} lançado!"),
                            page.update(),
                        )
                    )
                else:
                    ui(
                        lambda: (
                            setattr(status, "value", f"Erro: Sem saldo de {label}!"),
                            page.update(),
                        )
                    )
            except Exception as ex:
                ui(lambda: (setattr(status, "value", f"Erro: {ex}"), page.update()))

        def executar_acao_presenca(tipo: str):
            try:
                if tipo == "normal":
                    if existe_retorno_hoje(cid):
                        remover_retorno(cid)
                        mensagem = "Consulente removido da fila Retorno."
                    else:
                        numero = registrar_retorno(cid)
                        mensagem = (
                            f"Consulente associado à fila Retorno. Senha: RT-{numero:03d}."
                        )
                elif tipo == "pref":
                    if existe_retorno_pref_hoje(cid):
                        remover_retorno_pref(cid)
                        mensagem = "Consulente removido da fila Retorno Preferencial."
                    else:
                        numero = registrar_retorno_pref(cid)
                        mensagem = (
                            "Consulente associado à fila Retorno Preferencial. "
                            f"Senha: RTP-{numero:03d}."
                        )
                elif tipo == "tri":
                    if existe_triagem_hoje(cid):
                        remover_triagem(cid)
                        mensagem = "Consulente removido da fila Triagem."
                    else:
                        numero = registrar_triagem(cid)
                        mensagem = (
                            f"Consulente associado à fila Triagem. Senha: T-{numero:03d}."
                        )
                elif tipo == "tri_pref":
                    if existe_triagem_pref_hoje(cid):
                        remover_triagem_pref(cid)
                        mensagem = "Consulente removido da fila Triagem Preferencial."
                    else:
                        numero = registrar_triagem_pref(cid)
                        mensagem = (
                            "Consulente associado à fila Triagem Preferencial. "
                            f"Senha: TP-{numero:03d}."
                        )
                ui(
                    lambda: (
                        setattr(status, "value", mensagem),
                        render_detalhes(cid),
                    )
                )
            except Exception as ex:
                ui(lambda: (setattr(status, "value", f"Erro: {ex}"), page.update()))

        def alternar_preferencial(e):
            novo_valor = bool(e.control.value)

            def _run():
                try:
                    ok = atualizar_preferencial_consulente(cid, novo_valor)
                    if not ok:
                        ui(
                            lambda: (
                                setattr(status, "value", "Erro: preferencial não atualizado."),
                                render_detalhes(cid),
                            )
                        )
                        return
                    msg = (
                        "Consulente marcado como preferencial."
                        if novo_valor
                        else "Consulente marcado como normal."
                    )
                    ui(lambda: (setattr(status, "value", msg), render_detalhes(cid)))
                except Exception as ex:
                    ui(
                        lambda: (
                            setattr(status, "value", f"Erro: {ex}"),
                            render_detalhes(cid),
                        )
                    )

            e.control.disabled = True
            e.control.update()
            threading.Thread(target=_run, daemon=True).start()

        pref_toggle = ft.Switch(
            label=ft.Text("Preferencial", size=11),
            value=is_pref_cadastro,
            on_change=alternar_preferencial,
            active_color="#006B2E",
            active_track_color="#BFE8CC",
            inactive_thumb_color="#777777",
            inactive_track_color="#DADADA",
            tooltip="Marcar ou desmarcar preferencial no cadastro",
            scale=0.78,
        )

        # Botões de presença
        btn_normal = ft.ElevatedButton(
            "-Retorno" if ja_normal else "Retorno",
            on_click=lambda _: threading.Thread(
                target=executar_acao_presenca, args=("normal",), daemon=True
            ).start(),
            style=style_remove if ja_normal else style_ok,
        )
        btn_pref = ft.ElevatedButton(
            "-Retorno Pref" if ja_pref else "Retorno Pref",
            on_click=lambda _: threading.Thread(
                target=executar_acao_presenca, args=("pref",), daemon=True
            ).start(),
            style=(
                style_pref_remove
                if ja_pref
                else style_pref_hi
            ),
        )
        btn_tri = ft.ElevatedButton(
            "-Triagem" if ja_tri else "Triagem",
            on_click=lambda _: threading.Thread(
                target=executar_acao_presenca, args=("tri",), daemon=True
            ).start(),
            style=style_remove if ja_tri else style_ok,
        )
        btn_tri_pref = ft.ElevatedButton(
            "-Triagem Pref" if ja_tri_pref else "Triagem Pref",
            on_click=lambda _: threading.Thread(
                target=executar_acao_presenca, args=("tri_pref",), daemon=True
            ).start(),
            style=(
                style_pref_remove
                if ja_tri_pref
                else style_pref_hi
            ),
        )

        # Extrair dados dos tratamentos
        if isinstance(dados, (list, tuple)):
            p_ag, p_re = (dados[6] or 0), (dados[7] or 0)
            c_ag, c_re = (dados[19] or 0), (dados[25] or 0)
            m_ag, m_re = (dados[20] or 0), (dados[26] or 0)
            i_ag, i_re = (dados[21] or 0), (dados[27] or 0)
            pt_ag, pt_re = (dados[23] or 0), (dados[28] or 0)

        # Se não houver tratamentos ativos, zera indicadores (mostra 0/0)
        if not tratamentos:
            p_ag = p_re = 0
            c_ag = c_re = 0
            m_ag = m_re = 0
            i_ag = i_re = 0
            pt_ag = pt_re = 0

        else:
            p_ag, p_re = (dados.get("con_passe") or 0), (dados.get("con_npasse") or 0)
            c_ag, c_re = (dados.get("con_cromoterapia") or 0), (
                dados.get("con_ncromo") or 0
            )
            m_ag, m_re = (dados.get("con_massagem") or 0), (dados.get("con_nmass") or 0)
            i_ag, i_re = (dados.get("con_cirurgia") or 0), (
                dados.get("con_ncirur") or 0
            )
            pt_ag, pt_re = (dados.get("con_pontos") or 0), (
                dados.get("con_nponto") or 0
            )

        btn_indicador_p = ft.ElevatedButton(
            f"Passe: {p_re}/{p_ag}",
            style=style_available if p_ag > p_re else style_default,
            on_click=lambda _: threading.Thread(
                target=registrar_uso_e_atualizar,
                args=(registrar_uso_passe, "Passe"),
                daemon=True,
            ).start(),
            width=120,
            height=36,
        )

        btn_indicador_c = ft.ElevatedButton(
            f"Cromo: {c_re}/{c_ag}",
            style=style_available if c_ag > c_re else style_default,
            on_click=lambda _: threading.Thread(
                target=registrar_uso_e_atualizar,
                args=(registrar_uso_cromo, "Cromoterapia"),
                daemon=True,
            ).start(),
            width=120,
            height=36,
        )

        btn_indicador_m = ft.ElevatedButton(
            f"Mass: {m_re}/{m_ag}",
            style=style_available if m_ag > m_re else style_default,
            on_click=lambda _: threading.Thread(
                target=registrar_uso_e_atualizar,
                args=(registrar_uso_massagem, "Massagem"),
                daemon=True,
            ).start(),
            width=120,
            height=36,
        )

        btn_indicador_i = ft.ElevatedButton(
            f"Cirur: {i_re}/{i_ag}",
            style=style_available if i_ag > i_re else style_default,
            on_click=lambda _: threading.Thread(
                target=registrar_uso_e_atualizar,
                args=(registrar_uso_cirurgia, "Cirurgia"),
                daemon=True,
            ).start(),
            width=120,
            height=36,
        )

        btn_indicador_pt = ft.ElevatedButton(
            f"Ponto: {pt_re}/{pt_ag}",
            style=style_available if pt_ag > pt_re else style_default,
            on_click=lambda _: threading.Thread(
                target=registrar_uso_e_atualizar,
                args=(registrar_uso_ponto, "Ponto"),
                daemon=True,
            ).start(),
            width=120,
            height=36,
        )

        botoes_tratamentos = []
        if p_ag > 0:
            botoes_tratamentos.append(btn_indicador_p)
        if c_ag > 0:
            botoes_tratamentos.append(btn_indicador_c)
        if m_ag > 0:
            botoes_tratamentos.append(btn_indicador_m)
        if i_ag > 0:
            botoes_tratamentos.append(btn_indicador_i)
        if pt_ag > 0:
            botoes_tratamentos.append(btn_indicador_pt)

        quantidades_prescritas = (p_ag, c_ag, m_ag, i_ag, pt_ag)
        qtd_tratamentos_indicados = contar_tratamentos_indicados(
            quantidades_prescritas, tratamentos
        )
        tipo_fila = tipo_fila_indicada(quantidades_prescritas, tratamentos)

        if selecionado["mostrar_todas_filas"]:
            botoes_fila_triagem = [btn_normal, btn_pref, btn_tri, btn_tri_pref]
        elif tipo_fila == "retorno" and is_pref_cadastro:
            botoes_fila_triagem = [btn_pref]
        elif tipo_fila == "retorno":
            botoes_fila_triagem = [btn_normal]
        elif is_pref_cadastro:
            botoes_fila_triagem = [btn_tri_pref]
        else:
            botoes_fila_triagem = [btn_tri]

        nome_fila_indicada = (
            "Retorno Preferencial"
            if tipo_fila == "retorno" and is_pref_cadastro
            else "Retorno"
            if tipo_fila == "retorno"
            else "Triagem Preferencial"
            if is_pref_cadastro
            else "Triagem"
        )

        def alternar_exibicao_filas(e):
            selecionado["mostrar_todas_filas"] = bool(e.control.value)
            render_detalhes(cid)

        mostrar_todas_filas = ft.Switch(
            label=ft.Text("Todas as filas (exceção)", size=11),
            value=selecionado["mostrar_todas_filas"],
            on_change=alternar_exibicao_filas,
            active_color="#7A3E8E",
            active_track_color="#D9B7E2",
            tooltip="Libera as quatro filas para tratar uma situação excepcional",
            scale=0.78,
        )

        resumo_fila = ft.Text(
            f"Fila indicada: {nome_fila_indicada} "
            f"({qtd_tratamentos_indicados} tratamento(s) indicado(s))",
            size=12,
            weight=ft.FontWeight.BOLD,
            color="#7A3E8E" if is_pref_cadastro else COLOR_TEXT,
        )

        # ==========================

        # NOVOS BOTÕES (DETAILS)

        style_danger = ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE)
        style_primary = ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE
        )
        style_warning = ft.ButtonStyle(
            bgcolor=ft.Colors.PURPLE_700, color=ft.Colors.WHITE
        )

        # Existe tratamento em aberto? (buscar_tratamentos_ativos já retorna status='A')
        tem_aberto = bool(tratamentos)

        def _open_overlay(ctrl):
            # Método mais compatível no Flet web/server: overlay + open flag
            try:
                if ctrl not in page.overlay:
                    page.overlay.append(ctrl)
            except Exception:
                pass
            ctrl.open = True
            page.update()

        def _close_overlay(ctrl):
            ctrl.open = False
            page.update()

        def _snack(msg: str, cor):
            page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=cor)
            page.snack_bar.open = True
            page.update()

        def confirmar_acao(titulo: str, mensagem: str, executar_fn):
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text(titulo),
                content=ft.Text(mensagem),
                actions_alignment=ft.MainAxisAlignment.END,
            )

            def _cancelar(e):
                _close_overlay(dlg)

            def _confirmar(e):
                _close_overlay(dlg)

                # feedback imediato
                status.value = "Processando..."
                status.update()

                def _run():
                    try:
                        executar_fn()
                    except Exception as ex:
                        ui(lambda: _snack(f"Erro: {ex}", ft.Colors.RED_900))
                    finally:
                        # Sempre atualiza o details ao final (independente de sucesso/erro)
                        ui(
                            lambda: (
                                render_detalhes(cid),
                                setattr(status, "value", ""),
                                status.update(),
                            )
                        )

                threading.Thread(target=_run, daemon=True).start()

            dlg.actions = [
                ft.TextButton("Cancelar", on_click=_cancelar),
                ft.ElevatedButton("Confirmar", on_click=_confirmar),
            ]
            _open_overlay(dlg)

        def executar_desistiu():
            n = atualizar_status_tratamentos(cid, "D", "A")
            ui(
                lambda: _snack(
                    f"{n} tratamento(s) marcado(s) como DESISTIU.", ft.Colors.RED_600
                )
            )

        def executar_finalizar():
            n = atualizar_status_tratamentos(cid, "F", "A")
            ui(lambda: _snack(f"{n} tratamento(s) finalizado(s).", ft.Colors.BLUE_700))

        def executar_reiniciar():
            r = reiniciar_tratamento(cid)
            if str(r).strip().lower() == "tratamento em aberto":
                ui(
                    lambda: _snack(
                        "Tratamento em Aberto. Não é possível reiniciar.",
                        ft.Colors.ORANGE_600,
                    )
                )
                return
            ui(
                lambda: _snack(
                    "Tratamento reiniciado com sucesso.", ft.Colors.PURPLE_700
                )
            )

        btn_desistiu = ft.ElevatedButton(
            "Desistiu",
            icon=ft.Icons.CANCEL,
            tooltip="Marca todos os tratamentos em aberto (A) como D",
            style=style_danger,
            on_click=lambda e: confirmar_acao(
                "Confirmar Desistência",
                "Deseja realmente marcar todos os tratamentos em aberto como DESISTIU?",
                executar_desistiu,
            ),
        )

        btn_finalizar = ft.ElevatedButton(
            "Finalizar",
            icon=ft.Icons.DONE_ALL,
            tooltip="Marca todos os tratamentos em aberto (A) como F",
            style=style_primary,
            on_click=lambda e: confirmar_acao(
                "Confirmar Finalização",
                "Deseja finalizar todos os tratamentos em aberto?",
                executar_finalizar,
            ),
        )

        btn_reiniciar = ft.ElevatedButton(
            "Reiniciar",
            icon=(ft.Icons.LOCK if tem_aberto else ft.Icons.REPLAY),
            tooltip="Bloqueado enquanto houver tratamento em aberto",
            style=style_warning,
            disabled=tem_aberto,
            on_click=lambda e: confirmar_acao(
                "Confirmar Reinício",
                "Deseja reiniciar o tratamento deste consulente?\nO diagnóstico atual será movido para o anterior e o atual será limpo.",
                executar_reiniciar,
            ),
        )

        msg_reiniciar = ft.Text(
            "Reiniciar bloqueado: existe tratamento em aberto.",
            size=12,
            color=ft.Colors.RED_600,
            visible=tem_aberto,
        )

        # Monta detalhes passando obs e callback
        detalhes_widget = montar_detalhes_modelo(dados, tratamentos, senhas_fila)

        acoes_col.controls = [
            ft.Text(
                "Tratamentos disponíveis:",
                size=14,
                weight="bold",
                color=COLOR_TEXT,
                visible=bool(botoes_tratamentos),
            ),
            ft.Row(
                botoes_tratamentos,
                wrap=True,
                spacing=10,
                visible=bool(botoes_tratamentos),
            ),
            ft.Container(height=5),
            ft.Container(
                width=330,
                content=ft.Row(
                    [pref_toggle, mostrar_todas_filas],
                    wrap=True,
                    spacing=0,
                    run_spacing=0,
                    tight=True,
                ),
            ),
            ft.Container(height=5),
            resumo_fila,
            ft.Row(botoes_fila_triagem, wrap=True),
            ft.Container(height=5),
            ft.Row([btn_desistiu, btn_finalizar, btn_reiniciar], wrap=True, spacing=10),
            msg_reiniciar,
        ]
        detalhes_col.controls = [
            detalhes_widget,
        ]
        page.update()

        # --- POPUP: Tratamento Terminado ---
        def _to_int(v):
            try:
                return int(v or 0)
            except Exception:
                return 0

        if isinstance(dados, (list, tuple)):
            p_ag, p_re = _to_int(dados[6] or 0), _to_int(dados[7] or 0)
            c_ag, c_re = _to_int(dados[19] or 0), _to_int(dados[25] or 0)
            m_ag, m_re = _to_int(dados[20] or 0), _to_int(dados[26] or 0)
            i_ag, i_re = _to_int(dados[21] or 0), _to_int(dados[27] or 0)
        else:
            p_ag, p_re = _to_int(dados.get("con_passe") or 0), _to_int(
                dados.get("con_npasse") or 0
            )
            c_ag, c_re = _to_int(dados.get("con_cromoterapia") or 0), _to_int(
                dados.get("con_ncromo") or 0
            )
            m_ag, m_re = _to_int(dados.get("con_massagem") or 0), _to_int(
                dados.get("con_nmass") or 0
            )
            i_ag, i_re = _to_int(dados.get("con_cirurgia") or 0), _to_int(
                dados.get("con_ncirur") or 0
            )
            pt_ag, pt_re = _to_int(dados.get("con_pontos") or 0), _to_int(
                dados.get("con_nponto") or 0
            )

        sem_saldo = (
            (p_ag <= p_re) and (c_ag <= c_re) and (m_ag <= m_re) and (i_ag <= i_re)
        )
        tem_movimento = (p_ag + p_re + c_ag + c_re + m_ag + m_re + i_ag + i_re) > 0

        if tem_movimento and sem_saldo:
            _mostrar_popup_tratamento_terminado()

    # --- BUSCA (Debounce) ---
    search_token = {"v": 0}

    def limpar_busca():
        search_token["v"] += 1
        txt_busca.value = ""
        lista.controls.clear()
        status_busca.value = ""
        resultados_busca_box.visible = False
        page.update()
        try:
            txt_busca.focus()
        except Exception:
            pass

    def selecionar_consulente(cid: int, nome: str):
        search_token["v"] += 1
        txt_busca.value = nome or ""
        lista.controls.clear()
        resultados_busca_box.visible = False
        render_detalhes(cid)

    def atualizar_lista(rows):
        lista.controls.clear()
        for r in rows or []:
            cid = r[0] if isinstance(r, (list, tuple)) else r.get("con_codigo")
            nome = r[1] if isinstance(r, (list, tuple)) else r.get("con_nome", "")
            lista.controls.append(
                ft.ListTile(
                    title=ft.Text(nome, color=COLOR_TEXT),
                    subtitle=ft.Text(f"ID: {cid}", color=COLOR_TEXT),
                    on_click=lambda e, c=cid, n=nome: selecionar_consulente(c, n),
                )
            )
        resultados_busca_box.visible = True
        page.update()

    def fazer_busca_async(texto_busca: str, token: int):
        time.sleep(0.25)
        if token != search_token["v"]:
            return
        texto = (texto_busca or "").strip()
        if not texto:
            ui(
                lambda: (
                    setattr(status_busca, "value", ""),
                    lista.controls.clear(),
                    setattr(resultados_busca_box, "visible", False),
                    page.update(),
                )
            )
            return
        rows = buscar_clientes(texto)
        if token != search_token["v"]:
            return
        ui(
            lambda: (
                setattr(status_busca, "value", f"{len(rows)} resultado(s)"),
                atualizar_lista(rows),
            )
        )

    def on_change_busca(e: ft.ControlEvent):
        texto = e.control.value or ""
        search_token["v"] += 1
        token = search_token["v"]
        status_busca.value = "Buscando..."
        resultados_busca_box.visible = bool(texto.strip())
        page.update()
        threading.Thread(
            target=fazer_busca_async, args=(texto, token), daemon=True
        ).start()

    txt_busca.on_change = on_change_busca
    txt_busca.on_submit = on_change_busca

    ferramentas_pdf = ft.Row(
        [
            ft.Row(
                [btn_imprimir, btn_pdf, btn_form_vazio],
                wrap=True,
                spacing=6,
                run_spacing=6,
            ),
            btn_listas,
            ft.Row(
                (
                    [btn_chamada, btn_exportar_base, btn_sql_loader]
                    if current_user and current_user.is_admin
                    else [btn_chamada]
                ),
                wrap=True,
                spacing=6,
                run_spacing=6,
            ),
        ],
        wrap=True,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        spacing=12,
        run_spacing=6,
    )

    header = ft.Container(
        bgcolor=COLOR_HEADER,
        border_radius=12,
        padding=8,
        width=float("inf"),
        content=ft.Column(
            [
                ft.Row(
                    [
                        logo_img,
                        ft.Column(
                            [txt_busca, resultados_busca_box],
                            expand=True,
                            spacing=2,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                        btn_novo,
                        btn_editar,
                        sw_auto,
                    ],
                    spacing=7,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ferramentas_pdf,
            ],
            spacing=6,
        ),
    )
    page.add(
        ft.Row(
            [info_servidor, status_box],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    page.add(
        header,
        ft.ResponsiveRow(
            [
                ft.Column(
                    col={"xs": 12, "md": 4, "lg": 4},
                    controls=[
                        ft.Card(
                            elevation=3,
                            content=ft.Container(
                                padding=15,
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "Tratamentos e Filas",
                                            size=16,
                                            weight="bold",
                                            color=COLOR_TEXT,
                                        ),
                                        ft.Divider(),
                                        ft.Container(
                                            content=acoes_col,
                                            height=565,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ),
                        )
                    ],
                ),
                ft.Column(
                    col={"xs": 12, "md": 8, "lg": 8},
                    controls=[
                        ft.Card(
                            elevation=3,
                            content=ft.Container(
                                padding=15,
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "Detalhes do Consulente",
                                            size=16,
                                            weight="bold",
                                            color=COLOR_TEXT,
                                        ),
                                        ft.Divider(),
                                        ft.Container(
                                            content=detalhes_col,
                                            height=620,
                                            expand=True,
                                        ),
                                    ]
                                ),
                            ),
                        )
                    ],
                ),
            ],
            spacing=15,
            run_spacing=15,
        ),
    )
