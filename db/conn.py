"""Conexao PostgreSQL compartilhada pela aplicacao."""

import psycopg
from psycopg.rows import dict_row

from core.config import Settings, settings


def get_conn(config: Settings = settings):
    """Abre uma conexao transacional e retorna linhas como dicionarios."""

    kwargs = config.connection_kwargs()
    conninfo = kwargs.pop("conninfo", "")
    return psycopg.connect(
        conninfo,
        **kwargs,
        connect_timeout=10,
        row_factory=dict_row,
        autocommit=False,
    )
