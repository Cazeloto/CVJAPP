"""Professional PDF exports based on ReportLab."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from analytics.exceptions import ExportError
from analytics.models import ExportResult, KPIResult
from analytics.utils import ensure_directory, require_dependency


@dataclass(frozen=True)
class PDFReport:
    """Generic PDF report payload."""

    title: str
    subtitle: str = ""
    kpis: list[KPIResult] = field(default_factory=list)
    tables: dict[str, Any] = field(default_factory=dict)
    images: list[Path] = field(default_factory=list)


class PDFExporter:
    """Exports analytics reports to PDF."""

    def export(self, path: str | Path, report: PDFReport) -> ExportResult:
        """Write a formatted PDF report."""

        require_dependency("reportlab", "reportlab")
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        target = Path(path)
        ensure_directory(target.parent)
        styles = getSampleStyleSheet()
        story: list[Any] = []

        try:
            doc = SimpleDocTemplate(
                str(target),
                pagesize=A4,
                rightMargin=1.5 * cm,
                leftMargin=1.5 * cm,
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm,
                title=report.title,
            )
            story.append(Paragraph(report.title, styles["Title"]))
            if report.subtitle:
                story.append(Paragraph(report.subtitle, styles["Heading2"]))
            story.append(Paragraph(f"Emitido em {datetime.now():%d/%m/%Y %H:%M}", styles["Normal"]))
            story.append(Spacer(1, 0.4 * cm))

            if report.kpis:
                rows = [["Indicador", "Valor", "Unidade"]]
                rows.extend([[k.label or k.name, k.value, k.unit or ""] for k in report.kpis])
                table = Table(rows, hAlign="LEFT")
                table.setStyle(_table_style(colors))
                story.extend([Paragraph("Indicadores", styles["Heading2"]), table, Spacer(1, 0.4 * cm)])

            for title, data in report.tables.items():
                rows = _dataframe_to_rows(data)
                if not rows:
                    continue
                table = Table(rows, repeatRows=1)
                table.setStyle(_table_style(colors))
                story.extend([Paragraph(title, styles["Heading2"]), table, Spacer(1, 0.4 * cm)])

            for image_path in report.images:
                image = Path(image_path)
                if image.exists():
                    story.append(Image(str(image), width=16 * cm, height=9 * cm, kind="proportional"))
                    story.append(Spacer(1, 0.4 * cm))

            doc.build(story)
            return ExportResult(path=target, format="pdf")
        except Exception as exc:
            raise ExportError(str(exc)) from exc


def _table_style(colors: Any) -> Any:
    from reportlab.platypus import TableStyle

    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F1B5C")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F1F7")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )


def _dataframe_to_rows(data: Any, max_rows: int = 40) -> list[list[Any]]:
    if data is None:
        return []
    if hasattr(data, "head") and hasattr(data, "columns"):
        limited = data.head(max_rows)
        return [list(limited.columns)] + limited.astype(str).values.tolist()
    if isinstance(data, list) and data and isinstance(data[0], dict):
        columns = list(data[0].keys())
        return [columns] + [[row.get(column, "") for column in columns] for row in data[:max_rows]]
    return []
