from __future__ import annotations
from datetime import date, datetime
import threading
import unicodedata
from core.base_status import BaseUpdateStatus
from db.conn import get_conn


# ----------------- HELPERS -----------------
def _normalizar_nome_consulente(nome: str) -> str:
    nome = " ".join((nome or "").strip().split())
    nome = unicodedata.normalize("NFD", nome)
    nome = "".join(ch for ch in nome if unicodedata.category(ch) != "Mn")
    return nome.upper()


def _existe_nome_normalizado(cur, nome_norm: str, ignorar_codigo: int | None = None) -> bool:
    cur.execute("SELECT con_codigo, con_nome FROM consulente WHERE con_nome IS NOT NULL;")
    for row in cur.fetchall() or []:
        codigo = row["con_codigo"] if isinstance(row, dict) else row[0]
        nome = row["con_nome"] if isinstance(row, dict) else row[1]
        if ignorar_codigo is not None and int(codigo) == int(ignorar_codigo):
            continue
        if _normalizar_nome_consulente(nome) == nome_norm:
            return True
    return False


# ----------------- BUSCA E CONSULTA -----------------
def buscar_clientes(texto: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT con_codigo, con_nome FROM consulente WHERE UPPER(con_nome) LIKE %s ORDER BY con_nome LIMIT 50;",
                (f"%{texto.upper()}%",),
            )
            return cur.fetchall()


