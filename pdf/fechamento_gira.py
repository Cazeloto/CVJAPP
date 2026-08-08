from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Mapping

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from core.paths import resource_path


FILAS_PDF = (
    ("retorno", "Retorno", "#E8F0FE", "#2855A6"),
    ("retornopref", "Retorno Preferencial", "#FFF3CD", "#7A5900"),
    ("triagem", "Triagem", "#E2F4EA", "#19623A"),
    ("triagempref", "Triagem Preferencial", "#F3E5F5", "#6A3472"),
)


def _inteiro(valor) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def gerar_pdf_fechamento_gira(
    caminho: str | Path,
    resumo: Mapping[str, Mapping[str, int]],
    data_ref: date | None = None,
    centro_nome: str = "Casa da Vovó Joaquina",
) -> str:
    """Gera um fechamento A4 com totalizadores das quatro filas."""
    data_ref = data_ref or date.today()
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)

    largura, altura = A4
    margem = 18 * mm
    canvas = Canvas(str(destino), pagesize=A4)
    canvas.setTitle("Fechamento da Gira")
    canvas.setAuthor(centro_nome)

    logo_path = Path(resource_path("assets/logopb.jpg"))
    if logo_path.is_file():
        canvas.drawImage(
            str(logo_path),
            margem,
            altura - 38 * mm,
            width=34 * mm,
            height=20 * mm,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )

    canvas.setFillColor(colors.HexColor("#5B315E"))
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(margem + 42 * mm, altura - 24 * mm, "Fechamento da Gira")
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(
        margem + 42 * mm,
        altura - 31 * mm,
        f"{centro_nome} - {data_ref.strftime('%d/%m/%Y')}",
    )

    canvas.setStrokeColor(colors.HexColor("#C9A3C8"))
    canvas.setLineWidth(1)
    canvas.line(margem, altura - 43 * mm, largura - margem, altura - 43 * mm)

    espaco = 8 * mm
    card_largura = (largura - 2 * margem - espaco) / 2
    card_altura = 47 * mm
    topo_cards = altura - 55 * mm

    total_chamados = 0
    total_faltam = 0

    for indice, (fila, titulo, fundo, texto) in enumerate(FILAS_PDF):
        dados = resumo.get(fila, {})
        chamados = _inteiro(dados.get("chamados"))
        faltam = _inteiro(dados.get("faltam"))
        total = chamados + faltam
        total_chamados += chamados
        total_faltam += faltam

        coluna = indice % 2
        linha = indice // 2
        x = margem + coluna * (card_largura + espaco)
        y = topo_cards - (linha + 1) * card_altura - linha * espaco

        canvas.setFillColor(colors.HexColor(fundo))
        canvas.roundRect(x, y, card_largura, card_altura, 8, stroke=0, fill=1)

        canvas.setFillColor(colors.HexColor(texto))
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(x + 8 * mm, y + card_altura - 11 * mm, titulo)

        centros = (
            (x + card_largura * 0.18, "Chamados", chamados),
            (x + card_largura * 0.50, "Faltam", faltam),
            (x + card_largura * 0.82, "Total", total),
        )
        for centro_x, rotulo, valor in centros:
            canvas.setFont("Helvetica-Bold", 18)
            canvas.drawCentredString(centro_x, y + 17 * mm, str(valor))
            canvas.setFont("Helvetica", 8)
            canvas.drawCentredString(centro_x, y + 10 * mm, rotulo)

    total_inscritos = total_chamados + total_faltam
    resumo_y = 74 * mm
    resumo_altura = 48 * mm

    canvas.setFillColor(colors.HexColor("#F6F1F6"))
    canvas.roundRect(
        margem,
        resumo_y,
        largura - 2 * margem,
        resumo_altura,
        8,
        stroke=0,
        fill=1,
    )
    canvas.setFillColor(colors.HexColor("#5B315E"))
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(margem + 9 * mm, resumo_y + resumo_altura - 11 * mm, "Resumo geral")

    totais = (
        ("Chamados", total_chamados, "#25733D"),
        ("Ainda aguardando", total_faltam, "#A06400"),
        ("Inscritos nas filas", total_inscritos, "#5B315E"),
    )
    for indice, (rotulo, valor, cor) in enumerate(totais):
        centro_x = margem + (largura - 2 * margem) * ((indice + 0.5) / 3)
        canvas.setFillColor(colors.HexColor(cor))
        canvas.setFont("Helvetica-Bold", 22)
        canvas.drawCentredString(centro_x, resumo_y + 17 * mm, str(valor))
        canvas.setFont("Helvetica", 9)
        canvas.drawCentredString(centro_x, resumo_y + 10 * mm, rotulo)

    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        margem,
        13 * mm,
        f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
    )
    canvas.drawRightString(largura - margem, 13 * mm, "Página 1 de 1")

    canvas.showPage()
    canvas.save()
    return str(destino)
