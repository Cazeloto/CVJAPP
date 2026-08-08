MAP_TIPO = {1: "PASSE", 2: "CROMO", 3: "MASSA", 4: "CIRURG", 5: "PONTO"}


def fmt_data_br(valor) -> str:
    """YYYY-MM-DD -> DD/MM/YYYY"""
    if not valor:
        return ""
    s = str(valor)
    if len(s) >= 10 and s[4] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s


def trunc_1linha(txt, n=8) -> str:
    """1 linha, remove espaços extras, corta em n e adiciona '…'"""
    txt = "" if txt is None else str(txt)
    txt = " ".join(txt.split())
    if len(txt) <= n:
        return txt
    return txt[: n - 1] + "…"


def to_int(v) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def preparar_grade(tratamentos: list[dict]) -> tuple[int, dict]:
    """Retorna (quantidade de linhas, tratamentos por categoria), mais novos primeiro."""
    por_cat = {"PASSE": [], "CROMO": [], "MASSA": [], "CIRURG": [], "PONTO": []}

    for t in tratamentos or []:
        cat = MAP_TIPO.get(t.get("tra_codtra"))
        if cat:
            por_cat[cat].append(t)

    def key_dt(t):
        return (str(t.get("tra_data") or ""), str(t.get("tra_hora") or ""))

    for cat in por_cat:
        por_cat[cat].sort(key=key_dt, reverse=True)

    max_linhas = max([len(por_cat[c]) for c in por_cat] + [0])
    return max_linhas, por_cat


def extrair_triagem(tratamentos: list[dict]):
    """
    Retorna o registro do tratamento de TRIAGEM (ativo), ou None.
    - Não pega o primeiro tratamento.
    - Procura pelo item cuja descrição contenha 'TRIAGEM' (case-insensitive).
    - Se houver mais de um, pega o mais recente por data/hora.
    """
    if not tratamentos:
        return None

    # garante apenas ativos (caso algum lugar ainda traga tudo)
    ativos = [t for t in tratamentos if str(t.get("tra_status", "A")).upper() == "A"]

    # identifica triagem pela descrição
    candidatos = []
    for t in ativos:
        desc = t.get("tra_descricao") or ""
        if "TRIAG" in desc.upper():  # pega TRIAGEM / TRIAGEMPREF / variações
            candidatos.append(t)

    if not candidatos:
        return None

    def key_dt(t):
        # trata data/hora como strings ou objetos
        d = t.get("tra_data")
        h = t.get("tra_hora")
        return (d or "", h or "")

    # pega o mais recente
    candidatos.sort(key=key_dt, reverse=True)
    return candidatos[0]