def buscar_cliente_por_id(cid: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM consulente WHERE con_codigo = %s;", (cid,))
            return cur.fetchone()


def obter_status_atualizacao_base() -> BaseUpdateStatus:
    """Verifica diagnostico e inicio do tratamento do ultimo consulente criado."""

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT con_diagnostico, con_datainicial
                  FROM consulente
                 ORDER BY con_codigo DESC
                 LIMIT 1;
                """
            )
            row = cur.fetchone()
    if not row:
        return BaseUpdateStatus(diagnosis_filled=False)
    return BaseUpdateStatus(
        diagnosis_filled=bool(str(row.get("con_diagnostico") or "").strip()),
        treatment_start=row.get("con_datainicial"),
    )


def buscar_tratamentos_ativos(cid: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM tratamento WHERE tra_codpac = %s AND tra_status = 'A' ORDER BY tra_data DESC, tra_hora DESC;",
                (cid,),
            )
            return cur.fetchall()


# ----------------- CRIAÇÃO DE CONSULENTE -----------------


def inserir_consulente(nome: str, sexo: str, nascimento: date, preferencial: str = ""):
    nome_caps = _normalizar_nome_consulente(nome)
    sexo = (sexo or "").strip().upper()
    preferencial = (preferencial or "").strip().upper()

    if not nome_caps:
        raise ValueError("Informe o nome.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("BEGIN;")
                cur.execute("LOCK TABLE consulente IN EXCLUSIVE MODE;")

                if _existe_nome_normalizado(cur, nome_caps):
                    raise ValueError("Já existe um consulente com este nome.")

                cur.execute(
                    """
                    INSERT INTO consulente (
                        con_nome, con_sexo, con_nascim, con_preferencial,
                        con_status, con_passe, con_npasse, con_datainicial,
                        con_fonecel, con_email, con_endereco, con_numero, con_complemento,
                        con_bairro, con_cidade, con_cep, con_diagnostico, con_diagnant,
                        con_cromoterapia, con_massagem, con_cirurgia, con_ebo, con_desenv, con_pontos,
                        con_ncromo, con_nmass, con_ncirur, con_nponto
                    )
                    VALUES (
                        %s, %s, %s, %s, 'A', 1, 0, CURRENT_DATE,
                        ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ',
                        0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ) RETURNING con_codigo;
                    """,
                    (nome_caps, sexo, nascimento, preferencial),
                )

                # Recupera o ID gerado automaticamente pelo banco
                row = cur.fetchone()
                # Dependendo do cursor (Dict ou Tuple), pegamos o valor:
                new_id = row["con_codigo"] if isinstance(row, dict) else row[0]

                # Usa o novo ID para criar os registros base do tratamento.
                _inserir_tratamento_base(cur, new_id, "Triagem", 9)
                _inserir_tratamento_base(cur, new_id, "Passe01", 1, com_data=False)

                cur.execute("COMMIT;")
                return new_id
            except Exception as e:
                cur.execute("ROLLBACK;")
                print(f"Erro ao inserir consulente: {e}")
                raise e


# ----------------- GESTÃO DE TRATAMENTOS (P, C, M, Ci, Ponto) -----------------
def _inserir_tratamento_base(
    cur, con_codigo: int, descricao: str, codtra: int, com_data: bool = True
):
    # REMOVIDO: Não buscamos mais MAX(tra_codigo) - campo é SERIAL
    tra_chave = f"{con_codigo}{descricao}"
    cur.execute(
        """
        INSERT INTO tratamento (
            tra_codpac, tra_descricao, tra_codtra, tra_chave,
            tra_data, tra_hora, tra_status, tra_medium, tra_entidade
        )
        VALUES (
            %s, %s, %s, %s,
            CASE WHEN %s THEN CURRENT_DATE ELSE NULL END,
            CASE WHEN %s THEN LOCALTIME(0) ELSE NULL END,
            'A', ' ', ' '
        )
        RETURNING tra_codigo;
        """,
        (con_codigo, descricao, codtra, tra_chave, com_data, com_data),
    )
    # Retorna o ID gerado (opcional, se precisar usar depois)
    return cur.fetchone()["tra_codigo"]


def _registrar_uso_generico(
    con_codigo: int, campo_max: str, campo_atual: str, prefixo_desc: str, codtra: int
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN;")
            # Seleciona limites com trava para atualização
            cur.execute(
                f"SELECT {campo_max}, {campo_atual} FROM consulente WHERE con_codigo = %s FOR UPDATE;",
                (con_codigo,),
            )
            row = cur.fetchone()

            if not row:
                cur.execute("ROLLBACK;")
                return None

            # Acesso flexível (suporta dict ou tupla via nomes de colunas se configurado)
            max_v = int(row[campo_max] or 0)
            atual_v = int(row[campo_atual] or 0)

            if max_v <= atual_v:
                cur.execute("ROLLBACK;")
                return None  # Sem saldo

            novo_n = atual_v + 1
            cur.execute(
                f"UPDATE consulente SET {campo_atual} = %s WHERE con_codigo = %s;",
                (novo_n, con_codigo),
            )

            # --- AJUSTE NA DESCRIÇÃO E CHAVE ---
            # Removemos o espaço: "Cromo 01" vira "Cromo01"
            desc = f"{prefixo_desc}{novo_n:02d}"
            # tra_chave = tra_codpac + tra_descricao (ex: "123Cromo01")
            tra_chave = f"{con_codigo}{desc}"

            cur.execute(
                """
                SELECT tra_codigo
                FROM tratamento
                WHERE tra_codpac = %s
                  AND tra_codtra = %s
                  AND tra_status = 'A'
                  AND (tra_descricao = %s OR tra_chave = %s)
                  AND tra_data IS NULL
                ORDER BY tra_codigo
                FOR UPDATE
                LIMIT 1;
                """,
                (con_codigo, codtra, desc, tra_chave),
            )
            row_trat = cur.fetchone()

            if row_trat is None:
                cur.execute(
                    """
                    SELECT tra_codigo
                    FROM tratamento
                    WHERE tra_codpac = %s
                      AND tra_codtra = %s
                      AND tra_status = 'A'
                      AND tra_data IS NULL
                    ORDER BY tra_descricao, tra_codigo
                    FOR UPDATE
                    LIMIT 1;
                    """,
                    (con_codigo, codtra),
                )
                row_trat = cur.fetchone()

            if row_trat is None:
                cur.execute(
                    """
                    INSERT INTO tratamento (
                        tra_codpac, tra_descricao, tra_codtra, tra_chave,
                        tra_data, tra_hora, tra_status, tra_medium, tra_entidade
                    )
                    VALUES (%s, %s, %s, %s, CURRENT_DATE, LOCALTIME(0), 'A', ' ', ' ')
                    RETURNING tra_codigo;
                    """,
                    (con_codigo, desc, codtra, tra_chave),
                )
                row_trat = cur.fetchone()

            if row_trat is None:
                cur.execute("ROLLBACK;")
                raise ValueError(
                    f"Não encontrei tratamento previsto sem data para {prefixo_desc}."
                )

            tra_codigo = row_trat["tra_codigo"] if isinstance(row_trat, dict) else row_trat[0]
            cur.execute(
                """
                UPDATE tratamento
                SET tra_descricao = %s,
                    tra_chave = %s,
                    tra_data = CURRENT_DATE,
                    tra_hora = LOCALTIME(0),
                    tra_status = 'A'
                WHERE tra_codigo = %s;
                """,
                (desc, tra_chave, tra_codigo),
            )

            cur.execute("COMMIT;")
            return novo_n


# Passando os índices corretos para o SELECT interno da função genérica
def registrar_uso_passe(cid):
    return _registrar_uso_generico(cid, "con_passe", "con_npasse", "Passe", 1)


def registrar_uso_cromo(cid):
    return _registrar_uso_generico(cid, "con_cromoterapia", "con_ncromo", "Cromo", 2)


def registrar_uso_massagem(cid):
    return _registrar_uso_generico(cid, "con_massagem", "con_nmass", "Massa", 3)


def registrar_uso_cirurgia(cid):
    return _registrar_uso_generico(cid, "con_cirurgia", "con_ncirur", "Cirur", 4)


def registrar_uso_ponto(cid):
    # Ponto passa a ser tratado como os demais itens do plano.
    # Código do tratamento na tabela tratamento: tra_codtra = 5.
    return _registrar_uso_generico(cid, "con_pontos", "con_nponto", "Ponto", 5)


def registrar_retorno(c):
    return _registrar_em_tabela("retorno", c)


def registrar_retorno_pref(c):
    return _registrar_em_tabela("retornopref", c)


def registrar_triagem(c):
    return _registrar_em_tabela("triagem", c)


def registrar_triagem_pref(c):
    return _registrar_em_tabela("triagempref", c)


def _registrar_em_tabela(tabela: str, con_codigo: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN;")
            cur.execute(f"SELECT COALESCE(MAX(codigo),0)+1 AS next_id FROM {tabela};")
            nxt_c = cur.fetchone()["next_id"]
            cur.execute(
                f"SELECT COALESCE(MAX(numero),0)+1 AS next_num FROM {tabela} WHERE data = CURRENT_DATE;"
            )
            nxt_n = cur.fetchone()["next_num"]
            cur.execute(
                f"INSERT INTO {tabela} (codigo, codpac, data, hora, numero) VALUES (%s,%s,CURRENT_DATE,LOCALTIME(0),%s);",
                (nxt_c, con_codigo, nxt_n),
            )
            cur.execute("COMMIT;")
            return nxt_n


def remover_retorno(c):
    return _remover_hoje("retorno", c)


def remover_retorno_pref(c):
    return _remover_hoje("retornopref", c)


def remover_triagem(c):
    return _remover_hoje("triagem", c)


def remover_triagem_pref(c):
    return _remover_hoje("triagempref", c)


def _remover_hoje(tab, cid):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {tab} WHERE codpac = %s AND data = CURRENT_DATE;", (cid,)
            )


def _existe_hoje(tab, cid):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {tab} WHERE codpac = %s AND data = CURRENT_DATE;",
                (cid,),
            )
            return cur.fetchone() is not None


def existe_retorno_hoje(c):
    return _existe_hoje("retorno", c)


def existe_retorno_pref_hoje(c):
    return _existe_hoje("retornopref", c)


def existe_triagem_hoje(c):
    return _existe_hoje("triagem", c)


def existe_triagem_pref_hoje(c):
    return _existe_hoje("triagempref", c)


def obter_senha_hoje(cid):
    for tab, tipo in [
        ("retornopref", "Retorno Preferencial"),
        ("retorno", "Retorno "),
        ("triagempref", "Triagem Preferencial"),
        ("triagem", "Triagem"),
    ]:
        if _existe_hoje(tab, cid):
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT numero FROM {tab} WHERE codpac=%s AND data=CURRENT_DATE;",
                        (cid,),
                    )
                    return tipo, cur.fetchone()["numero"]
    return None, None


def obter_senhas_hoje(cid):
    """Retorna todas as filas e senhas associadas ao consulente na data atual."""
    filas = [
        ("retorno", "Retorno", "RT"),
        ("retornopref", "Retorno Preferencial", "RTP"),
        ("triagem", "Triagem", "T"),
        ("triagempref", "Triagem Preferencial", "TP"),
    ]
    resultado = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            for tabela, nome, prefixo in filas:
                cur.execute(
                    f"""
                    SELECT data, numero
                    FROM {tabela}
                    WHERE codpac = %s AND data = CURRENT_DATE
                    ORDER BY numero;
                    """,
                    (cid,),
                )
                for row in cur.fetchall() or []:
                    resultado.append(
                        {
                            "fila": nome,
                            "prefixo": prefixo,
                            "data": row["data"],
                            "numero": row["numero"],
                        }
                    )
    return resultado


def listar_chamada_retorno():
    return _listar_chamada("retorno")


def listar_chamada_retorno_pref():
    return _listar_chamada("retornopref")


def listar_chamada_triagem():
    return _listar_chamada("triagem")


def listar_chamada_triagem_pref():
    return _listar_chamada("triagempref")


def _listar_chamada(tab):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT r.numero, c.con_nome, c.con_codigo FROM {tab} r JOIN consulente c ON c.con_codigo = r.codpac WHERE r.data = CURRENT_DATE ORDER BY r.numero;"
            )
            return cur.fetchall()


# ----------------- MÓDULO DE CHAMADAS -----------------
_FILAS_CHAMADA = {
    "retorno": "retorno",
    "retornopref": "retornopref",
    "triagem": "triagem",
    "triagempref": "triagempref",
}
_modulo_chamadas_preparado = False
_modulo_chamadas_lock = threading.Lock()


def preparar_modulo_chamadas():
    """Cria o histórico persistente usado pelos celulares na chamada da gira."""
    global _modulo_chamadas_preparado
    if _modulo_chamadas_preparado:
        return

    with _modulo_chamadas_lock:
        if _modulo_chamadas_preparado:
            return
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chamada_concluida (
                        id BIGSERIAL PRIMARY KEY,
                        fila VARCHAR(20) NOT NULL,
                        fila_codigo BIGINT NOT NULL,
                        codpac BIGINT NOT NULL,
                        numero INTEGER NOT NULL,
                        nome TEXT NOT NULL,
                        data DATE NOT NULL DEFAULT CURRENT_DATE,
                        concluida_em TIMESTAMP NOT NULL DEFAULT LOCALTIMESTAMP
                    );
                    """
                )
                # Os códigos das filas legadas podem ser reutilizados depois
                # de uma exclusão; portanto, eles não são uma chave de negócio.
                cur.execute(
                    """
                    ALTER TABLE chamada_concluida
                    DROP CONSTRAINT IF EXISTS uq_chamada_concluida;
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chamada_concluida_data_fila
                    ON chamada_concluida (data, fila);
                    """
                )
            conn.commit()
        _modulo_chamadas_preparado = True


