from core.fila_rules import contar_tratamentos_indicados, tipo_fila_indicada


def test_um_passe_prescrito_vai_para_triagem():
    tratamentos = [{"tra_codtra": 1, "tra_status": "A", "tra_descricao": "Passe01"}]

    assert contar_tratamentos_indicados([1, 0, 0, 0, 0], tratamentos) == 1
    assert tipo_fila_indicada([1, 0, 0, 0, 0], tratamentos) == "triagem"


def test_passe_base_zerado_continua_sendo_triagem():
    tratamentos = [{"tra_codtra": 1, "tra_status": "A", "tra_descricao": "Passe01"}]

    assert contar_tratamentos_indicados([0, 0, 0, 0, 0], tratamentos) == 1
    assert tipo_fila_indicada([0, 0, 0, 0, 0], tratamentos) == "triagem"


def test_mais_de_um_tratamento_vai_para_retorno():
    tratamentos = [
        {"tra_codtra": 1, "tra_status": "A", "tra_descricao": "Passe01"},
        {"tra_codtra": 2, "tra_status": "A", "tra_descricao": "Cromo01"},
    ]

    assert contar_tratamentos_indicados([1, 1, 0, 0, 0], tratamentos) == 2
    assert tipo_fila_indicada([1, 1, 0, 0, 0], tratamentos) == "retorno"


def test_triagem_e_tratamento_inativo_nao_entram_na_contagem():
    tratamentos = [
        {"tra_codtra": 9, "tra_status": "A", "tra_descricao": "Triagem"},
        {"tra_codtra": 2, "tra_status": "F", "tra_descricao": "Cromo01"},
    ]

    assert contar_tratamentos_indicados([1, 0, 0, 0, 0], tratamentos) == 1
    assert tipo_fila_indicada([1, 0, 0, 0, 0], tratamentos) == "triagem"
