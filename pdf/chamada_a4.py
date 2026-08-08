# pdf/chamada_a4.py
import os
from datetime import datetime
from typing import Any, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

LINHAS_POR_PAGINA = 50
ALTURA_CABECALHO = 14
ALTURA_LINHA = 13


def _as_rows(rows: Any) -> List[Tuple[str, str]]:
    """Converte rows para formato (num, nome)."""
    out: List[Tuple[str, str]] = []
    if not rows:
        return out

    for r in rows:
        if isinstance(r, dict):
            num = r.get("numero", "")
            nome = r.get("con_nome", r.get("nome", ""))
        else:
            num = r[0] if len(r) > 0 else ""
            nome = r[1] if len(r) > 1 else ""

        out.append((str(num), str(nome)))
    return out


def _logo(path: Optional[str]):
    if path and os.path.exists(path):
        return path
    return None


def _estilo_tabela_coluna():
    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("SPAN", (0, 0), (1, 0)),
            ("SPAN", (2, 0), (3, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("BACKGROUND", (0, 1), (-1, 1), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, 1), "CENTER"),
            ("ALIGN", (0, 2), (0, -1), "CENTER"),
            ("ALIGN", (2, 2), (2, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
        ]
    )


def _tabela_colunada(
    rows_pref: List[Tuple[str, str]],
    rows_normal: List[Tuple[str, str]],
    largura: float,
    linhas_min: int,
):
    data = [
        ["PREFERENCIAL", "", "NORMAL", ""],
        ["Senha", "Nome", "Senha", "Nome"],
    ]

    pref = list(rows_pref)
    normal = list(rows_normal)
    while len(pref) < linhas_min:
        pref.append(("", ""))
    while len(normal) < linhas_min:
        normal.append(("", ""))

    for i in range(linhas_min):
        pref_num, pref_nome = pref[i]
        normal_num, normal_nome = normal[i]
        data.append([pref_num, pref_nome, normal_num, normal_nome])

    tabela = Table(
        data,
        colWidths=[14 * mm, (largura / 2) - 14 * mm, 14 * mm, (largura / 2) - 14 * mm],
        rowHeights=[ALTURA_CABECALHO, ALTURA_CABECALHO]
        + [ALTURA_LINHA] * linhas_min,
        repeatRows=2,
    )
    tabela.setStyle(_estilo_tabela_coluna())
    return tabela


def _pagina_chamada_colunada(
    titulo: str,
    data_ref: str,
    rows_pref: List[Tuple[str, str]],
    rows_normal: List[Tuple[str, str]],
    logo_path: Optional[str],
    linhas_min: int = 35,
):
    styles = getSampleStyleSheet()
    titulo_style = styles["Heading3"]

    story = []
    lg = _logo(logo_path)

    if lg:
        header_tbl = Table(
            [
                [
                    Image(lg, width=30 * mm, height=15 * mm),
                    Paragraph(f"<b>{titulo}</b><br/>Data: {data_ref}", titulo_style),
                ]
            ],
            colWidths=[35 * mm, 155 * mm],
        )
    else:
        header_tbl = Table(
            [[Paragraph(f"<b>{titulo}</b> - Data: {data_ref}", titulo_style)]],
            colWidths=[190 * mm],
        )

    header_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(header_tbl)
    story.append(Spacer(1, 6))

    largura_tabela = 184 * mm
    linhas = max(linhas_min, len(rows_pref), len(rows_normal))
    linhas = min(linhas, LINHAS_POR_PAGINA)

    story.append(_tabela_colunada(rows_pref, rows_normal, largura_tabela, linhas))
    return story


def _paginas_chamada_colunada(
    titulo: str,
    data_ref: str,
    rows_pref: List[Tuple[str, str]],
    rows_normal: List[Tuple[str, str]],
    logo_path: Optional[str],
):
    total = max(len(rows_pref), len(rows_normal), 1)
    story = []

    for inicio in range(0, total, LINHAS_POR_PAGINA):
        fim = inicio + LINHAS_POR_PAGINA
        titulo_pagina = titulo if inicio == 0 else f"{titulo} (continua)"
        if story:
            story.append(PageBreak())
        story += _pagina_chamada_colunada(
            titulo_pagina,
            data_ref,
            rows_pref[inicio:fim],
            rows_normal[inicio:fim],
            logo_path,
        )

    return story


def gerar_pdf_chamada_4paginas(
    caminho_pdf: str,
    rows_normal: Any,
    rows_pref: Any,
    rows_triagem: Any,
    rows_triagem_pref: Any,
    data_ref: Optional[str] = None,
    logo_path: Optional[str] = None,
):
    """Gera PDF com uma pagina para Retorno e outra para Triagem."""
    os.makedirs(os.path.dirname(caminho_pdf) or ".", exist_ok=True)

    if not data_ref:
        data_ref = datetime.now().strftime("%d/%m/%Y")

    retorno_normal = _as_rows(rows_normal)
    retorno_pref = _as_rows(rows_pref)
    triagem_normal = _as_rows(rows_triagem)
    triagem_pref = _as_rows(rows_triagem_pref)

    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    story = _paginas_chamada_colunada(
        "Lista RETORNO", data_ref, retorno_pref, retorno_normal, logo_path
    )
    story.append(PageBreak())
    story += _paginas_chamada_colunada(
        "Lista TRIAGEM", data_ref, triagem_pref, triagem_normal, logo_path
    )

    doc.build(story)
    return caminho_pdf
