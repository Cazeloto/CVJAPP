# Analytics Framework

Framework reutilizável de Business Intelligence para aplicações Python com PostgreSQL.

## Objetivo

Este pacote fornece uma camada de BI desacoplada da aplicação principal. Ele conecta ao
PostgreSQL, executa SQL puro por meio de SQLAlchemy, transforma dados com Pandas, calcula
indicadores, gera gráficos Plotly e exporta relatórios para Excel e PDF.

## Arquitetura

```text
PostgreSQL
  -> analytics.database
  -> analytics.queries
  -> analytics.dataframe
  -> analytics.indicadores
  -> analytics.charts / exports_excel / exports_pdf
  -> Flet ou outra aplicação Python
```

## Decisões

- `database.py` apenas cria e gerencia conexão.
- `queries.py` executa SQL puro, inclusive Views e Materialized Views.
- `indicadores.py` calcula KPIs genéricos sem conhecer regras da aplicação.
- `charts.py` recebe dados prontos e devolve figuras Plotly.
- `exports_excel.py` e `exports_pdf.py` geram arquivos profissionais.
- `cache.py` oferece cache em memória com TTL para indicadores e consultas caras.
- Nenhuma consulta SQL deve ficar dentro da interface gráfica.

## Dependências

Instale as dependências do BI:

```bash
pip install pandas plotly SQLAlchemy openpyxl kaleido reportlab
```

`kaleido` é necessário para exportar gráficos Plotly em PNG e SVG.

## Uso básico

```python
from analytics.config import DatabaseConfig
from analytics.database import DatabaseManager
from analytics.queries import QueryExecutor
from analytics.indicadores import total_records, active_records
from analytics.charts import ChartFactory

db = DatabaseManager(
    DatabaseConfig(url="postgresql+psycopg://usuario:senha@localhost:5432/banco")
)
executor = QueryExecutor(db)

df = executor.fetch_dataframe(
    """
    SELECT status, data_atendimento, categoria
    FROM vw_atendimentos
    WHERE data_atendimento >= :inicio
    """,
    params={"inicio": "2026-01-01"},
)

kpi_total = total_records(df)
kpi_ativos = active_records(df, status_column="status", active_value="A")

chart = ChartFactory().bar(
    df=df.groupby("categoria").size().reset_index(name="total"),
    x="categoria",
    y="total",
    title="Atendimentos por categoria",
)
```

## Integração com Flet

O framework não depende de Flet. Para exibir um gráfico em uma aplicação Flet,
gere HTML a partir do Plotly:

```python
from analytics.charts import figure_to_html

html = figure_to_html(chart.figure)
```

A aplicação Flet pode decidir se renderiza esse HTML em um controle apropriado,
se exporta para imagem, ou se abre o relatório em PDF.

## Performance

Para milhões de registros:

- prefira Views e Materialized Views para agregações pesadas;
- use filtros de data no SQL antes de carregar dados;
- use `chunksize` em `QueryExecutor.fetch_dataframe`;
- use `cache.CacheManager` para KPIs reutilizados;
- carregue somente as colunas necessárias.

## Testes

```bash
python -m unittest discover -s tests -v
```

Alguns testes são pulados automaticamente quando dependências opcionais não estão instaladas.
