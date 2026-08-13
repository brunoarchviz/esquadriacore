"""Primeira visualização real da Suprema de correr 2 folhas (E.4H).

Exerce o gate de visualização preliminar, ABERTO desde E.4D e nunca usado
para esta tipologia. Estes testes protegem exatamente a fronteira que a
rodada pediu: a cena usa SÓ topologia confirmada e geometria homologada;
nenhuma regra dimensional PENDENTE foi promovida, e os gates de cálculo e
produção continuam bloqueados como antes.
"""
from __future__ import annotations

from collections import Counter

import pytest

from composicao import fontes, receita as receita_mod, validar
from composicao.modelos import EstadoConhecimento
from composicao.visualizacao import montar_cena_suprema_2f

from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent

CODIGOS_ESPERADOS = Counter({
    "SU-001": 1, "SU-002": 1, "SU-003": 2, "SU-039": 2,
    "SU-040": 1, "SU-041": 1, "SU-053": 4, "SU-102": 8,
})


@pytest.fixture(scope="module")
def cena():
    return montar_cena_suprema_2f()


# ---------------------------------------------------------------------------
# A composição usa exatamente a topologia confirmada — nada a mais, nada a menos
# ---------------------------------------------------------------------------

def test_cena_tem_as_20_ocorrencias_da_topologia(cena):
    assert len(cena.instancias) == 20


def test_cena_usa_exatamente_os_oito_codigos_oficiais(cena):
    contagem = Counter(inst.perfil_id.removeprefix("ALCOA-")
                       for inst in cena.instancias)
    assert contagem == CODIGOS_ESPERADOS


def test_cada_instancia_referencia_perfil_oficial_alcoa(cena):
    for inst in cena.instancias:
        assert inst.perfil_id.startswith("ALCOA-SU-")


def test_ids_de_instancia_sao_unicos(cena):
    ids = [inst.instancia_id for inst in cena.instancias]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Nenhuma dimensão de fabricação foi inventada — todo comprimento/posicao é
# finito e positivo (exigência do renderer), mas nenhum deles é regra
# ---------------------------------------------------------------------------

def test_toda_instancia_tem_geometria_de_desenho_valida(cena):
    for inst in cena.instancias:
        assert inst.comprimento_mm > 0
        assert all(v == v for v in inst.posicao_mm)  # não é NaN


def test_a_cena_nao_promove_nenhuma_regra_dimensional_pendente():
    """A visualização não pode ter, como efeito colateral, transformado
    fórmula candidata em regra confirmada."""
    receita = receita_mod.construir_receita_preliminar()
    for regra in receita.regras_dimensionais:
        assert regra.estado is EstadoConhecimento.PENDENTE
        assert regra.expressao is None
    for regra in receita.regras_acessorios:
        assert regra.estado is EstadoConhecimento.PENDENTE


# ---------------------------------------------------------------------------
# Gates — exatamente como antes desta rodada
# ---------------------------------------------------------------------------

def test_gate_de_visualizacao_continua_aberto():
    rec = receita_mod.construir_receita_preliminar()
    bib = fontes.carregar_biblioteca_oficial()
    assert validar.validar_prontidao_para_visualizacao(rec, bib, RAIZ).ok


def test_gate_de_calculo_continua_bloqueado():
    rec = receita_mod.construir_receita_preliminar()
    bib = fontes.carregar_biblioteca_oficial()
    assert not validar.validar_prontidao_para_calculo(rec, bib, RAIZ).ok


def test_gate_de_producao_continua_bloqueado():
    rec = receita_mod.construir_receita_preliminar()
    bib = fontes.carregar_biblioteca_oficial()
    assert not validar.validar_prontidao_para_producao(rec, bib, RAIZ).ok


# ---------------------------------------------------------------------------
# Integração ponta a ponta — a cena realmente renderiza
# ---------------------------------------------------------------------------

def test_renderiza_a_composicao_completa(tmp_path):
    from contrato.consumo import carregar_biblioteca
    from core_engine.renderer import renderizar
    from domain.entidades import Perfil, Vista

    bib = carregar_biblioteca()
    cena_local = montar_cena_suprema_2f()
    codigos = sorted({inst.perfil_id.removeprefix("ALCOA-")
                      for inst in cena_local.instancias})
    perfis = {f"ALCOA-{c}": Perfil(id=f"ALCOA-{c}", fabricante="Alcoa",
                                   codigo_fabricante=c) for c in codigos}
    associacoes = [a for a in bib.associacoes if a.perfil_id in perfis]
    geometrias = {a.geometria_padrao_id: bib.geometria(a.geometria_padrao_id)
                 for a in associacoes}
    vista = Vista(id="V-TESTE", cena_id=cena_local.id,
                 tipo_projecao="isometrica")

    saida = renderizar(vista, cena_local, perfis, associacoes, geometrias,
                       str(tmp_path / "vista_teste.png"))

    import os
    assert os.path.exists(saida)
    assert os.path.getsize(saida) > 10_000
