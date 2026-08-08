from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


# ============================================================
# CARREGA .ENV
# ============================================================

load_dotenv()  # <-- automaticamente lê o .env da pasta


# ============================================================
# CONFIG
# ============================================================


@dataclass
class Config:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    tabela: str = "tratamento"

    pk_col: str = "tra_codigo"
    pac_col: str = "tra_codpac"
    chave_col: str = "tra_chave"
    data_col: str = "tra_data"
    status_col: str = "tra_status"
    status_ativo: str = "A"

    dry_run: bool = False


def carregar_config() -> Config:
    return Config(
        host=os.getenv("PG_HOST"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        tabela=os.getenv("TRA_TABELA", "tratamento"),
        pk_col=os.getenv("TRA_PK_COL", "tra_codigo"),
        pac_col=os.getenv("TRA_PAC_COL", "tra_codpac"),
        chave_col=os.getenv("TRA_CHAVE_COL", "tra_chave"),
        data_col=os.getenv("TRA_DATA_COL", "tra_data"),
        status_col=os.getenv("TRA_STATUS_COL", "tra_status"),
        status_ativo=os.getenv("TRA_STATUS_ATIVO", "A"),
        dry_run=os.getenv("DRY_RUN", "0").strip() == "1",
    )


# ============================================================
# HELPERS
# ============================================================


def qident(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def validar_env(cfg: Config):
    if not all([cfg.host, cfg.dbname, cfg.user]):
        raise RuntimeError("Variáveis PG_* não carregadas do .env corretamente.")


def existe_coluna(conn, tabela, coluna):
    sql = """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (tabela, coluna))
        return cur.fetchone() is not None


# ============================================================
# LÓGICA PRINCIPAL
# ============================================================


def buscar_grupos(conn, cfg):
    tbl = qident(cfg.tabela)
    sql = f"""
        SELECT {cfg.pac_col}, {cfg.chave_col}, COUNT(*)
        FROM {tbl}
        WHERE {cfg.status_col} = %s
        GROUP BY {cfg.pac_col}, {cfg.chave_col}
        HAVING COUNT(*) > 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (cfg.status_ativo,))
        return cur.fetchall()


def buscar_registros(conn, cfg, codpac, chave):
    tbl = qident(cfg.tabela)

    sql = f"""
        SELECT {cfg.pk_col}, {cfg.data_col}
        FROM {tbl}
        WHERE {cfg.status_col} = %s
          AND {cfg.pac_col} = %s
          AND {cfg.chave_col} = %s
        ORDER BY
            CASE WHEN {cfg.data_col} IS NOT NULL THEN 0 ELSE 1 END,
            {cfg.data_col} DESC NULLS LAST,
            {cfg.pk_col} DESC
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (cfg.status_ativo, codpac, chave))
        return cur.fetchall()


def limpar_duplicados(conn, cfg):
    grupos = buscar_grupos(conn, cfg)

    total_excluidos = 0
    detalhes = []

    for codpac, chave, qtd in grupos:
        registros = buscar_registros(conn, cfg, codpac, chave)
        if not registros:
            continue

        manter = registros[0][cfg.pk_col]
        excluir = [r[cfg.pk_col] for r in registros[1:]]

        detalhes.append(
            {
                "codpac": codpac,
                "chave": chave,
                "qtd": int(qtd),
                "manter": manter,
                "excluir": list(excluir),
            }
        )

        if excluir and not cfg.dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {cfg.tabela} WHERE {cfg.pk_col} = ANY(%s)",
                    (excluir,),
                )
                total_excluidos += cur.rowcount
        else:
            total_excluidos += len(excluir)

    return total_excluidos, detalhes


def renumerar(conn, cfg):
    tbl = qident(cfg.tabela)
    pk = qident(cfg.pk_col)
    seq = f"{cfg.tabela}_{cfg.pk_col}_seq"

    print("\nRenumerando PK...")

    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {tbl} ALTER COLUMN {pk} DROP DEFAULT")
        cur.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq}")

        cur.execute(
            f"""
            CREATE TEMP TABLE tmp AS
            SELECT ctids, ROW_NUMBER() OVER (ORDER BY {pk}) AS novo
            FROM {tbl}
        """
        )

        cur.execute(
            f"""
            UPDATE {tbl} t
            SET {pk} = x.novo
            FROM tmp x
            WHERE t.ctids = x.ctids
        """
        )

        cur.execute(
            f"""
            ALTER TABLE {tbl}
            ALTER COLUMN {pk}
            SET DEFAULT nextval('{seq}')
        """
        )

        cur.execute(f"SELECT MAX({pk}) FROM {tbl}")
        max_id = cur.fetchone()[0] or 0

        cur.execute("SELECT setval(%s, %s, true)", (seq, max_id))



# ============================================================
# API REUTILIZÁVEL P/ UI
# ============================================================


def executar_ajustes(dry_run: Optional[bool] = None) -> Dict[str, Any]:
    cfg = carregar_config()
    if dry_run is not None:
        cfg.dry_run = bool(dry_run)

    validar_env(cfg)

    with psycopg.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.dbname,
        user=cfg.user,
        password=cfg.password,
        autocommit=False,
    ) as conn:
        total_excluidos, detalhes = limpar_duplicados(conn, cfg)

        if cfg.dry_run:
            conn.rollback()
            mensagem = (
                f"Simulação concluída. Grupos afetados: {len(detalhes)} | "
                f"Registros a excluir: {total_excluidos}"
            )
        else:
            conn.commit()
            mensagem = (
                f"Acertos concluídos. Grupos afetados: {len(detalhes)} | "
                f"Registros excluídos: {total_excluidos}"
            )

        return {
            "ok": True,
            "dry_run": cfg.dry_run,
            "total_excluidos": int(total_excluidos),
            "grupos_afetados": int(len(detalhes)),
            "detalhes": detalhes,
            "mensagem": mensagem,
        }



# ============================================================
# MAIN
# ============================================================


def main():
    cfg = carregar_config()
    validar_env(cfg)

    print("Conectando no banco:", cfg.dbname)
    resultado = executar_ajustes(dry_run=cfg.dry_run)

    print(resultado["mensagem"])
    for item in resultado["detalhes"]:
        print(
            f"Paciente={item['codpac']} | Chave={item['chave']} | "
            f"Manter={item['manter']} | Excluir={item['excluir']}"
        )


if __name__ == "__main__":
    main()
