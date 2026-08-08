# pdf/layout_a5.py
from __future__ import annotations

import os
from datetime import date as dt_date
from typing import Any

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit

from core.config import get_pdf_ficha_rodape
from core.utils import (
    fmt_data_br,
    preparar_grade,
    to_int,
    extrair_triagem,
    trunc_1linha,
)


def _get(d: Any, key: str, default=None):
    """Acessa dict-row ou objeto/tupla de forma tolerante."""
    if d is None:
        return default
    try:
        if isinstance(d, dict):
            return d.get(key, default)
        return d[key]
    except Exception:
        return default


def _idade_anos(nasc):
    if not nasc or not hasattr(nasc, "year"):
        return None
    hoje = dt_date.today()
    anos = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
    return anos


def _logo_path_padrao(logo_path: str | None = None) -> str | None:
    """Retorna o caminho da logo."""
    candidatos = []
    if logo_path:
        candidatos.append(logo_path)
    candidatos.append(os.path.join("assets", "logopb.jpg"))
    candidatos.append("logopb.jpg")

    for p in candidatos:
        if p and os.path.exists(p):
            return p
    return None


def _trunc_chars(txt: str, n: int) -> str:
    txt = (txt or "").strip()
    if not txt:
        return ""
    if len(txt) <= n:
        return txt
    return txt[: n - 3].rstrip() + "..."


def _fmt_ddmmyy(valor) -> str:
    """
    Normaliza data para dd/mm/yy.

    Aceita:
    - date/datetime (strftime)
    - strings "dd/mm", "dd/mm/aaaa", "dd/mm/aa"
    - caso não reconheça, retorna como string original.
    """
    if not valor:
        return ""
    # objeto date/datetime
    try:
        if hasattr(valor, "strftime"):
            return valor.strftime("%d/%m/%y")
    except Exception:
        pass

    s = str(valor).strip()
    if not s:
        return ""

    # se já parece dd/mm/yy ou dd/mm/yyyy
    if "/" in s:
        partes = [p.strip() for p in s.split("/")]
        if len(partes) == 2:
            # "dd/mm" -> assume ano atual
            dd, mm_ = partes[0].zfill(2), partes[1].zfill(2)
            yy = dt_date.today().strftime("%y")
            return f"{dd}/{mm_}/{yy}"
        if len(partes) == 3:
            dd, mm_, yy = partes[0].zfill(2), partes[1].zfill(2), partes[2]
            yy = yy.strip()
            if len(yy) == 4:
                yy = yy[2:]
            yy = yy.zfill(2)
            return f"{dd}/{mm_}/{yy}"

    return s