def _tabela_fila_chamada(fila: str) -> str:
    try:
        return _FILAS_CHAMADA[fila]
    except KeyError as ex:
        raise ValueError("Fila de chamada inválida.") from ex


def listar_painel_chamadas():
    """Retorna pendentes e totais concluídos das quatro filas do dia."""
    preparar_modulo_chamadas()
    resultado = {
        fila: {"pendentes": [], "concluidos": 0}
        for fila in _FILAS_CHAMADA
    }

    with get_conn() as conn:
        with conn.cursor() as cur:
            for fila, tabela in _FILAS_CHAMADA.items():
                cur.execute(
                    f"""
                    SELECT
                        r.codigo AS fila_codigo,
                        r.numero,
                        r.codpac,
                        c.con_nome
                    FROM {tabela} r
                    JOIN consulente c ON c.con_codigo = r.codpac
                    WHERE r.data = CURRENT_DATE
                    ORDER BY r.numero, r.codigo;
                    """
                )
                resultado[fila]["pendentes"] = cur.fetchall()

            cur.execute(
                """
                SELECT fila, COUNT(*) AS total
                FROM chamada_concluida
                WHERE data = CURRENT_DATE
                GROUP BY fila;
                """
            )
            for row in cur.fetchall() or []:
                fila = row["fila"]
                if fila in resultado:
                    resultado[fila]["concluidos"] = int(row["total"] or 0)

    return resultado


