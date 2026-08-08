from __future__ import annotations

from collections.abc import Iterable, Mapping


CODIGOS_TRATAMENTO = {1, 2, 3, 4, 5}


def _inteiro_nao_negativo(valor) -> int:
    try:
        return max(0, int(valor or 0))
    except (TypeError, ValueError):
        return 0


def contar_tratamentos_indicados(
    quantidades_prescritas: Iterable[object],
    tratamentos: Iterable[Mapping[str, object]] | None = None,
) -> int:
    """Conta indicações, preservando o passe-base mesmo com contador zerado.

    Os contadores do cadastro são a fonte principal. Os registros ativos da
    tabela de tratamento servem de garantia para cadastros legados, como o
    passe-base exibido como 0/0.
    """
    total_prescrito = sum(
        _inteiro_nao_negativo(valor) for valor in quantidades_prescritas
    )
    total_registros = 0

    for tratamento in tratamentos or []:
        if str(tratamento.get("tra_status", "A")).strip().upper() != "A":
            continue
        codigo = _inteiro_nao_negativo(tratamento.get("tra_codtra"))
        if codigo in CODIGOS_TRATAMENTO:
            total_registros += 1

    return max(total_prescrito, total_registros)


def tipo_fila_indicada(
    quantidades_prescritas: Iterable[object],
    tratamentos: Iterable[Mapping[str, object]] | None = None,
) -> str:
    """Retorna ``triagem`` para até uma indicação e ``retorno`` para mais de uma."""
    quantidade = contar_tratamentos_indicados(quantidades_prescritas, tratamentos)
    return "retorno" if quantidade > 1 else "triagem"
