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


# ---------------------------------------------------------------------------
# Viewport diagnóstica de curadoria — a ferramenta que Bruno usa para dizer
# qual orientação está certa. O que ela mostra TEM de ser a mesma composição
# que o renderer produz; se divergir, Bruno estaria validando outra coisa.
#
# Importada por caminho porque `curadoria/composicao/` é diretório de scripts
# standalone (sem __init__.py, ao contrário de `curadoria/aquisicao/`) — criar
# o pacote só para o teste mudaria a convenção do diretório.
# ---------------------------------------------------------------------------

def _viewport():
    import importlib.util
    caminho = RAIZ / "curadoria/composicao/viewport_diagnostica.py"
    spec = importlib.util.spec_from_file_location("viewport_diagnostica",
                                                  caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_viewport_reproduz_exatamente_a_composicao_do_renderer():
    """`deduzir_transform` levanta se algum ângulo não reproduzir os vértices
    do renderer dentro de 1e-6 mm — coletar sem erro é a prova."""
    dados = _viewport().coletar()
    assert len(dados["instancias"]) == 20
    assert set(dados["geometrias"]) == set(CODIGOS_ESPERADOS)


def test_viewport_expoe_apenas_angulos_de_90_graus():
    """Bruno ajusta em cliques de 90°; um estado inicial fora da grade o
    obrigaria a perseguir ângulos que os botões não alcançam."""
    for inst in _viewport().coletar()["instancias"]:
        for eixo in ("rx", "ry", "rz"):
            assert inst["inicial"][eixo] in (0, 90, 180, 270)


def test_viewport_cobre_os_tres_grupos_de_validacao():
    from collections import Counter
    grupos = Counter(i["grupo"] for i in _viewport().coletar()["instancias"])
    assert grupos == Counter({"QUADRO": 4, "FOLHAS": 8, "BAGUETES": 8})


# ---------------------------------------------------------------------------
# Montagem: as peças têm de SE ENCONTRAR
#
# Cada teste abaixo trava um defeito que a validação visual do Bruno
# encontrou na primeira versão da cena — quando ela era montada por margens
# ilustrativas fixas e nenhuma peça encostava na vizinha. São invariantes de
# DESENHO, não de fabricação: nenhum deles afirma medida, corte ou folga.
# ---------------------------------------------------------------------------

def _caixas():
    """Bounding box no mundo de cada instância, pela mesma função que o
    renderer usa para desenhar."""
    import numpy as np
    from core_engine.renderer import _pontos_no_mundo
    from composicao.visualizacao import _contorno_de

    caixas = {}
    for inst in montar_cena_suprema_2f().instancias:
        ct = _contorno_de(inst.perfil_id)
        pts = np.vstack([
            _pontos_no_mundo(ct, 0.0, inst.rotacao_graus, inst.posicao_mm,
                             inst.rotacao_xyz, inst.posicao_z_mm),
            _pontos_no_mundo(ct, inst.comprimento_mm, inst.rotacao_graus,
                             inst.posicao_mm, inst.rotacao_xyz,
                             inst.posicao_z_mm)])
        caixas[inst.instancia_id.split(":", 1)[-1]] = {
            eixo: (float(pts[:, i].min()), float(pts[:, i].max()))
            for i, eixo in enumerate("xyz")}
    return caixas


def test_marcos_horizontais_seguem_onde_bruno_validou():
    """SU-002 é a âncora que Bruno pediu para não mexer, e SU-001 ele deu
    como correto. Mover qualquer um dos dois invalidaria a validação visual
    já feita."""
    c = _caixas()
    assert c["QUADRO-INFERIOR"]["x"] == (0.0, 2000.0)
    assert c["QUADRO-INFERIOR"]["y"][0] == 0.0
    assert c["QUADRO-SUPERIOR"]["x"] == (0.0, 2000.0)
    assert c["QUADRO-SUPERIOR"]["y"][0] == 1200.0


def test_marco_lateral_alcanca_a_extremidade_do_trilho_superior():
    """Bruno: o SU-003 deve chegar até a extremidade do trilho superior. Na
    versão anterior ele parava em 1200 e o SU-001 ia até 1233."""
    c = _caixas()
    topo = c["QUADRO-SUPERIOR"]["y"][1]
    for lado in ("QUADRO-LATERAL-1", "QUADRO-LATERAL-2"):
        assert c[lado]["y"][1] == pytest.approx(topo)
        assert c[lado]["y"][0] == pytest.approx(0.0)


def test_marco_lateral_tem_a_profundidade_do_quadro():
    """Os quatro perfis do quadro fecham o mesmo volume: se o lateral tiver
    profundidade diferente dos trilhos, o quadro não é um quadro."""
    c = _caixas()
    prof = c["QUADRO-INFERIOR"]["z"]
    for lado in ("QUADRO-LATERAL-1", "QUADRO-LATERAL-2"):
        assert c[lado]["z"] == pytest.approx(prof)


def test_marco_lateral_nao_escapa_do_envelope():
    c = _caixas()
    assert c["QUADRO-LATERAL-1"]["x"][0] == pytest.approx(0.0)
    assert c["QUADRO-LATERAL-2"]["x"][1] == pytest.approx(2000.0)


def test_as_duas_folhas_ficam_em_planos_distintos():
    """O defeito que fazia "um dos lados ficar sempre aberto": as duas folhas
    estavam coplanares, e duas folhas de uma correr coplanares não podem se
    sobrepor."""
    c = _caixas()
    interna = c["FOLHA-INTERNA:MONTANTE-CENTRAL"]["z"]
    externa = c["FOLHA-EXTERNA:MONTANTE-CENTRAL"]["z"]
    assert interna[1] <= externa[0] or externa[1] <= interna[0]


def test_mao_de_amigo_ocupa_a_mesma_faixa_horizontal():
    """SU-040 e SU-041 se cruzam: mesma faixa em X, planos diferentes. É isso
    que faz o encontro central ler como encaixe, e não como duas peças
    separadas por uma lacuna."""
    c = _caixas()
    assert (c["FOLHA-INTERNA:MONTANTE-CENTRAL"]["x"]
            == pytest.approx(c["FOLHA-EXTERNA:MONTANTE-CENTRAL"]["x"]))


def test_travessas_encostam_nos_montantes_da_propria_folha():
    """Sem folga: a travessa vai de montante a montante. Era aqui que a folha
    "ficava aberta"."""
    c = _caixas()
    for folha, lateral, central in (
            ("FOLHA-INTERNA", "MONTANTE-LATERAL", "MONTANTE-CENTRAL"),
            ("FOLHA-EXTERNA", "MONTANTE-CENTRAL", "MONTANTE-LATERAL")):
        esq = c[f"{folha}:{lateral}"]["x"][1]
        dir_ = c[f"{folha}:{central}"]["x"][0]
        for t in ("TRAVESSA-SUPERIOR", "TRAVESSA-INFERIOR"):
            assert c[f"{folha}:{t}"]["x"] == pytest.approx((esq, dir_))


def test_travessas_ficam_dentro_do_vao_do_quadro():
    """A travessa superior chegava a y=1251, POR CIMA do trilho superior."""
    c = _caixas()
    base_do_trilho_superior = c["QUADRO-SUPERIOR"]["y"][0]
    topo_do_trilho_inferior = c["QUADRO-INFERIOR"]["y"][1]
    for folha in ("FOLHA-INTERNA", "FOLHA-EXTERNA"):
        assert c[f"{folha}:TRAVESSA-SUPERIOR"]["y"][1] <= base_do_trilho_superior
        assert c[f"{folha}:TRAVESSA-INFERIOR"]["y"][0] >= topo_do_trilho_inferior


def test_baguetes_encostam_no_quadro_da_folha():
    """Bruno deu a posição dos baguetes como certa e o comprimento como
    curto: eles flutuavam a 60mm de tudo."""
    c = _caixas()
    for folha in ("FOLHA-INTERNA", "FOLHA-EXTERNA"):
        vao_y = (c[f"{folha}:TRAVESSA-INFERIOR"]["y"][1],
                 c[f"{folha}:TRAVESSA-SUPERIOR"]["y"][0])
        for b in ("BAGUETE-VERTICAL-1", "BAGUETE-VERTICAL-2"):
            assert c[f"{folha}:{b}"]["y"] == pytest.approx(vao_y)


def test_as_duas_folhas_sao_praticamente_identicas():
    """Princípio de domínio informado por Bruno: as duas folhas de uma correr
    são praticamente iguais; a diferença fica nas mãos de amigo."""
    c = _caixas()
    def largura(k):
        return c[k]["x"][1] - c[k]["x"][0]
    for peca in ("TRAVESSA-SUPERIOR", "TRAVESSA-INFERIOR",
                 "BAGUETE-HORIZONTAL-1", "BAGUETE-HORIZONTAL-2"):
        assert largura(f"FOLHA-INTERNA:{peca}") == pytest.approx(
            largura(f"FOLHA-EXTERNA:{peca}"))


def test_nenhuma_instancia_usa_espelhamento():
    """Uma barra extrudada não pode ser espelhada no mundo físico — pares
    esquerda/direita são a mesma seção girada. O caminho `rotacao_xyz` não
    oferece espelho, e nenhuma instância pode cair no caminho antigo que
    oferecia."""
    for inst in montar_cena_suprema_2f().instancias:
        assert inst.rotacao_xyz is not None