def concluir_chamada(fila: str, fila_codigo: int) -> bool:
    """Registra a conclusão e retira exatamente um item da fila, atomicamente."""
    tabela = _tabela_fila_chamada(fila)
    preparar_modulo_chamadas()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT r.codigo, r.numero, r.codpac, c.con_nome
                FROM {tabela} r
                JOIN consulente c ON c.con_codigo = r.codpac
                WHERE r.codigo = %s AND r.data = CURRENT_DATE
                FOR UPDATE OF r;
                """,
                (fila_codigo,),
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return False

            cur.execute(
                """
                INSERT INTO chamada_concluida
                    (fila, fila_codigo, codpac, numero, nome, data)
                VALUES (%s, %s, %s, %s, %s, CURRENT_DATE);
                """,
                (
                    fila,
                    row["codigo"],
                    row["codpac"],
                    row["numero"],
                    row["con_nome"],
                ),
            )
            cur.execute(
                f"DELETE FROM {tabela} WHERE codigo = %s AND data = CURRENT_DATE;",
                (fila_codigo,),
            )
        conn.commit()
    return True


def apagar_chamada(fila: str, fila_codigo: int) -> bool:
    """Remove um item pendente sem contabilizá-lo como chamado."""
    tabela = _tabela_fila_chamada(fila)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                DELETE FROM {tabela}
                WHERE codigo = %s AND data = CURRENT_DATE;
                """,
                (fila_codigo,),
            )
            apagados = cur.rowcount
        conn.commit()
    return bool(apagados)