def gerar_pdf_plano_tratamento_a5(
    caminho_pdf: str,
    dados: dict,
    tratamentos: list[dict],
    logo_path: str | None = None,
    senha_tipo: str | None = None,
    senha_numero: int | None = None,
):
    texto_rodape = get_pdf_ficha_rodape()
    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=A5,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=4 * mm,
        bottomMargin=(11 * mm if texto_rodape else 5 * mm),
    )

    def _desenhar_rodape(canvas, _doc):
        if not texto_rodape:
            return

        canvas.saveState()
        font_name = "Helvetica"
        font_size = 7.5
        linhas = simpleSplit(texto_rodape, font_name, font_size, doc.width)
        while len(linhas) > 2 and font_size > 5.0:
            font_size -= 0.5
            linhas = simpleSplit(texto_rodape, font_name, font_size, doc.width)

        canvas.setFillColor(colors.red)
        canvas.setFont(font_name, font_size)
        leading = font_size + 1
        y = 3 * mm + ((len(linhas) - 1) * leading)
        for linha in linhas[:2]:
            canvas.drawCentredString(A5[0] / 2, y, linha)
            y -= leading
        canvas.restoreState()

    styles = getSampleStyleSheet()

    def _add_or_update_style(ps: ParagraphStyle):
        name = ps.name
        if name in styles.byName:
            st = styles[name]
            st.parent = ps.parent
            st.fontName = ps.fontName
            st.fontSize = ps.fontSize
            st.leading = ps.leading
            st.alignment = ps.alignment
            st.textColor = ps.textColor
            st.spaceBefore = ps.spaceBefore
            st.spaceAfter = ps.spaceAfter
            st.leftIndent = ps.leftIndent
            st.rightIndent = ps.rightIndent
            st.firstLineIndent = ps.firstLineIndent
        else:
            styles.add(ps)

    # ===== Estilos base =====
    _add_or_update_style(
        ParagraphStyle(
            name="H",
            parent=styles["Normal"],
            fontSize=10.0,
            leading=11.0,
            alignment=1,
        )
    )
    _add_or_update_style(
        ParagraphStyle(
            name="K",
            parent=styles["Normal"],
            fontSize=11.2,
            leading=12.2,
            alignment=1,
        )
    )
    _add_or_update_style(
        ParagraphStyle(name="L", parent=styles["Normal"], fontSize=10.5, leading=11.5)
    )
    _add_or_update_style(
        ParagraphStyle(
            name="Small", parent=styles["Normal"], fontSize=9.0, leading=10.0
        )
    )
    _add_or_update_style(
        ParagraphStyle(name="Tiny", parent=styles["Normal"], fontSize=8.2, leading=9.0)
    )

    # ===== Diagnósticos (regras atuais) =====
    _add_or_update_style(
        ParagraphStyle(
            name="DiagAtual",
            parent=styles["Normal"],
            fontSize=12,
            leading=15,
            alignment=0,
        )
    )
    _add_or_update_style(
        ParagraphStyle(
            name="DiagAnt",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            alignment=0,
        )
    )

    # ===== Grade / tratamentos =====
    _add_or_update_style(
        ParagraphStyle(name="XS", parent=styles["Normal"], fontSize=7.4, leading=8.0, alignment=1)
    )
    _add_or_update_style(
        ParagraphStyle(name="XSLeft", parent=styles["XS"], alignment=0)
    )
    _add_or_update_style(
        ParagraphStyle(
            name="CheckboxLabel",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=9.5,
            alignment=1,
        )
    )
    _add_or_update_style(
        ParagraphStyle(
            name="CheckboxLabelLeft",
            parent=styles["CheckboxLabel"],
            alignment=0,
        )
    )
    _add_or_update_style(
        ParagraphStyle(name="M", parent=styles["Normal"], fontSize=8.0, leading=9.0)
    )
    _add_or_update_style(
        ParagraphStyle(name="Resumo", parent=styles["Normal"], fontSize=8.0, leading=9.0)
    )

    def P(txt, st="L"):
        txt = "" if txt is None else str(txt)
        return Paragraph(txt.replace("\n", "<br/>"), styles[st])

    DIAG_ATUAL_ALTURA_FIXA = 48 * mm
    DIAG_PAD_LEFT_RIGHT = 5 * mm
    DIAG_PAD_TOP_BOTTOM = 4 * mm

    data_plano = fmt_data_br(_get(dados, "con_datainicial"))
    hoje = fmt_data_br(dt_date.today())
    is_novo_tratamento = data_plano == hoje

    # --- tratamentos ativos para triagem ---
    trat_ativos = []
    for t in tratamentos or []:
        st = _get(t, "tra_status", "A")
        if (st or "A") == "A":
            trat_ativos.append(t)

    # ===== Diagnósticos (TRUNCADOS EM 300) =====
    diagnostico_atual = (_get(dados, "con_diagnostico") or "").strip()

    diagnostico_anterior = (_get(dados, "con_diagnant") or "").strip()
    if not diagnostico_anterior:
        campos_fallback = [
            "con_diagnostico_anterior",
            "con_diagnantr",
            "con_diagnostico_ant",
        ]
        for campo in campos_fallback:
            diag = (_get(dados, campo, "") or "").strip()
            if diag:
                diagnostico_anterior = diag
                break
    diagnostico_anterior = _trunc_chars(diagnostico_anterior, 300)

    # ===== Header =====
    logo_file = _logo_path_padrao(logo_path)
    logo = Image(logo_file, width=18 * mm, height=9 * mm) if logo_file else P("", "L")

    if is_novo_tratamento:
        titulo = P(f"<b>NOVO TRATAMENTO - {hoje}</b>", "K")
    else:
        titulo = P(f"<b>PLANO DE TRATAMENTO - {data_plano}</b>", "K")

    header = Table([[logo, titulo]], colWidths=[20 * mm, None])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -1), 1.0, colors.black),
            ]
        )
    )

    # ===== Senha =====
    senha_block = None
    if senha_tipo and senha_numero is not None:
        senha_txt = f"<b>SENHA {senha_tipo.upper()}: {senha_numero}</b>"
        senha_block = Table([[P(senha_txt, "K")]], colWidths=[doc.width])
        senha_block.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

    # ===== Identificação - TUDO EM UMA LINHA =====
    tri = extrair_triagem(trat_ativos)

    nasc_date = _get(dados, "con_nascim")
    nasc_br = fmt_data_br(nasc_date)
    idade = _idade_anos(nasc_date)

    nasc_idade_txt = f"Nasc: {nasc_br}"
    if idade is not None:
        nasc_idade_txt += f", {idade} anos"

    medium_str = trunc_1linha(_get(tri, "tra_medium"), n=20) if tri else "-"
    entidade_str = trunc_1linha(_get(tri, "tra_entidade"), n=20) if tri else "-"

    nome = _get(dados, "con_nome", "") or ""

    endereco = _get(dados, "con_endereco", "")
    bairro = _get(dados, "con_bairro", "")
    cidade = _get(dados, "con_cidade", "")
    estado = _get(dados, "con_estado", "")
    cep = _get(dados, "con_cep", "")
    celular1 = _get(dados, "con_fonecel", "")
    celular2 = _get(dados, "con_celular2", "")
    email = _get(dados, "con_email", "")

    cep_formatado = ""
    if cep:
        cep_limpo = "".join(filter(str.isdigit, str(cep)))
        if len(cep_limpo) == 8:
            cep_formatado = f"{cep_limpo[:5]}-{cep_limpo[5:]}"

    celular_str = celular1
    if celular2:
        celular_str = f"{celular1} / {celular2}" if celular1 else celular2

    cidade_estado = f"{cidade}/{estado}" if cidade and estado else f"{cidade}{estado}"

    ident_data = [
        [P(f"<b>{nome.upper()}</b>", "K"), "", ""],
        [
            P(f"<b>{nasc_idade_txt}</b>", "Small"),
            P(f"<b>Médium:</b> {medium_str}", "Small"),
            P(f"<b>Ent:</b> {entidade_str}", "Small"),
        ],
        [P(f"<b>End:</b> {endereco}", "Tiny"), "", ""],
        [
            P(f"<b>Bairro:</b> {bairro}", "Tiny"),
            P(f"<b>Cid:</b> {cidade_estado}", "Tiny"),
            P(f"<b>CEP:</b> {cep_formatado}", "Tiny"),
        ],
        [P(f"<b>Cel:</b> {celular_str}", "Tiny"), "", ""],
        [P(f"<b>Email:</b> {email}", "Tiny"), "", ""],
    ]

    ident = Table(
        ident_data, colWidths=[doc.width * 0.35, doc.width * 0.35, doc.width * 0.30]
    )
    ident.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("SPAN", (0, 0), (2, 0)),  # Nome
                ("SPAN", (0, 2), (2, 2)),  # Endereço
                ("SPAN", (0, 4), (2, 4)),  # Celular
                ("SPAN", (0, 5), (2, 5)),  # Email
                ("BACKGROUND", (0, 0), (2, 0), colors.whitesmoke),
                ("BACKGROUND", (0, 1), (2, 1), colors.HexColor("#F5F5F5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    # ===== Labels e Aviso =====
    aviso_cambone = None
    if is_novo_tratamento:
        aviso_cambone = Table(
            [
                [
                    P(
                        "<b>Atenção Consulente! Preencher somente os campos acima.</b>",
                        "H",
                    )
                ]
            ],
            colWidths=[doc.width],
        )
        aviso_cambone.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF3CD")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#856404")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#FFC107")),
                ]
            )
        )

    if not is_novo_tratamento:
        diag_label = Table(
            [[P("<b>DIAGNÓSTICO ATUAL - USE O VERSO DA FOLHA CASO NECESSÁRIO</b>", "H")]], colWidths=[doc.width]
        )
        diag_label.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.lightgrey),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
    else:
        diag_label = Table(
            [[P("<b>DIAGNÓSTICO ATUAL - USE O VERSO DA FOLHA CASO NECESSÁRIO</b>", "H")]], colWidths=[doc.width]
        )
        diag_label.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.lightblue),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("BOX", (0, 0), (-1, -1), 1.0, colors.black),
                ]
            )
        )

    diag_ant_label = Table(
        [[P("<b>DIAGNÓSTICO ANTERIOR</b>", "H")]], colWidths=[doc.width]
    )
    diag_ant_label.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    # ===== Caixas Diagnóstico =====
    diag_par = Paragraph(
        (diagnostico_atual or "").replace("\n", "<br/>"), styles["DiagAtual"]
    )
    box_txt = Table(
        [[diag_par]],
        colWidths=[doc.width],
        rowHeights=[DIAG_ATUAL_ALTURA_FIXA],
    )
    box_txt.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.0, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), DIAG_PAD_LEFT_RIGHT),
                ("RIGHTPADDING", (0, 0), (-1, -1), DIAG_PAD_LEFT_RIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), DIAG_PAD_TOP_BOTTOM),
                ("BOTTOMPADDING", (0, 0), (-1, -1), DIAG_PAD_TOP_BOTTOM),
            ]
        )
    )

    # diag_ant_par = Paragraph(
    #    (diagnostico_anterior or "").replace("\n", "<br/>"), styles["DiagAnt"]
    # )
    # box_ant_txt = Table([[diag_ant_par]], colWidths=[doc.width])
    # box_ant_txt.setStyle(
    #    TableStyle(
    #        [
    #            ("BOX", (0, 0), (-1, -1), 1.0, colors.grey),
    #            ("BACKGROUND", (0, 0), (-1, -1), colors.floralwhite),
    #            ("VALIGN", (0, 0), (-1, -1), "TOP"),
    #            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
    #            ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
    #            ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
    #            ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
    #        ]
    #    )
    # )

    # ===== Blocos específicos =====
    obs_table = None

    if not is_novo_tratamento:
        # RESUMO
        q_passe = to_int(_get(dados, "con_passe"))
        q_cromo = to_int(_get(dados, "con_cromoterapia"))
        q_massa = to_int(_get(dados, "con_massagem"))
        q_cirurg = to_int(_get(dados, "con_cirurgia"))
        q_ponto = to_int(_get(dados, "con_pontos"))
        q_npasse = to_int(_get(dados, "con_npasse"))
        q_ncromo = to_int(_get(dados, "con_ncromo"))
        q_nmassa = to_int(_get(dados, "con_nmass"))
        q_ncirurg = to_int(_get(dados, "con_ncirur"))
        q_nponto = to_int(_get(dados, "con_nponto"))

        total_planejado = q_passe + q_cromo + q_massa + q_cirurg + q_ponto
        total_realizado = q_npasse + q_ncromo + q_nmassa + q_ncirurg + q_nponto
        percentual = (
            (total_realizado / total_planejado * 100) if total_planejado > 0 else 0
        )

        linha_resumo = (
            f"<b>Passe:</b>{q_npasse}/{q_passe} "
            f"| <b>Cromo:</b>{q_ncromo}/{q_cromo} "
            f"| <b>Mass:</b>{q_nmassa}/{q_massa} "
            f"| <b>Cir:</b>{q_ncirurg}/{q_cirurg} "
            f"| <b>Ponto:</b>{q_nponto}/{q_ponto} "
            f"| <b>Total:</b>{total_realizado}/{total_planejado} ({percentual:.0f}%)"
        )
        resumo = Table([[P(linha_resumo, "Resumo")]], colWidths=[doc.width])
        resumo.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )

        # ===== GRADE (colunas compactadas independentemente + data dd/mm/yy) =====
        linhas_fixas, por_cat = preparar_grade(tratamentos or [])

        # Fallback local: core.utils.preparar_grade pode ainda não criar a categoria PONTO.
        pontos_lista = []
        for t in tratamentos or []:
            cod = 0
            try:
                cod = int(_get(t, "tra_codtra") or 0)
            except Exception:
                cod = 0
            desc = str(_get(t, "tra_descricao", "") or "").upper()
            if cod == 5 or desc.startswith("PONTO"):
                pontos_lista.append(t)
        linhas_fixas = max(linhas_fixas, len(pontos_lista))
        por_cat.setdefault("PONTO", pontos_lista)

        def _mediums_tratamento(item) -> str:
            nomes = [
                str(_get(item, "tra_medium", "") or "").strip(),
                str(_get(item, "tra_medium2", "") or "").strip(),
                str(_get(item, "tra_medium3", "") or "").strip(),
            ]
            return "/".join(nome for nome in nomes if nome)

        def _extrair_lista(cat: str):
            """
            Gera lista compacta [(data_txt, medium_txt), ...] para a categoria,
            usando acesso tolerante a categorias ausentes.
            """
            lista: list[tuple[str, str]] = []
            itens = por_cat.get(cat, []) or []

            for item in itens:
                dt_txt = _fmt_ddmmyy(_get(item, "tra_data"))
                md_txt = _mediums_tratamento(item)
                if dt_txt or md_txt:
                    lista.append((dt_txt, md_txt))

            return lista

        lista_p = _extrair_lista("PASSE")
        lista_c = _extrair_lista("CROMO")
        lista_m = _extrair_lista("MASSA")
        lista_s = _extrair_lista("CIRURG")
        lista_pt = _extrair_lista("PONTO")

        # Fallback: se core.utils ainda não categorizar tra_codtra=5 como PONTO.
        if not lista_pt:
            for t in tratamentos or []:
                cod = 0
                try:
                    cod = int(_get(t, "tra_codtra") or 0)
                except Exception:
                    cod = 0
                desc = str(_get(t, "tra_descricao", "") or "").upper()
                if cod == 5 or desc.startswith("PONTO"):
                    dt_txt = _fmt_ddmmyy(_get(t, "tra_data"))
                    md_txt = _mediums_tratamento(t)
                    if dt_txt or md_txt:
                        lista_pt.append((dt_txt, md_txt))

        max_linhas = max(len(lista_p), len(lista_c), len(lista_m), 1)
        hoje_proc = dt_date.today().strftime("%d/%m/%y")

        grid = [
            [
                P("<b>PASSE</b>", "XS"),
                P("<b>CROMO</b>", "XS"),
                P("<b>MASSA</b>", "XS"),
            ]
        ]

        def _celula_trat(item: tuple[str, str]):
            data_txt = (item[0] or "").strip()
            medium_txt = (item[1] or "").strip()
            data_html = data_txt.replace(" ", "&nbsp;")
            medium_html = medium_txt.replace(" ", "&nbsp;")
            if data_txt and medium_txt:
                conteudo = f"<b>{data_html}</b>&nbsp;<font size='6.2'>{medium_html}</font>"
            elif data_txt:
                conteudo = f"<b>{data_html}</b>"
            else:
                conteudo = f"<font size='6.2'>{medium_html}</font>"
            return P(conteudo, "XSLeft")

        destaques_grade = []
        for i in range(max_linhas):
            p = lista_p[i] if i < len(lista_p) else ("", "")
            c = lista_c[i] if i < len(lista_c) else ("", "")
            m = lista_m[i] if i < len(lista_m) else ("", "")

            for col, item in enumerate([p, c, m]):
                if (item[0] or "").strip() == hoje_proc:
                    destaques_grade.append(("BACKGROUND", (col, i + 1), (col, i + 1), colors.HexColor("#E6E6E6")))

            grid.append(
                [
                    _celula_trat(p),
                    _celula_trat(c),
                    _celula_trat(m),
                ]
            )

        largura_grade = doc.width - (2 * mm)
        largura_coluna = largura_grade / 3
        grade = Table(
            grid,
            colWidths=[largura_coluna] * 3,
            rowHeights=[4.5 * mm] + [5.5 * mm] * max_linhas,
        )
        grade_style = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 1), (-1, -1), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]
        grade.setStyle(
            TableStyle(grade_style + destaques_grade)
        )

        grade_cirurgia = None
        tem_cirurgia = q_cirurg > 0 or q_ncirurg > 0 or bool(lista_s)
        if tem_cirurgia:
            max_linhas_cirurgia = max(len(lista_s), len(lista_pt), 1)
            grid_cirurgia = [
                [
                    P("<b>CIRURG</b>", "XS"),
                    P("<b>PONTO</b>", "XS"),
                ]
            ]

            destaques_cirurgia = []
            for i in range(max_linhas_cirurgia):
                s = lista_s[i] if i < len(lista_s) else ("", "")
                pt = lista_pt[i] if i < len(lista_pt) else ("", "")
                for col, item in enumerate([s, pt]):
                    if (item[0] or "").strip() == hoje_proc:
                        destaques_cirurgia.append(("BACKGROUND", (col, i + 1), (col, i + 1), colors.HexColor("#E6E6E6")))
                grid_cirurgia.append([_celula_trat(s), _celula_trat(pt)])

            largura_coluna_cirurgia = largura_grade / 2
            grade_cirurgia = Table(
                grid_cirurgia,
                colWidths=[largura_coluna_cirurgia] * 2,
                rowHeights=[4.5 * mm] + [5.5 * mm] * max_linhas_cirurgia,
            )
            grade_cirurgia_style = [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
            grade_cirurgia.setStyle(
                TableStyle(grade_cirurgia_style + destaques_cirurgia)
            )

        # OBSERVAÇÕES
        observacoes = _get(dados, "con_observacoes", "")
        if observacoes and max_linhas <= 8:
            obs_truncada = (
                (observacoes[:80] + "...") if len(observacoes) > 80 else observacoes
            )
            obs_table = Table(
                [[P("<b>OBSERVAÇÕES:</b>", "L")], [P(obs_truncada, "M")]],
                colWidths=[doc.width],
                rowHeights=[4.0 * mm, 6.0 * mm],
            )
            obs_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                        ("SPAN", (0, 0), (-1, 0)),
                        ("SPAN", (0, 1), (-1, 1)),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )

    else:
        # Formulário do novo tratamento (mantido)
        formulario_titulo = Table(
            [[P("<b>TRATAMENTOS PRESCRITOS</b>", "H")]], colWidths=[doc.width]
        )
        formulario_titulo.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.lightgrey),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        altura_quadrados_total = 40 * mm
        altura_quadrado = altura_quadrados_total / 2

        quadrados_data = [
            [
                Table(
                    [[P("Passe", "CheckboxLabelLeft")], [""]],
                    colWidths=[doc.width * 0.45],
                    rowHeights=[5 * mm, altura_quadrado - 5 * mm],
                ),
                Table(
                    [[P("Cromoterapia", "CheckboxLabelLeft")], [""]],
                    colWidths=[doc.width * 0.45],
                    rowHeights=[5 * mm, altura_quadrado - 5 * mm],
                ),
            ],
            [
                Table(
                    [[P("Massagem", "CheckboxLabelLeft")], [""]],
                    colWidths=[doc.width * 0.45],
                    rowHeights=[5 * mm, altura_quadrado - 5 * mm],
                ),
                Table(
                    [[P("Cirurgia", "CheckboxLabelLeft")], [""]],
                    colWidths=[doc.width * 0.45],
                    rowHeights=[5 * mm, altura_quadrado - 5 * mm],
                ),
            ],
        ]

        quadrados = Table(
            quadrados_data,
            colWidths=[doc.width * 0.5, doc.width * 0.5],
            rowHeights=[altura_quadrado, altura_quadrado],
        )
        quadrados.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (0, 0), 1.0, colors.black),
                    ("BOX", (1, 0), (1, 0), 1.0, colors.black),
                    ("BOX", (0, 1), (0, 1), 1.0, colors.black),
                    ("BOX", (1, 1), (1, 1), 1.0, colors.black),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )

        assinatura = Table(
            [[P("<b>Médium Passe:</b> _________________________", "L")]],
            colWidths=[doc.width],
            rowHeights=[7 * mm],
        )
        assinatura.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

    # ===== Montagem =====
    elementos = [header]

    if senha_block:
        elementos.append(senha_block)
        elementos.append(Spacer(1, 1 * mm))

    elementos.append(ident)
    elementos.append(Spacer(1, 1.5 * mm))

    if aviso_cambone:
        elementos.append(aviso_cambone)
        elementos.append(Spacer(1, 1 * mm))

    elementos.append(diag_label)
    elementos.append(box_txt)

    # if diagnostico_anterior and diagnostico_anterior.strip():
    #    elementos.append(Spacer(1, 2 * mm))
    #    elementos.append(diag_ant_label)
    #    elementos.append(box_ant_txt)

    # elementos.append(Spacer(1, 3 * mm))

    if not is_novo_tratamento:
        elementos.append(resumo)
        elementos.append(Spacer(1, 1.5 * mm))
        elementos.append(grade)
        if grade_cirurgia:
            elementos.append(Spacer(1, 1 * mm))
            elementos.append(grade_cirurgia)
        if obs_table:
            elementos.append(Spacer(1, 1.5 * mm))
            elementos.append(obs_table)
    else:
        elementos.append(formulario_titulo)
        elementos.append(Spacer(1, 1 * mm))
        elementos.append(quadrados)
        elementos.append(Spacer(1, 1.5 * mm))
        elementos.append(assinatura)

    doc.build(
        elementos,
        onFirstPage=_desenhar_rodape,
        onLaterPages=_desenhar_rodape,
    )
