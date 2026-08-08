# ui/details.py
import flet as ft
from core.utils import (
    fmt_data_br,
    preparar_grade,
    to_int,
    extrair_triagem,
    trunc_1linha,
)


def border_all(width, color):
    side = ft.BorderSide(width=width, color=color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def border_bottom(width, color):
    return ft.Border(bottom=ft.BorderSide(width=width, color=color))


def padding_symmetric(vertical=0, horizontal=0):
    return ft.Padding(
        left=horizontal,
        top=vertical,
        right=horizontal,
        bottom=vertical,
    )


def padding_only(left=0, top=0, right=0, bottom=0):
    return ft.Padding(left=left, top=top, right=right, bottom=bottom)


def _row_get(row, key: str, default=""):
    if row is None:
        return default
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        return row[key]
    except Exception:
        return default


def _mediums_tratamento(row, trunc_n: int = 15) -> str:
    nomes = [
        str(_row_get(row, "tra_medium", "") or "").strip(),
        str(_row_get(row, "tra_medium2", "") or "").strip(),
        str(_row_get(row, "tra_medium3", "") or "").strip(),
    ]
    return "/".join(trunc_1linha(nome, n=trunc_n) for nome in nomes if nome)


def _linha_cat_com_mediums(por_cat: dict, cat: str, idx: int, trunc_n: int = 15):
    itens = por_cat.get(cat, []) or []
    if idx >= len(itens):
        return "", ""
    item = itens[idx]
    return fmt_data_br(_row_get(item, "tra_data")), _mediums_tratamento(item, trunc_n)


def montar_detalhes_modelo(
    dados: dict,
    tratamentos: list[dict],
    senhas_fila: list[dict] | None = None,
) -> ft.Control:
    # Extrair dados
    data_plano = fmt_data_br(dados.get("con_datainicial"))
    nome = dados.get("con_nome", "") or ""
    nasc = fmt_data_br(dados.get("con_nascim"))
    diag = (dados.get("con_diagnostico", "") or "").strip()
    prefer = (dados.get("con_preferencial", "") or "").strip().upper()

    # Contato
    celular = (dados.get("con_fonecel", "") or "").strip()
    email = (dados.get("con_email", "") or "").strip()
    endereco = (dados.get("con_endereco", "") or "").strip()
    numero = (dados.get("con_numero", "") or "").strip()
    bairro = (dados.get("con_bairro", "") or "").strip()
    cidade = (dados.get("con_cidade", "") or "").strip()
    cep = (dados.get("con_cep", "") or "").strip()

    # Dados médicos
    diag_ant = (dados.get("con_diagnant", "") or "").strip()

    # Triagem
    tri = extrair_triagem(tratamentos)
    if tri:
        tri_med = trunc_1linha(tri.get("tra_medium"), n=25)
        tri_ent = trunc_1linha(tri.get("tra_entidade"), n=25)
        tri_txt = f"{tri_med} / {tri_ent}".strip() or "-"
    else:
        tri_txt = "-"

    # Contadores de tratamentos
    q_passe = to_int(dados.get("con_passe"))
    q_cromo = to_int(dados.get("con_cromoterapia"))
    q_massa = to_int(dados.get("con_massagem"))
    q_cirurg = to_int(dados.get("con_cirurgia"))
    q_ponto = to_int(dados.get("con_pontos"))

    q_npasse = to_int(dados.get("con_npasse"))
    q_ncromo = to_int(dados.get("con_ncromo"))
    q_nmassa = to_int(dados.get("con_nmass"))
    q_ncirurg = to_int(dados.get("con_ncirur"))
    q_nponto = to_int(dados.get("con_nponto"))

    def calcular_percentual(atual, total):
        if total > 0:
            return (atual / total) * 100
        return 0

    p_passe = calcular_percentual(q_npasse, q_passe)
    p_cromo = calcular_percentual(q_ncromo, q_cromo)
    p_massa = calcular_percentual(q_nmassa, q_massa)
    p_cirurg = calcular_percentual(q_ncirurg, q_cirurg)
    p_ponto = calcular_percentual(q_nponto, q_ponto)

    # Mostra somente sessões realizadas que ainda pertencem ao plano ativo.
    historico = [
        t
        for t in (tratamentos or [])
        if str(_row_get(t, "tra_status", "A")).strip().upper() == "A"
        and _row_get(t, "tra_data")
        and to_int(_row_get(t, "tra_codtra")) in (1, 2, 3, 4, 5)
    ]

    # Grade de tratamentos
    linhas_fixas, por_cat = preparar_grade(historico)

    # Fallback local para PONTO enquanto core.utils/preparar_grade não for alterado.
    pontos_lista = []
    for t in historico or []:
        try:
            cod = int(t.get("tra_codtra") or 0) if isinstance(t, dict) else 0
        except Exception:
            cod = 0
        desc = (t.get("tra_descricao", "") if isinstance(t, dict) else "") or ""
        if cod == 5 or str(desc).upper().startswith("PONTO"):
            pontos_lista.append(t)
    linhas_fixas = max(linhas_fixas, len(pontos_lista))
    # Evita KeyError se core.utils.preparar_grade ainda não conhece a categoria PONTO.
    por_cat.setdefault("PONTO", pontos_lista)

    # Monta a tabela SOMENTE com linhas que tenham conteúdo (e no máximo 10)
    grade_tabela = None
    if linhas_fixas > 0:
        grade_controles = []

        cabecalho = ft.Container(
            padding=padding_symmetric(vertical=8, horizontal=8),
            bgcolor=ft.Colors.GREY_200,
            content=ft.Row(
                [
                    ft.Container(
                        width=105,
                        content=ft.Text(
                            "PASSE",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                    ft.Container(
                        width=105,
                        content=ft.Text(
                            "CROMO",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                    ft.Container(
                        width=105,
                        content=ft.Text(
                            "MASSA",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                    ft.Container(
                        width=105,
                        content=ft.Text(
                            "CIRURG",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                    ft.Container(
                        width=105,
                        content=ft.Text(
                            "PONTO",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                ]
            ),
        )
        grade_controles.append(cabecalho)

        # varre índices possíveis, mas limita ao que existe + 10 no máximo
        max_idx = min(linhas_fixas, 10)

        for i in range(max_idx):
            p_dt, p_md = _linha_cat_com_mediums(por_cat, "PASSE", i, trunc_n=15)
            c_dt, c_md = _linha_cat_com_mediums(por_cat, "CROMO", i, trunc_n=15)
            m_dt, m_md = _linha_cat_com_mediums(por_cat, "MASSA", i, trunc_n=15)
            s_dt, s_md = _linha_cat_com_mediums(por_cat, "CIRURG", i, trunc_n=15)
            pt_dt, pt_md = _linha_cat_com_mediums(por_cat, "PONTO", i, trunc_n=15)

            # Fallback: se core.utils ainda não categorizar tra_codtra=5, busca direto nos tratamentos.
            if not (pt_dt or pt_md) and i < len(pontos_lista):
                t = pontos_lista[i]
                pt_dt = fmt_data_br(t.get("tra_data")) if isinstance(t, dict) else ""
                pt_md = _mediums_tratamento(t, trunc_n=15)

            tem_algo = any(
                [
                    (p_dt or "").strip(),
                    (p_md or "").strip(),
                    (c_dt or "").strip(),
                    (c_md or "").strip(),
                    (m_dt or "").strip(),
                    (m_md or "").strip(),
                    (s_dt or "").strip(),
                    (s_md or "").strip(),
                    (pt_dt or "").strip(),
                    (pt_md or "").strip(),
                ]
            )
            if not tem_algo:
                continue

            linha = ft.Container(
                padding=padding_symmetric(vertical=6, horizontal=8),
                bgcolor=ft.Colors.WHITE if i % 2 == 0 else ft.Colors.GREY_50,
                border=border_bottom(0.5, ft.Colors.GREY_300),
                content=ft.Row(
                    [
                        ft.Container(
                            width=105,
                            content=ft.Column(
                                [
                                    ft.Text(p_dt or "", size=13, color=ft.Colors.BLACK),
                                    ft.Text(
                                        p_md or "", size=12, color=ft.Colors.BLUE_700
                                    ),
                                ],
                                spacing=2,
                            ),
                        ),
                        ft.Container(
                            width=105,
                            content=ft.Column(
                                [
                                    ft.Text(c_dt or "", size=13, color=ft.Colors.BLACK),
                                    ft.Text(
                                        c_md or "", size=12, color=ft.Colors.BLUE_700
                                    ),
                                ],
                                spacing=2,
                            ),
                        ),
                        ft.Container(
                            width=105,
                            content=ft.Column(
                                [
                                    ft.Text(m_dt or "", size=13, color=ft.Colors.BLACK),
                                    ft.Text(
                                        m_md or "", size=12, color=ft.Colors.BLUE_700
                                    ),
                                ],
                                spacing=2,
                            ),
                        ),
                        ft.Container(
                            width=105,
                            content=ft.Column(
                                [
                                    ft.Text(s_dt or "", size=13, color=ft.Colors.BLACK),
                                    ft.Text(
                                        s_md or "", size=12, color=ft.Colors.BLUE_700
                                    ),
                                ],
                                spacing=2,
                            ),
                        ),
                        ft.Container(
                            width=105,
                            content=ft.Column(
                                [
                                    ft.Text(pt_dt or "", size=13, color=ft.Colors.BLACK),
                                    ft.Text(
                                        pt_md or "", size=12, color=ft.Colors.BLUE_700
                                    ),
                                ],
                                spacing=2,
                            ),
                        ),
                    ]
                ),
            )
            grade_controles.append(linha)

        # Se ficou só o cabeçalho, não mostra nada
        if len(grade_controles) > 1:
            grade_tabela = ft.Container(
                border=border_all(1, ft.Colors.GREY_400),
                border_radius=8,
                content=ft.Column(grade_controles, spacing=0),
            )

    # Barra de progresso
    def criar_barra_progresso(label, atual, total, percentual):
        cor_barra = ft.Colors.GREEN if percentual < 100 else ft.Colors.BLUE
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(f"{label}:", size=11, weight=ft.FontWeight.BOLD),
                        ft.Text(f" {atual}/{total}", size=11),
                        ft.Text(
                            f" ({percentual:.0f}%)",
                            size=10,
                            color=ft.Colors.GREY_600,
                        ),
                    ]
                ),
                ft.ProgressBar(
                    value=percentual / 100,
                    width=200,
                    height=8,
                    color=cor_barra,
                    bgcolor=ft.Colors.GREY_300,
                ),
            ],
            spacing=2,
        )

    # Controles
    controles = [
        ft.Container(
            padding=10,
            bgcolor=ft.Colors.PURPLE_50,
            border_radius=10,
            content=ft.Column(
                [
                    ft.Text(
                        nome,
                        size=21,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.PURPLE_900,
                    ),
                    ft.Row(
                        [
                            ft.Text(f"Nasc: {nasc}", size=12),
                            ft.Text(
                                f" | Pref: {'SIM' if prefer else 'NÃO'}",
                                size=12,
                                color=(
                                    ft.Colors.GREEN_700
                                    if prefer
                                    else ft.Colors.GREY_600
                                ),
                            ),
                            ft.Text(f" | Plano: {data_plano}", size=12),
                        ],
                        wrap=True,
                    ),
                ]
            ),
        ),
        ft.Card(
            content=ft.Container(
                padding=10,
                content=ft.Column(
                    [
                        ft.Text(
                            "Diagnósticos",
                            size=17,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.PURPLE_900,
                        ),
                        ft.Divider(height=1),
                        ft.Text(
                            f"Atual: {diag or 'Não informado'}",
                            size=16,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.BLACK,
                        ),
                        ft.Divider(height=8, color=ft.Colors.GREY_300),
                        ft.Text(
                            f"Anterior: {diag_ant or 'Não informado'}",
                            size=16,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.BLACK,
                        ),
                    ],
                    spacing=5,
                ),
            )
        ),
        ft.Card(
            content=ft.Container(
                padding=10,
                content=ft.Column(
                    [
                        ft.Text("Triagem", size=16, weight=ft.FontWeight.BOLD),
                        ft.Divider(height=1),
                        ft.Text(tri_txt, size=14),
                    ]
                ),
            )
        ),
        ft.Card(
            content=ft.Container(
                padding=10,
                content=ft.Column(
                    [
                        ft.Text(
                            "Progresso dos Tratamentos",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Divider(height=1),
                        criar_barra_progresso("Passe", q_npasse, q_passe, p_passe),
                        criar_barra_progresso(
                            "Cromoterapia", q_ncromo, q_cromo, p_cromo
                        ),
                        criar_barra_progresso("Massagem", q_nmassa, q_massa, p_massa),
                        criar_barra_progresso(
                            "Cirurgia", q_ncirurg, q_cirurg, p_cirurg
                        ),
                        criar_barra_progresso("Ponto", q_nponto, q_ponto, p_ponto),
                    ],
                    spacing=8,
                ),
            )
        ),
    ]

    if senhas_fila:
        linhas_senha = []
        for item in senhas_fila:
            numero_senha = to_int(_row_get(item, "numero"))
            prefixo = str(_row_get(item, "prefixo", "") or "").strip()
            linhas_senha.append(
                ft.Text(
                    f"{_row_get(item, 'fila', 'Fila')} | "
                    f"Senha: {prefixo}-{numero_senha:03d}",
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.BLUE_800,
                )
            )
        controles.insert(
            1,
            ft.Card(
                content=ft.Container(
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Fila associada hoje",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Divider(height=1),
                            *linhas_senha,
                        ],
                        spacing=5,
                    ),
                )
            ),
        )

    # Card de tratamentos realizados (só se existir tabela real)
    if grade_tabela is not None:
        controles.append(
            ft.Card(
                content=ft.Container(
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Tratamentos Realizados (10 últimas sessões)",
                                size=14,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Divider(height=1),
                            ft.Text(
                                f"Total de tratamentos: {len(historico or [])}",
                                size=11,
                                color=ft.Colors.GREY_600,
                            ),
                            ft.Container(
                                padding=padding_only(top=10, bottom=10),
                                content=grade_tabela,
                            ),
                        ]
                    ),
                )
            )
        )

    return ft.Column(
        controles,
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