# ----------------- ATUALIZAÇÃO DE CONSULENTE -----------------
def atualizar_consulente(cid: int, dados: dict) -> bool:
    """
    Atualiza os dados de um consulente no banco.

    Args:
        cid: ID do consulente
        dados: Dicionário com os campos a atualizar

    Returns:
        True se atualizado com sucesso, False caso contrário
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                # Construir a query dinamicamente
                campos = []
                valores = []
                nome_para_validar = None

                # Mapear nomes dos campos do formulário para nomes das colunas no banco
                mapeamento = {
                    "con_nome": "con_nome",
                    "con_sexo": "con_sexo",
                    "con_nascim": "con_nascim",
                    "con_preferencial": "con_preferencial",
                    "con_fonecel": "con_fonecel",
                    "con_email": "con_email",
                    "con_cep": "con_cep",
                    "con_endereco": "con_endereco",
                    "con_numero": "con_numero",
                    "con_complemento": "con_complemento",
                    "con_bairro": "con_bairro",
                    "con_cidade": "con_cidade",
                    "con_diagnostico": "con_diagnostico",
                    "con_diagnant": "con_diagnant",
                    "con_ebo": "con_ebo",
                    "con_pontos": "con_pontos",
                    "con_desenv": "con_desenv",
                    "con_passe": "con_passe",
                    "con_cromoterapia": "con_cromoterapia",
                    "con_massagem": "con_massagem",
                    "con_cirurgia": "con_cirurgia",
                    "con_nponto": "con_nponto",
                }

                for campo_form, campo_db in mapeamento.items():
                    if campo_form in dados:
                        valor = dados[campo_form]
                        if campo_db == "con_nome":
                            valor = _normalizar_nome_consulente(valor)
                            if not valor:
                                raise ValueError("Informe o nome.")
                            nome_para_validar = valor

                        # Converter campos numéricos
                        if campo_db in [
                            "con_passe",
                            "con_cromoterapia",
                            "con_massagem",
                            "con_cirurgia",
                            "con_pontos",
                            "con_nponto",
                        ]:
                            try:
                                # Tratar valores vazios ou None
                                if valor in ["", None]:
                                    valor = 0
                                elif isinstance(valor, str):
                                    # Remover espaços e converter
                                    valor_limpo = valor.strip()
                                    if valor_limpo == "":
                                        valor = 0
                                    else:
                                        # Tentar converter para int
                                        try:
                                            valor = int(float(valor_limpo))
                                        except ValueError:
                                            valor = int(valor_limpo)
                                else:
                                    valor = int(valor)
                            except (ValueError, TypeError) as ve:
                                print(
                                    f"DEBUG: Erro ao converter {campo_db}: {valor} - {ve}"
                                )
                                valor = 0

                        # Para campos de data (con_nascim)
                        elif campo_db == "con_nascim" and isinstance(valor, str):
                            try:
                                valor = datetime.strptime(valor, "%d/%m/%Y").date()
                            except ValueError:
                                try:
                                    valor = datetime.strptime(valor, "%Y-%m-%d").date()
                                except ValueError:
                                    pass

                        # Para campos de texto, garantir que são strings
                        elif isinstance(valor, (int, float)) and campo_db not in [
                            "con_passe",
                            "con_cromoterapia",
                            "con_massagem",
                            "con_cirurgia",
                            "con_pontos",
                            "con_nponto",
                        ]:
                            valor = str(valor)

                        campos.append(f"{campo_db} = %s")
                        valores.append(valor)

                if not campos:
                    print("DEBUG: Nenhum campo para atualizar")
                    return False

                if nome_para_validar:
                    cur.execute("LOCK TABLE consulente IN EXCLUSIVE MODE;")
                    if _existe_nome_normalizado(cur, nome_para_validar, ignorar_codigo=cid):
                        raise ValueError("Já existe um consulente com este nome.")

                # Adicionar o ID no final
                valores.append(cid)

                query = f"""
                    UPDATE consulente
                    SET {', '.join(campos)}
                    WHERE con_codigo = %s
                """

                print(f"DEBUG: Query: {query}")
                print(f"DEBUG: Valores: {valores}")

                cur.execute(query, tuple(valores))
                conn.commit()

                print(f"DEBUG: Consulente {cid} atualizado com sucesso")
                return True

            except Exception as e:
                conn.rollback()
                print(f"Erro ao atualizar consulente {cid}: {e}")
                import traceback

                traceback.print_exc()
                return False


def atualizar_preferencial_consulente(cid: int, preferencial: bool) -> bool:
    valor = "X" if preferencial else ""
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    UPDATE consulente
                    SET con_preferencial = %s
                    WHERE con_codigo = %s
                    """,
                    (valor, cid),
                )
                conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                conn.rollback()
                print(f"Erro ao atualizar preferencial do consulente {cid}: {e}")
                return False


