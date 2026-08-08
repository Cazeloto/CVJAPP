"""Plotly chart factory functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from analytics.exceptions import ChartGenerationError
from analytics.models import ChartResult
from analytics.utils import ensure_directory, require_dependency, safe_filename


def _px() -> Any:
    require_dependency("plotly", "plotly")
    import plotly.express as px

    return px


def _go() -> Any:
    require_dependency("plotly", "plotly")
    import plotly.graph_objects as go

    return go


class ChartFactory:
    """Factory for reusable Plotly charts."""

    def __init__(self, template: str = "plotly_white") -> None:
        """Create a chart factory using a Plotly template."""

        self.template = template

    def bar(self, df: Any, x: str, y: str, title: str = "") -> ChartResult:
        """Create a bar chart."""

        px = _px()
        fig = px.bar(df, x=x, y=y, title=title, template=self.template)
        return ChartResult(name="bar", figure=fig)

    def line(self, df: Any, x: str, y: str, title: str = "") -> ChartResult:
        """Create a line chart."""

        px = _px()
        fig = px.line(df, x=x, y=y, title=title, template=self.template)
        return ChartResult(name="line", figure=fig)

    def pie(self, df: Any, names: str, values: str, title: str = "") -> ChartResult:
        """Create a pie chart."""

        px = _px()
        fig = px.pie(df, names=names, values=values, title=title, template=self.template)
        return ChartResult(name="pie", figure=fig)

    def donut(self, df: Any, names: str, values: str, title: str = "") -> ChartResult:
        """Create a donut chart."""

        result = self.pie(df, names=names, values=values, title=title)
        result.figure.update_traces(hole=0.45)
        return ChartResult(name="donut", figure=result.figure)

    def heatmap(self, df: Any, x: str, y: str, z: str, title: str = "") -> ChartResult:
        """Create a heatmap chart."""

        px = _px()
        fig = px.density_heatmap(df, x=x, y=y, z=z, title=title, template=self.template)
        return ChartResult(name="heatmap", figure=fig)

    def treemap(self, df: Any, path: list[str], values: str, title: str = "") -> ChartResult:
        """Create a treemap chart."""

        px = _px()
        fig = px.treemap(df, path=path, values=values, title=title)
        fig.update_layout(template=self.template)
        return ChartResult(name="treemap", figure=fig)

    def sunburst(self, df: Any, path: list[str], values: str, title: str = "") -> ChartResult:
        """Create a sunburst chart."""

        px = _px()
        fig = px.sunburst(df, path=path, values=values, title=title)
        fig.update_layout(template=self.template)
        return ChartResult(name="sunburst", figure=fig)

    def gauge(
        self,
        value: int | float,
        title: str = "",
        minimum: int | float = 0,
        maximum: int | float = 100,
    ) -> ChartResult:
        """Create a gauge indicator chart."""

        go = _go()
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=value,
                title={"text": title},
                gauge={"axis": {"range": [minimum, maximum]}},
            )
        )
        fig.update_layout(template=self.template)
        return ChartResult(name="gauge", figure=fig)

    def histogram(self, df: Any, x: str, title: str = "") -> ChartResult:
        """Create a histogram chart."""

        px = _px()
        fig = px.histogram(df, x=x, title=title, template=self.template)
        return ChartResult(name="histogram", figure=fig)

    def scatter(self, df: Any, x: str, y: str, title: str = "", color: str | None = None) -> ChartResult:
        """Create a scatter chart."""

        px = _px()
        fig = px.scatter(df, x=x, y=y, color=color, title=title, template=self.template)
        return ChartResult(name="scatter", figure=fig)

    def timeline(self, df: Any, x_start: str, x_end: str, y: str, title: str = "") -> ChartResult:
        """Create a timeline chart."""

        px = _px()
        fig = px.timeline(df, x_start=x_start, x_end=x_end, y=y, title=title, template=self.template)
        return ChartResult(name="timeline", figure=fig)


def figure_to_html(figure: Any, include_plotlyjs: str | bool = "cdn") -> str:
    """Serialize a Plotly figure to embeddable HTML."""

    try:
        return figure.to_html(include_plotlyjs=include_plotlyjs, full_html=False)
    except Exception as exc:
        raise ChartGenerationError(str(exc)) from exc


def export_figure(figure: Any, path: str | Path, fmt: str | None = None) -> Path:
    """Export a Plotly figure to HTML, PNG, or SVG.

    PNG and SVG require the optional ``kaleido`` package.
    """

    target = Path(path)
    ensure_directory(target.parent)
    output_format = (fmt or target.suffix.lstrip(".")).lower()
    if not output_format:
        output_format = "html"
        target = target.with_suffix(".html")
    if output_format == "html":
        target.write_text(figure_to_html(figure), encoding="utf-8")
        return target
    if output_format in {"png", "svg"}:
        require_dependency("kaleido", "kaleido")
        figure.write_image(str(target), format=output_format)
        return target
    raise ChartGenerationError(f"Formato de gráfico não suportado: {output_format}")


def default_chart_path(output_dir: str | Path, title: str, fmt: str = "html") -> Path:
    """Build a safe chart output path."""

    return Path(output_dir) / f"{safe_filename(title, 'grafico')}.{fmt.lstrip('.')}"