# ----------------- AÇÕES EM LOTE (DETAILS) -----------------
def atualizar_status_tratamentos(con_codigo: int, status_destino: str, status_origem: str = "A") -> int:
    """Atualiza em lote o status dos tratamentos de um consulente.

    Ex.: desistiu -> A para D; finalizar -> A para F.

    Returns:
        Quantidade de linhas atualizadas.
    """
    status_destino = (status_destino or "").strip().upper()
    status_origem = (status_origem or "").strip().upper()
    if not status_destino or not status_origem:
        return 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tratamento SET tra_status = %s WHERE tra_codpac = %s AND tra_status = %s;",
                (status_destino, con_codigo, status_origem),
            )
            try:
                conn.commit()
            except Exception:
                pass
            return int(getattr(cur, "rowcount", 0) or 0)


def existe_tratamento_status(con_codigo: int, status: str = "A") -> bool:
    """Retorna True se existir pelo menos 1 tratamento com o status informado."""
    status = (status or "").strip().upper()
    if not status:
        return False
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM tratamento WHERE tra_codpac = %s AND tra_status = %s LIMIT 1;",
                (con_codigo, status),
            )
            return cur.fetchone() is not None


def reiniciar_tratamento(con_codigo: int) -> str:
    """Reinicia o tratamento do consulente.

    Regras:
    - Se existir algum tratamento com status 'A', retorna 'tratamento em Aberto' (sem alterar nada).
    - Caso não exista, cria 2 registros em tratamento: 'Triagem' (codtra=9), com data atual,
      e 'Passe01' (codtra=1), previsto sem data para ser atrelado ao uso do passe.
    - Atualiza a tabela consulente:
        * copia con_diagnostico -> con_diagnant
        * con_datainicial = CURRENT_DATE
        * con_passe = 1
        * zera contadores/quantidades numéricas (cromo/massa/cirurg e executados)

    Returns:
        'ok' ou 'tratamento em Aberto'
    """
    if existe_tratamento_status(con_codigo, "A"):
        return "tratamento em Aberto"

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("BEGIN;")

                # Atualiza consulente (ajusta plano e zera contadores)
                cur.execute(
                    """
                    UPDATE consulente
                    SET
                        con_diagnant = COALESCE(con_diagnostico, con_diagnant),
                        con_diagnostico = '',
                        con_datainicial = CURRENT_DATE,
                        con_passe = 1,
                        con_npasse = 0,
                        con_cromoterapia = 0,
                        con_ncromo = 0,
                        con_massagem = 0,
                        con_nmass = 0,
                        con_cirurgia = 0,
                        con_ncirur = 0,
                        con_desenv = 0,
                        con_pontos = 0,
                        con_nponto = 0
                    WHERE con_codigo = %s;
                    """,
                    (con_codigo,),
                )

                # Cria novos tratamentos base
                _inserir_tratamento_base(cur, con_codigo, "Triagem", 9)
                _inserir_tratamento_base(cur, con_codigo, "Passe01", 1, com_data=False)

                cur.execute("COMMIT;")
                return "ok"
            except Exception as e:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                print(f"Erro ao reiniciar tratamento: {e}")
                raise e
