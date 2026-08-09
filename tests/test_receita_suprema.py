"""Sprint E.4D — infraestrutura preliminar da receita da Suprema de correr.

Estes testes cobrem o que a rodada realmente entrega: referências oficiais,
estados de conhecimento, exigência de evidência, leitura da ficha de campo,
gates de prontidão e imutabilidade.

O que eles NÃO cobrem, porque não existe: fórmula de corte, medida de vidro,
folga, sobreposição, quantidade de acessório e posição funcional de perfil.
Nenhuma delas foi confirmada pelo especialista, e um teste que fixasse um valor
inventado transformaria o chute em regressão protegida.
"""
import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from composicao import fontes, prontidao, receita as receita_mod, validar
from composicao.modelos import (ESCOPO_APROVACAO_FORMULAS,
                                ESCOPO_APROVACAO_RECEITA,
                                ESTADO_CASO_AGUARDANDO, ESTADO_CASO_PARCIAL,
                                ESTADO_CASO_RECEBIDO, ESTADO_CASO_VALIDADO,
                                ESTADO_RECEITA_PRELIMINAR,
                                AprovacaoEspecialista, CasoRealFabricacao,
                                ComponenteReceita, CorteReal,
                                EstadoConhecimento, FolgaReal, FonteEvidencia,
                                PapelComponente, ReceitaErro, ReceitaTipologia,
                                RegraAcessorio, RegraDimensional,
                                ResultadoAprovacao, ValidacaoCasoReal,
                                VidroReal)

RAIZ = Path(__file__).resolve().parent.parent
MODELO_FICHA = RAIZ / "composicao/insumos/suprema_2f_modelo_preenchimento.yaml"

PERFIS = fontes.PERFIS_SUPREMA_E4C


@pytest.fixture(scope="module")
def biblioteca():
    return fontes.carregar_biblioteca_oficial()


@pytest.fixture
def receita():
    return receita_mod.construir_receita_preliminar()


@pytest.fixture
def ficha_em_branco():
    return fontes.carregar_ficha_campo(MODELO_FICHA)


def _fonte(estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA, responsavel="Bruno",
           data="2026-08-03", id_fonte=None, tipo=None):
    """Fonte de teste com ID derivado do estado.

    IDs distintos por estado de propósito: o registro central recusa o mesmo
    `id_fonte` com conteúdos diferentes, e reaproveitar um único ID aqui
    esconderia justamente essa checagem."""
    tipo = tipo or ("especialista_de_dominio"
                    if estado is EstadoConhecimento.CONFIRMADO_ESPECIALISTA
                    else "lista_de_corte_real")
    id_fonte = id_fonte or f"FONTE-TESTE-{estado.value.replace('_', '-')}"
    # `identificador_externo`: a fonte de teste é um marcador, não um arquivo.
    # Declará-la como arquivo faria o gate cobrar um artefato que não existe.
    return FonteEvidencia(
        id_fonte=id_fonte, tipo=tipo,
        referencia=f"DECISAO-TESTE-{estado.value}",
        descricao="decisão registrada em teste", estado=estado,
        responsavel=responsavel, data=data,
        forma_referencia="identificador_externo")


def _regra_acessorio_confirmada(item="roldanas"):
    return RegraAcessorio(
        identificador=f"TESTE:acessorio:{item}", item=item,
        quantidade_expressao="PLACEHOLDER_DE_TESTE", posicao="base da folha",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))


# Fonte de especialista com autoria completa, datada no dia da aprovação.
FONTE_APROVACAO = FonteEvidencia(
    id_fonte="FONTE-APROVACAO", tipo="especialista_de_dominio",
    referencia="ARBITRAGEM-FINAL-TESTE",
    descricao="arbitragem final", estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
    responsavel="Bruno", data="2026-08-10",
    forma_referencia="identificador_externo")

# Evidência do caso real: lista de corte de verdade, não parecer.
FONTE_CASO = FonteEvidencia(
    id_fonte="FONTE-CASO-01", tipo="lista_de_corte_real",
    referencia="LISTA-CASO-01", descricao="lista de corte real",
    estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
    responsavel="Bruno", data="2026-08-10",
    forma_referencia="identificador_externo")


def _aprovacao(escopo, resultado=ResultadoAprovacao.APROVADO,
               responsavel="Bruno", fonte_id="FONTE-APROVACAO",
               data="2026-08-10"):
    return AprovacaoEspecialista(
        resultado=resultado, responsavel=responsavel, data=data,
        fonte_id=fonte_id, escopo=escopo)


def _validacao_aprovada(resultado=ResultadoAprovacao.APROVADO,
                        fontes_ids=("FONTE-CASO-01",)):
    return ValidacaoCasoReal(
        resultado=resultado, responsavel="Bruno", data="2026-08-10",
        fontes_ids=fontes_ids)


def _corte_confirmado(perfil="SU-001", comprimento="1000", quantidade=1,
                      componente_id="TESTE:SU-001", id_fonte="FONTE-CASO-01"):
    return CorteReal(perfil=perfil, comprimento_mm=Decimal(comprimento),
                     quantidade=quantidade, componente_id=componente_id,
                     estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                     fontes_ids=(id_fonte,))


def _vidro_confirmado(largura="500", altura="900",
                      id_fonte="FONTE-CASO-01"):
    return VidroReal(folha="1", largura_mm=Decimal(largura),
                     altura_mm=Decimal(altura), espessura_mm=Decimal("6"),
                     estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                     fontes_ids=(id_fonte,))


def _fonte_do_caso(id_fonte, ident):
    """Evidência PRIMÁRIA — própria de cada exemplar."""
    return FonteEvidencia(
        id_fonte=id_fonte, tipo="lista_de_corte_real",
        referencia=f"LISTA-{ident}", descricao="lista de corte real",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        responsavel="Bruno", data="2026-08-10",
        forma_referencia="identificador_externo")


def _caso_validado(ident, largura, altura, validacao=None,
                   id_fonte="FONTE-CASO-01", **kw):
    base = dict(
        identificador=ident, id_exemplar=f"OP-{ident}",
        largura_total_mm=Decimal(largura), altura_total_mm=Decimal(altura),
        estado_dimensoes=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes_ids_dimensoes=(id_fonte,),
        cortes=(_corte_confirmado(id_fonte=id_fonte),),
        vidros=(_vidro_confirmado(id_fonte=id_fonte),),
        fontes=(_fonte_do_caso(id_fonte, ident),),
        estado_recebimento=ESTADO_CASO_RECEBIDO,
        validacao=(validacao if validacao is not None
                   else _validacao_aprovada(fontes_ids=(id_fonte,))))
    base.update(kw)
    return CasoRealFabricacao(**base)


def _caso_homologavel(ident, largura, altura, id_fonte):
    """Caso que corresponde, peça a peça, à receita de `_receita_completa()`.

    Um corte por ocorrência funcional, um vidro e os seis acessórios: é o que
    a comparação com a receita exige, e por isso a fixture precisa entregá-lo
    completo — senão o teste reprovaria por motivo diferente do que quer provar."""
    from composicao.modelos import ITENS_DE_ACESSORIO_BASE, AcessorioReal
    cortes = tuple(_corte_confirmado(perfil=perfil,
                                     componente_id=f"TESTE:{perfil}",
                                     id_fonte=id_fonte) for perfil in PERFIS)
    acessorios = tuple(
        AcessorioReal(item=item, quantidade=2, posicao="janela",
                      estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                      fontes_ids=(id_fonte,))
        for item in ITENS_DE_ACESSORIO_BASE)
    return _caso_validado(ident, largura, altura, id_fonte=id_fonte,
                          cortes=cortes, acessorios=acessorios)


_TRES_CASOS_HOMOLOGAVEIS = None      # preenchido após os helpers


FONTE_CONFERENCIA = FonteEvidencia(
    id_fonte="FONTE-CONFERENCIA", tipo="conferencia_caso_receita",
    referencia="CONFERENCIA-TESTE",
    descricao="comparação do resultado calculado com a janela real",
    estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
    responsavel="Bruno", data="2026-08-10",
    forma_referencia="identificador_externo")


def _conferencia(caso_id, id_fonte="FONTE-CONFERENCIA",
                 resultado=ResultadoAprovacao.APROVADO, divergencias=(),
                 resultado_calculo_id=None, componentes=None):
    from composicao.modelos import ConferenciaCasoContraReceita
    return ConferenciaCasoContraReceita(
        caso_id=caso_id, resultado=resultado, responsavel="Bruno",
        data="2026-08-10", fonte_id=id_fonte,
        resultado_calculo_id=resultado_calculo_id or f"RES-{caso_id}",
        componentes_conferidos=(tuple(f"TESTE:{p}" for p in PERFIS)
                                if componentes is None else componentes),
        cortes_conferidos=True, vidros_conferidos=True,
        acessorios_conferidos=True, divergencias=divergencias)


def _resultado_calculado(caso_id, receita_codigo="TESTE", **kw):
    """Resultado de FIXTURE, espelhando o caso homologável.

    Os números são artificiais e servem só para exercitar estrutura e
    comparação. `origem=FIXTURE_TESTE` garante que ele nunca abre produção — a
    E.4D não tem motor de cálculo."""
    from composicao.modelos import (AcessorioCalculado, CorteCalculado,
                                    ITENS_DE_ACESSORIO_BASE,
                                    OrigemResultadoCalculo,
                                    ResultadoCalculoCaso, VidroCalculado)
    base = dict(
        id_resultado=f"RES-{caso_id}", caso_id=caso_id,
        receita_codigo=receita_codigo, gerado_por="fixture de teste",
        origem=OrigemResultadoCalculo.FIXTURE_TESTE,
        componentes=tuple(f"TESTE:{p}" for p in PERFIS),
        cortes=tuple(CorteCalculado(componente_id=f"TESTE:{p}", perfil=p,
                                    comprimento_mm=Decimal("1000"),
                                    quantidade=1) for p in PERFIS),
        vidros=(VidroCalculado(folha="1", largura_mm=Decimal("500"),
                               altura_mm=Decimal("900"),
                               espessura_mm=Decimal("6")),),
        acessorios=tuple(AcessorioCalculado(item=i, quantidade=2,
                                            posicao="janela")
                         for i in ITENS_DE_ACESSORIO_BASE))
    base.update(kw)
    return ResultadoCalculoCaso(**base)


def _componente_confirmado(codigo="SU-001", **kw):
    base = dict(
        identificador=f"TESTE:{codigo}",
        perfil=fontes.referencia_oficial(codigo),
        papel=PapelComponente.MARCO_SUPERIOR,
        quantidade=1, orientacao="horizontal",
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        fontes=(_fonte(),))
    base.update(kw)
    return ComponenteReceita(**base)


# ===========================================================================
# Referências à biblioteca oficial
# ===========================================================================

def test_carrega_os_oito_geos_oficiais(receita, biblioteca):
    codigos = {g.codigo for g in biblioteca.geometrias}
    for p in PERFIS:
        assert f"GEO-{p}" in codigos, p
    assert len(receita.perfis_disponiveis) == 8
    # Inventário e ocorrências são contagens diferentes: 8 perfis, 20 peças.
    assert len(receita.componentes) == 20
    r = validar.validar_referencias_geometricas(receita, biblioteca)
    assert r.ok, r.descrever()


def test_rejeita_geo_inexistente(biblioteca, receita):
    comp = _componente_confirmado("SU-001")
    from dataclasses import replace
    ref = replace(comp.perfil, id_geometria="GEO-NAO-EXISTE")
    r2 = replace(receita, componentes=(replace(comp, perfil=ref),))
    r = validar.validar_referencias_geometricas(r2, biblioteca)
    assert not r.ok and any("geometria inexistente" in f["regra"] for f in r.falhas)


def test_rejeita_associacao_orfa(receita, biblioteca):
    from dataclasses import replace

    class BibliotecaComOrfa:
        geometrias = tuple(biblioteca.geometrias)
        associacoes = tuple(biblioteca.associacoes) + (
            replace(biblioteca.associacoes[0], perfil_id="FANTASMA-001",
                    geometria_padrao_id="GEO-QUE-NAO-EXISTE"),)
    r = validar.validar_referencias_geometricas(receita, BibliotecaComOrfa)
    assert not r.ok and any("órfãs" in f["regra"] for f in r.falhas)


def test_rejeita_codigo_apontando_para_geo_errado(receita, biblioteca):
    from dataclasses import replace
    trocadas = tuple(
        replace(a, geometria_padrao_id="GEO-SU-005")
        if a.perfil_id == "ALCOA-SU-053" else a
        for a in biblioteca.associacoes)

    class BibliotecaTrocada:
        geometrias = tuple(biblioteca.geometrias)
        associacoes = trocadas
    r = validar.validar_referencias_geometricas(receita, BibliotecaTrocada)
    assert not r.ok
    assert any("outra geometria" in f["regra"] for f in r.falhas)


def test_confirma_ausencia_de_geo_tms102(receita, biblioteca):
    """SU-102 e TMS-102 são o mesmo perfil físico — uma geometria própria para
    o TMS-102 quebraria a identidade confirmada no E.4C."""
    assert "GEO-TMS-102" not in {g.codigo for g in biblioteca.geometrias}
    assert validar.validar_referencias_geometricas(receita, biblioteca).ok
    assert [p for p in receita.perfis_disponiveis
            if p.codigo_perfil == "SU-102"][0].id_geometria == "GEO-SU-102"


# ===========================================================================
# Estados de conhecimento
# ===========================================================================

def test_aceita_componente_confirmado():
    c = _componente_confirmado()
    assert c.confirmado and c.pendencias() == ()


def test_aceita_componente_pendente_em_receita_preliminar(receita, biblioteca):
    """A topologia confirmada não fecha a porta para o que ainda falta.

    Um componente futuro entra pendente e a visualização preliminar continua
    aberta — do contrário, registrar conhecimento parcial ficaria proibido."""
    from dataclasses import replace
    assert receita.preliminar
    pendente = _componente_confirmado("SU-102",
                                      estado=EstadoConhecimento.PENDENTE,
                                      fontes=())
    assert not pendente.confirmado
    r2 = replace(receita, componentes=receita.componentes + (pendente,))
    r = validar.validar_prontidao_para_visualizacao(r2, biblioteca)
    assert r.ok, r.descrever()


def test_bloqueia_calculo_sem_ocorrencias_funcionais(receita, biblioteca):
    """Saber quais perfis existem não é saber como a janela se monta."""
    from dataclasses import replace
    so_inventario = replace(receita, componentes=(), relacoes=())
    r = validar.validar_prontidao_para_calculo(so_inventario, biblioteca)
    assert not r.ok
    assert any("nenhuma ocorrência funcional" in f["regra"] for f in r.falhas)


def test_topologia_conhecida_nao_abre_o_gate_de_calculo(receita, biblioteca):
    """E saber ONDE cada perfil fica ainda não é saber QUANTO ele mede."""
    r = validar.validar_prontidao_para_calculo(receita, biblioteca)
    assert not r.ok
    assert not any("nenhuma ocorrência funcional" in f["regra"]
                   for f in r.falhas), "a topologia já foi registrada"
    assert any("fórmula" in f["regra"] for f in r.falhas)


def test_bloqueia_producao_com_hipotese(biblioteca, receita):
    """Hipótese é conhecimento honesto — e não autoriza cortar alumínio."""
    from dataclasses import replace
    hipotese = _componente_confirmado(
        estado=EstadoConhecimento.HIPOTESE,
        fontes=(_fonte(estado=EstadoConhecimento.HIPOTESE),))
    assert not hipotese.confirmado
    r2 = replace(receita, componentes=(hipotese,), estado="CONFIRMADA")
    assert not validar.validar_prontidao_para_producao(r2, biblioteca).ok
    assert not validar.validar_prontidao_para_calculo(r2, biblioteca).ok


def test_nao_interpreta_none_como_zero(receita):
    for regra in receita.regras_dimensionais:
        assert regra.expressao is None
        assert not regra.calculavel
    for a in receita.regras_acessorios:
        assert a.quantidade_expressao is None
    with pytest.raises(ReceitaErro, match="nunca 0"):
        _componente_confirmado(quantidade=0)
    caso = CasoRealFabricacao(identificador="CASO_A_PEQUENO")
    assert caso.largura_total_mm is None and not caso.tem_medidas


# ===========================================================================
# Fontes de evidência
# ===========================================================================

def test_exige_fonte_para_regra_confirmada():
    with pytest.raises(ReceitaErro, match="sem evidência"):
        RegraDimensional(
            identificador="X", descricao="d", alvo="largura_folha",
            expressao="largura_total_mm / 2",
            estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA, fontes=())


def test_aceita_pendencia_sem_formula(receita):
    for regra in receita.regras_dimensionais:
        assert regra.expressao is None
        assert regra.estado is EstadoConhecimento.PENDENTE
        assert not regra.calculavel


def test_rejeita_regra_confirmada_sem_expressao():
    with pytest.raises(ReceitaErro, match="sem expressão"):
        RegraDimensional(
            identificador="X", descricao="d", alvo="altura_vidro",
            expressao=None,
            estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
            fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))


def test_preserva_autoria_da_decisao_do_especialista(biblioteca, receita):
    from dataclasses import replace
    sem_autor = RegraDimensional(
        identificador="X", descricao="d", alvo="largura_folha",
        expressao="PLACEHOLDER_DE_TESTE",
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        fontes=(_fonte(responsavel=None),))
    r2 = replace(receita, regras_corte=(sem_autor,))
    r = validar.validar_fontes(r2)
    assert not r.ok
    assert any("autoria completa" in str(f["encontrado"]) for f in r.falhas)

    com_autor = replace(sem_autor, fontes=(_fonte(responsavel="Bruno"),))
    assert validar.validar_fontes(replace(receita, regras_corte=(com_autor,))).ok


def test_fonte_recusa_caminho_absoluto():
    with pytest.raises(ReceitaErro, match="absoluto"):
        FonteEvidencia(id_fonte="FONTE-X", tipo="foto",
                       referencia="/home/bruno/foto.jpg",
                       descricao="", estado=EstadoConhecimento.PENDENTE)


def test_fonte_recusa_tipo_desconhecido():
    with pytest.raises(ReceitaErro, match="tipo de fonte desconhecido"):
        FonteEvidencia(id_fonte="FONTE-X", tipo="chute", referencia="x",
                       descricao="", estado=EstadoConhecimento.PENDENTE)


# ===========================================================================
# Ficha de campo
# ===========================================================================

def test_carrega_ficha_estruturalmente_valida(ficha_em_branco):
    r = fontes.validar_estrutura_ficha(ficha_em_branco, "modelo")
    assert r.ok, r.descrever()
    assert ficha_em_branco["tipologia"]["codigo"] == "SUPREMA_CORRER_2F"


def test_rejeita_ficha_sem_tipologia():
    r = fontes.validar_estrutura_ficha(
        {"versao_ficha": 1, "caso_real": {}}, "x")
    assert not r.ok
    assert any("tipologia" in f["alvo"] for f in r.falhas)


@pytest.mark.parametrize("campo", ["largura_total_mm", "altura_total_mm"])
@pytest.mark.parametrize("valor", [0, -1, "0", "abc"])  # noqa: PT006
def test_rejeita_medida_nao_positiva_ou_nao_numerica(ficha_em_branco, campo, valor):
    d = copy.deepcopy(ficha_em_branco)
    d["caso_real"][campo] = valor
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any(campo in f["alvo"] for f in r.falhas)


def test_rejeita_perfil_desconhecido(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-999"] = {"observacoes_gerais": "x"}
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("fora do microlote" in f["regra"] for f in r.falhas)


def test_rejeita_campo_inventado_no_perfil(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-001"] = {"observacoes_gerais": "x", "peso_kg_m": 1.2}
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("campo desconhecido" in f["regra"] for f in r.falhas)


def test_nao_inventa_campo_ausente(ficha_em_branco):
    """Campo em branco entra como None — não como 0, não como string vazia
    convertida em número."""
    caso = fontes.converter_ficha_em_caso_real(ficha_em_branco, "modelo")
    assert caso.largura_total_mm is None
    assert caso.altura_total_mm is None
    assert caso.cortes == () and caso.vidros == () and caso.acessorios == ()
    assert caso.estado_recebimento == ESTADO_CASO_AGUARDANDO


def test_extrai_pendencias(ficha_em_branco):
    pend = fontes.extrair_pendencias(ficha_em_branco)
    escopos = {p["escopo"] for p in pend}
    assert "caso_real" in escopos and "vista" in escopos
    for p in PERFIS:
        assert f"perfis.{p}" in escopos, p
    assert len(pend) >= 3 + 5 + len(PERFIS), \
        "caso, vista e um item de aplicações por perfil"


def test_extrai_confirmacoes(ficha_em_branco):
    assert fontes.extrair_campos_preenchidos(ficha_em_branco) == ()
    d = copy.deepcopy(ficha_em_branco)
    d["vista"]["lado_de_referencia"] = "interno"
    d["perfis"]["SU-001"] = {"aplicacoes": [
        {"id_componente": "MARCO-SUP", "funcao": "MARCO_SUPERIOR",
         "quantidade": 1, "orientacao": "horizontal"}]}
    dec = fontes.extrair_campos_preenchidos(d)
    campos = {(x["escopo"], x["campo"]) for x in dec}
    assert ("vista", "lado_de_referencia") in campos
    assert ("perfis.SU-001.aplicacoes[0]", "funcao") in campos
    assert ("perfis.SU-001.aplicacoes[0]", "quantidade") in campos
    pend = fontes.extrair_pendencias(d)
    assert ("perfis.SU-001", "aplicacoes") not in {(p["escopo"], p["campo"])
                                                   for p in pend}


def test_ficha_preenchida_vira_caso_real(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["caso_real"] = {"identificador": "CASO_B_MEDIO",
                      "largura_total_mm": 1500, "altura_total_mm": "1200,5"}
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.identificador == "CASO_B_MEDIO"
    assert caso.largura_total_mm == Decimal("1500")
    assert caso.altura_total_mm == Decimal("1200.5")
    assert caso.estado_recebimento == ESTADO_CASO_PARCIAL, \
        "sem lista de corte, o caso ainda é parcial"


def test_ficha_em_json_equivale_a_yaml(ficha_em_branco, tmp_path):
    """O formato é conveniência de edição; o conteúdo é o mesmo."""
    p = tmp_path / "ficha.json"
    p.write_text(json.dumps(ficha_em_branco, ensure_ascii=False), encoding="utf-8")
    assert fontes.carregar_ficha_campo(p) == ficha_em_branco


def test_ficha_inexistente_e_recusada(tmp_path):
    with pytest.raises(ReceitaErro, match="ausente"):
        fontes.carregar_ficha_campo(tmp_path / "nao_existe.yaml")


# ===========================================================================
# Prontidão e gates
# ===========================================================================

def test_oito_geometrias_disponiveis(receita, biblioteca):
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    assert len(rel["geometrias"]["disponiveis"]) == 8
    assert rel["geometrias"]["ausentes"] == []


def test_gate_visual_preliminar_aberto_com_pendencias(receita, biblioteca):
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    g = rel["gates"]["visualizacao_preliminar"]
    assert g["aberto"] is True
    assert rel["perfis_disponiveis"] == list(PERFIS)
    assert rel["componentes"]["total"] == 20


def test_gate_visual_fecha_se_receita_deixar_de_ser_preliminar(receita, biblioteca):
    from dataclasses import replace
    pendente = _componente_confirmado(estado=EstadoConhecimento.PENDENTE,
                                      fontes=())
    r2 = replace(receita, estado="CONFIRMADA", componentes=(pendente,))
    r = validar.validar_prontidao_para_visualizacao(r2, biblioteca)
    assert not r.ok, "receita não preliminar não pode ter papel pendente"


def test_gate_de_calculo_bloqueado_inicialmente(receita, biblioteca):
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    g = rel["gates"]["calculo"]
    assert g["aberto"] is False
    assert g["bloqueios"], "gate bloqueado sem motivo legível é só um 'não'"


def test_gate_de_producao_bloqueado_inicialmente(receita, biblioteca):
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    assert rel["gates"]["producao"]["aberto"] is False


_TRES_CASOS = (_caso_validado("CASO_A_PEQUENO", "800", "600",
                              id_fonte="FONTE-CASO-A"),
               _caso_validado("CASO_B_MEDIO", "1500", "1200",
                              id_fonte="FONTE-CASO-B"),
               _caso_validado("CASO_C_GRANDE", "2400", "2100",
                              id_fonte="FONTE-CASO-C"))

_TRES_CASOS_HOMOLOGAVEIS = (
    _caso_homologavel("CASO_A_PEQUENO", "800", "600", "FONTE-CASO-A"),
    _caso_homologavel("CASO_B_MEDIO", "1500", "1200", "FONTE-CASO-B"),
    _caso_homologavel("CASO_C_GRANDE", "2400", "2100", "FONTE-CASO-C"))


def _receita_homologavel():
    """Receita completa + três casos que a comprovam + aprovações."""
    from dataclasses import replace
    return replace(
        _receita_completa(), casos_reais=_TRES_CASOS_HOMOLOGAVEIS,
        aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                    _aprovacao(ESCOPO_APROVACAO_FORMULAS)),
        conferencias=tuple(_conferencia(c.identificador)
                           for c in _TRES_CASOS_HOMOLOGAVEIS),
        fontes=(FONTE_APROVACAO, FONTE_CONFERENCIA))


def _regra_confirmada(alvo):
    """Regra com fórmula e evidência — o `PLACEHOLDER` deixa explícito que
    nenhuma expressão real de fabricação foi inventada nos testes."""
    return RegraDimensional(
        identificador=f"TESTE:{alvo}", descricao="d", alvo=alvo,
        expressao="PLACEHOLDER_DE_TESTE", variaveis=("largura_total_mm",),
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))


def _receita_completa(regra=None):
    """Receita estruturalmente completa e com tudo confirmado.

    Cobre os nove alvos dimensionais e os seis acessórios: a cobertura
    estrutural vale para todos os gates, e uma fixture incompleta reprovaria
    por motivo diferente do que o teste quer provar."""
    from composicao.modelos import (ALVOS_DIMENSIONAIS_BASE as ALVOS_DIMENSIONAIS,
                                    ITENS_DE_ACESSORIO_BASE as ITENS_DE_ACESSORIO)
    alvos_vidro = ("largura_vidro", "altura_vidro")
    corte = tuple(_regra_confirmada(a) for a in ALVOS_DIMENSIONAIS
                  if a not in alvos_vidro)
    if regra is not None:
        corte = (regra,) + tuple(g for g in corte if g.alvo != regra.alvo)
    return ReceitaTipologia(
        codigo="TESTE", nome="t", sistema="Suprema", quantidade_folhas=2,
        perfis_disponiveis=tuple(fontes.referencia_oficial(p) for p in PERFIS),
        componentes=tuple(_componente_confirmado(p) for p in PERFIS),
        regras_corte=corte,
        regras_vidro=tuple(_regra_confirmada(a) for a in alvos_vidro),
        regras_acessorios=tuple(_regra_acessorio_confirmada(i)
                                for i in ITENS_DE_ACESSORIO),
        fontes=(FONTE_APROVACAO,), estado="CONFIRMADA")


def test_producao_exige_casos_reais_validados_e_aprovacao(biblioteca):
    """Mesmo com tudo confirmado, sem janela real fabricada não há produção."""
    from dataclasses import replace
    completa = _receita_completa()
    assert validar.validar_prontidao_para_calculo(completa, biblioteca).ok
    r = validar.validar_prontidao_para_producao(completa, biblioteca)
    assert not r.ok
    assert any("canônicos ausentes" in f["regra"] for f in r.falhas)
    assert any("aprovação do especialista" in f["regra"] for f in r.falhas)

    # Documentação completa NÃO basta: sem resultado calculado não há o que
    # conferir, e a produção continua fechada.
    com_casos = _receita_homologavel()
    r2 = validar.validar_prontidao_para_producao(com_casos, biblioteca)
    assert not r2.ok
    assert any("nenhum resultado calculado" in f["regra"] for f in r2.falhas)


def test_relatorio_lista_todas_as_pendencias(receita, biblioteca):
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    assert rel["componentes"]["pendentes"] == []
    assert len(rel["acessorios"]["pendentes"]) == len(receita.regras_acessorios)
    assert len(rel["regras"]["pendentes"]) == 9
    # Topologia confirmada; o dimensional inteiro segue pendente.
    assert len(rel["componentes"]["confirmados"]) == 20
    assert rel["regras"]["confirmadas"] == []
    assert len(rel["perguntas_abertas"]) >= 8
    assert rel["casos_reais"] == {"recebidos": [], "validados": []}


def test_relatorio_markdown_e_legivel(receita, biblioteca):
    md = prontidao.relatorio_em_markdown(
        prontidao.gerar_relatorio_prontidao(receita, biblioteca))
    assert "BLOQUEADO" in md and "Perguntas abertas" in md
    assert "Checklist da visita" in md
    assert "Perfis disponíveis" in md
    for p in PERFIS:
        assert p in md, p


def test_nova_geometria_futura_nao_interfere_na_receita(receita, biblioteca):
    """Um lote futuro acrescenta geometrias. A receita do E.4D não muda."""
    class BibliotecaMaior:
        geometrias = tuple(biblioteca.geometrias) + (
            type(biblioteca.geometrias[0])(
                **{**biblioteca.geometrias[0].__dict__, "codigo": "GEO-FUTURO-001"}),)
        associacoes = tuple(biblioteca.associacoes)
    antes = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    depois = prontidao.gerar_relatorio_prontidao(receita, BibliotecaMaior)
    assert depois["geometrias"]["disponiveis"] == antes["geometrias"]["disponiveis"]
    assert depois["gates"]["calculo"]["aberto"] is False
    assert validar.validar_referencias_geometricas(receita, BibliotecaMaior).ok


# ===========================================================================
# Imutabilidade e determinismo
# ===========================================================================

def test_construir_receita_nao_altera_a_biblioteca(biblioteca):
    antes = ([g.codigo for g in biblioteca.geometrias],
             [a.perfil_id for a in biblioteca.associacoes])
    rec = receita_mod.construir_receita_preliminar()
    prontidao.gerar_relatorio_prontidao(rec, biblioteca)
    validar.validar_prontidao_para_producao(rec, biblioteca)
    assert ([g.codigo for g in biblioteca.geometrias],
            [a.perfil_id for a in biblioteca.associacoes]) == antes


def test_receita_nao_altera_dados_oficiais_no_disco(biblioteca):
    import hashlib
    caminhos = [RAIZ / "dados/geometrias.json", RAIZ / "dados/perfil_geometria.json"]
    antes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in caminhos]
    rec = receita_mod.construir_receita_preliminar()
    prontidao.gerar_relatorio_prontidao(rec, biblioteca)
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in caminhos] == antes


def test_carregar_ficha_nao_altera_o_arquivo():
    import hashlib
    antes = hashlib.sha256(MODELO_FICHA.read_bytes()).hexdigest()
    d = fontes.carregar_ficha_campo(MODELO_FICHA)
    fontes.validar_estrutura_ficha(d, "x")
    fontes.extrair_pendencias(d)
    fontes.converter_ficha_em_caso_real(d, "x")
    assert hashlib.sha256(MODELO_FICHA.read_bytes()).hexdigest() == antes


def test_validacao_e_deterministica(receita, biblioteca):
    a = validar.validar_prontidao_para_calculo(receita, biblioteca)
    b = validar.validar_prontidao_para_calculo(receita, biblioteca)
    assert a == b


def test_duas_execucoes_produzem_o_mesmo_relatorio(biblioteca):
    um = prontidao.gerar_relatorio_prontidao(
        receita_mod.construir_receita_preliminar(), biblioteca)
    dois = prontidao.gerar_relatorio_prontidao(
        receita_mod.construir_receita_preliminar(), biblioteca)
    assert json.dumps(um, sort_keys=True) == json.dumps(dois, sort_keys=True)


def test_receita_preliminar_e_imutavel(receita):
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        receita.estado = "CONFIRMADA"
    with pytest.raises(dataclasses.FrozenInstanceError):
        receita.perfis_disponiveis[0].codigo_perfil = "X"


# ===========================================================================
# A rodada não pode ter inventado regra de fabricação
# ===========================================================================

def test_nenhuma_formula_de_fabricacao_foi_declarada(receita):
    """A prova explícita de que esta sprint não inventou engenharia."""
    for regra in receita.regras_dimensionais:
        assert regra.expressao is None, regra.identificador
        assert regra.variaveis == ()
        assert regra.estado is EstadoConhecimento.PENDENTE
    for acessorio in receita.regras_acessorios:
        assert acessorio.quantidade_expressao is None, acessorio.identificador
        assert acessorio.posicao is None
        assert acessorio.estado is EstadoConhecimento.PENDENTE
    assert receita.estado == ESTADO_RECEITA_PRELIMINAR


def test_todo_componente_tem_papel_atribuido(receita):
    """Depois da E.4E, nenhuma ocorrência fica sem papel declarado."""
    assert len(receita.perfis_disponiveis) == 8
    for c in receita.componentes:
        assert c.papel is not PapelComponente.NAO_CONFIRMADO, c.identificador
        assert c.orientacao in ("vertical", "horizontal"), c.identificador


def test_cli_nao_expoe_comando_de_calculo():
    from composicao import cli
    with pytest.raises(SystemExit):
        cli.main(["calcular", "--tipologia", "SUPREMA_CORRER_2F"])


@pytest.mark.parametrize("argv", [
    ["diagnosticar"], ["prontidao"], ["prontidao", "--json"],
    ["prontidao", "--markdown"],
    ["validar-ficha", "composicao/insumos/suprema_2f_modelo_preenchimento.yaml"],
])
def test_cli_roda_sem_erro(argv, capsys):
    from composicao import cli
    assert cli.main(argv) == 0
    assert capsys.readouterr().out.strip()


# ===========================================================================
# Regressões da auditoria corretiva
#
# Cada teste aqui trava um erro que a auditoria encontrou. O padrão comum:
# dado desconhecido virando informação, dado real sendo descartado, ou
# "preenchido" sendo lido como "confirmado".
# ===========================================================================

def test_ficha_vazia_nao_cria_caso_a_pequeno(ficha_em_branco):
    """O bug em uma linha: identificador vazio virava CASO_A_PEQUENO — o
    conversor inventava justamente o dado que a ficha existe para coletar."""
    caso = fontes.converter_ficha_em_caso_real(ficha_em_branco, "modelo")
    assert caso.identificador is None
    assert caso.identificador != "CASO_A_PEQUENO"


def test_identificador_vazio_continua_pendencia(ficha_em_branco):
    pend = fontes.extrair_pendencias(ficha_em_branco)
    assert {"escopo": "caso_real", "campo": "identificador"} in [
        {"escopo": p["escopo"], "campo": p["campo"]} for p in pend]


def test_cli_mostra_nao_informado_para_caso_sem_identificador(capsys):
    from composicao import cli
    assert cli.main(["validar-ficha", str(MODELO_FICHA)]) == 0
    saida = capsys.readouterr().out
    assert "caso real: NAO_INFORMADO" in saida
    assert "CASO_A_PEQUENO" not in saida


def test_caso_real_recusa_identificador_desconhecido():
    with pytest.raises(ReceitaErro, match="identificador de caso desconhecido"):
        CasoRealFabricacao(identificador="CASO_Z")


def test_codigo_de_tipologia_diferente_reprova(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["tipologia"]["codigo"] = "SUPREMA_CORRER_3F"
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("código de tipologia divergente" in f["regra"] for f in r.falhas)


@pytest.mark.parametrize("versao", [None, 0, 2, "1"])
def test_versao_de_ficha_desconhecida_reprova(ficha_em_branco, versao):
    d = copy.deepcopy(ficha_em_branco)
    if versao is None:
        d.pop("versao_ficha")
    else:
        d["versao_ficha"] = versao
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("versao_ficha" in f["alvo"] for f in r.falhas)


def test_campo_desconhecido_na_raiz_reprova(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["cortess"] = []
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    falha = next(f for f in r.falhas if "cortess" in str(f["alvo"]))
    assert falha["esperado"].startswith("cortes"), \
        "a mensagem tem de sugerir o nome certo"


def test_campo_desconhecido_em_vista_reprova(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["vista"]["lado_de_referencias"] = "interno"
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    falha = next(f for f in r.falhas if "lado_de_referencias" in str(f["alvo"]))
    assert falha["esperado"].startswith("lado_de_referencia")


def test_campo_desconhecido_em_item_de_corte_reprova(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["cortes"] = [{"perfil": "SU-001", "comprimento_mmm": 1000}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    falha = next(f for f in r.falhas if "comprimento_mmm" in str(f["alvo"]))
    assert falha["esperado"].startswith("comprimento_mm")


def test_funcao_de_perfil_invalida_reprova(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-001"] = {"aplicacoes": [{"funcao": "MARCO_SUPERIORR"}]}
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    falha = next(f for f in r.falhas if "funcao" in str(f["alvo"]))
    assert falha["esperado"] == "MARCO_SUPERIOR"


@pytest.mark.parametrize("secao,valor", [
    ("vista", "interno"), ("vista", ["a"]),
    ("perfis", ["SU-001"]), ("perfis", "SU-001"),
    ("caso_real", "1500x1200"), ("cortes", {"perfil": "SU-001"}),
])
def test_ficha_malformada_nao_derruba_a_cli(ficha_em_branco, secao, valor,
                                            tmp_path, capsys):
    """Erro de preenchimento comum não pode virar traceback: quem preenche a
    ficha é o especialista, não um programador."""
    d = copy.deepcopy(ficha_em_branco)
    d[secao] = valor
    p = tmp_path / "ficha.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    # extratores defensivos por contrato
    assert isinstance(fontes.extrair_campos_preenchidos(d), tuple)
    assert isinstance(fontes.extrair_pendencias(d), tuple)
    assert isinstance(fontes.extrair_decisoes_confirmadas(d), tuple)

    from composicao import cli
    assert cli.main(["validar-ficha", str(p)]) != 0
    assert "Traceback" not in capsys.readouterr().out


def test_fonte_com_estado_invalido_nao_gera_traceback(ficha_em_branco, tmp_path,
                                                      capsys):
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"tipo": "foto", "referencia": "curadoria/x.jpg",
                    "estado": "CONFIRMADISSIMO"}]
    p = tmp_path / "ficha.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    from composicao import cli
    assert cli.main(["validar-ficha", str(p)]) != 0
    assert "Traceback" not in capsys.readouterr().out
    r = fontes.validar_estrutura_ficha(d, "x")
    assert any("estado de conhecimento desconhecido" in f["regra"]
               for f in r.falhas)


def test_conversao_preserva_todas_as_secoes(ficha_em_branco):
    """A conversão antiga descartava vista, perfis, baguetes, folgas,
    sobreposições e dúvidas — exatamente o que a visita à serralheria produz."""
    d = copy.deepcopy(ficha_em_branco)
    d["caso_real"] = {"identificador": "CASO_A_PEQUENO",
                      "largura_total_mm": 800, "altura_total_mm": 600}
    d["vista"] = {"lado_de_referencia": "interno",
                  "folha_trilho_interno": "folha 1",
                  "folha_trilho_externo": "folha 2",
                  "sentidos_de_movimento": "folha 1 abre à direita",
                  "posicao_do_fecho": "montante central da folha 1"}
    d["perfis"]["SU-001"] = {
        "observacoes_gerais": "trilho duplo",
        "aplicacoes": [{"id_componente": "MARCO-SUPERIOR",
                        "funcao": "MARCO_SUPERIOR", "quantidade": 1,
                        "orientacao": "horizontal",
                        "estado": "CONFIRMADO_CASO_REAL",
                        "fontes_ids": ["FONTE-LISTA-A"]}]}
    d["cortes"] = [{"perfil": "SU-001", "comprimento_mm": 760,
                    "quantidade": 1, "angulo": "90"}]
    d["vidros"] = [{"folha": "1", "largura_mm": 350, "altura_mm": 520,
                    "espessura_mm": 6}]
    d["baguetes"] = [{"perfil": "SU-053", "comprimento_mm": 340,
                      "quantidade": 2, "lado_de_encaixe": "interno"}]
    d["acessorios"] = [{"item": "roldana", "quantidade": 4,
                        "posicao": "base de cada folha"}]
    d["folgas"] = [{"entre": "folha e marco lateral", "valor_mm": 3,
                    "medido_por": "paquimetro"}]
    d["sobreposicoes"] = [{"entre": "folha 1 e folha 2", "valor_mm": 25}]
    d["croquis"] = [{"tipo": "croqui", "referencia": "curadoria/campo/a.jpg",
                     "descricao": "rabisco do serralheiro"}]
    d["fontes"] = [{"id_fonte": "FONTE-LISTA-A", "tipo": "lista_de_corte_real",
                    "referencia": "curadoria/campo/lista_a.pdf",
                    "descricao": "lista real", "estado": "CONFIRMADO_CASO_REAL",
                    "responsavel": "Bruno", "data": "2026-08-10"}]
    d["duvidas"] = ["confirmar se a escova é a mesma nos dois trilhos"]

    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.vista.lado_de_referencia == "interno"
    assert caso.vista.posicao_do_fecho == "montante central da folha 1"
    su001 = next(p for p in caso.perfis if p.codigo_perfil == "SU-001")
    assert su001.observacoes_gerais == "trilho duplo"
    ap = su001.aplicacoes[0]
    assert ap.funcao is PapelComponente.MARCO_SUPERIOR
    assert ap.quantidade == 1 and ap.orientacao == "horizontal"
    assert ap.id_componente == "MARCO-SUPERIOR"
    assert caso.cortes[0].comprimento_mm == Decimal("760")
    assert caso.vidros[0].espessura_mm == Decimal("6")
    assert caso.baguetes[0].lado_de_encaixe == "interno"
    assert caso.acessorios[0].quantidade == 4
    assert caso.folgas[0].valor_mm == Decimal("3")
    assert caso.sobreposicoes[0].valor_mm == Decimal("25")
    assert caso.croquis and caso.fontes and caso.duvidas
    assert caso.croquis[0].descricao == "rabisco do serralheiro"
    assert caso.fontes[0].id_fonte == "FONTE-LISTA-A"
    assert caso.estado_recebimento == ESTADO_CASO_RECEBIDO
    # nada se perdeu no caminho
    for secao in ("vista", "perfis", "cortes", "vidros", "baguetes",
                  "acessorios", "folgas", "sobreposicoes", "croquis",
                  "fontes", "duvidas"):
        assert secao in caso.secoes_preenchidas, secao


def test_dados_adicionais_sobrevivem_ao_fluxo_completo(ficha_em_branco):
    """Fluxo inteiro: validar -> converter -> serializar.

    Conteúdo livre tem um lugar declarado. Ele é preservado integralmente e
    marcado como NÃO interpretado — nada ali participa de cálculo."""
    d = copy.deepcopy(ficha_em_branco)
    d["dados_adicionais"] = {"observacao_geral": "serralheiro usou gabarito"}
    d["cortes"] = [{"perfil": "SU-001", "comprimento_mm": 700,
                    "dados_adicionais": {"medido_com": "trena",
                                         "conferido_por": "Anderson"}}]
    assert fontes.validar_estrutura_ficha(d, "x").ok

    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.dados_adicionais == {"observacao_geral":
                                     "serralheiro usou gabarito"}
    assert caso.cortes[0].dados_adicionais == {"medido_com": "trena",
                                               "conferido_por": "Anderson"}

    serializado = caso.para_dict()
    assert serializado["dados_adicionais"]["observacao_geral"] == \
        "serralheiro usou gabarito"
    assert serializado["dados_adicionais_interpretados"] is False
    assert serializado["cortes"][0]["dados_adicionais"]["medido_com"] == "trena"
    assert serializado["cortes"][0]["dados_adicionais_interpretados"] is False
    assert json.dumps(serializado, ensure_ascii=False)


def test_campo_extra_fora_de_dados_adicionais_reprova(ficha_em_branco):
    """A política é uma só: fora do bloco explícito, campo desconhecido
    reprova. 'Preservamos qualquer campo' seria conveniente e perigoso."""
    d = copy.deepcopy(ficha_em_branco)
    d["cortes"] = [{"perfil": "SU-001", "comprimento_mm": 700,
                    "medido_com": "trena"}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    falha = next(f for f in r.falhas if "medido_com" in str(f["alvo"]))
    assert "dados_adicionais" in falha["esperado"]


def test_ficha_apenas_com_folga_e_recebido_parcial(ficha_em_branco):
    """Uma ficha só com folgas medidas trouxe dado de campo real. Chamá-la de
    AGUARDANDO_DADOS apagaria a visita à serralheria."""
    d = copy.deepcopy(ficha_em_branco)
    d["folgas"] = [{"entre": "folha e marco", "valor_mm": 3,
                    "medido_por": "paquimetro"}]
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.estado_recebimento == ESTADO_CASO_PARCIAL
    assert "folgas" in caso.secoes_preenchidas


def test_ficha_apenas_com_foto_e_recebido_parcial(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"id_fonte": "FONTE-FOTO-A", "tipo": "foto",
                    "referencia": "curadoria/campo/frente.jpg",
                    "descricao": "vista interna", "estado": "CONFIRMADO_CASO_REAL",
                    "responsavel": "Bruno", "data": "2026-08-10"}]
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.estado_recebimento == ESTADO_CASO_PARCIAL
    assert caso.fontes and caso.fontes[0].tipo == "foto"


def test_preenchido_nao_e_confirmado(ficha_em_branco):
    """Sem fonte declarada, um campo preenchido é rascunho — não decisão."""
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-001"] = {"aplicacoes": [
        {"funcao": "MARCO_SUPERIOR", "quantidade": 2,
         "orientacao": "horizontal"}]}
    assert len(fontes.extrair_campos_preenchidos(d)) >= 3
    assert fontes.extrair_decisoes_confirmadas(d) == ()

    d["perfis"]["SU-001"]["aplicacoes"][0]["estado"] = "CONFIRMADO_ESPECIALISTA"
    d["perfis"]["SU-001"]["aplicacoes"][0]["fontes_ids"] = ["FONTE-ARB-01"]
    d["fontes"] = [{"id_fonte": "FONTE-ARB-01", "tipo": "especialista_de_dominio",
                    "referencia": "curadoria/handoffs/e4d/estado_inicial_e4d.md",
                    "descricao": "arbitragem", "estado": "CONFIRMADO_ESPECIALISTA",
                    "responsavel": "Bruno", "data": "2026-08-10"}]
    confirmadas = fontes.extrair_decisoes_confirmadas(d)
    assert {c["campo"] for c in confirmadas} == {"funcao", "quantidade",
                                                 "orientacao"}
    assert all(c["responsavel"] == "Bruno" for c in confirmadas)


def test_confirmacao_do_especialista_sem_autoria_nao_conta(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-001"] = {"aplicacoes": [
        {"funcao": "MARCO_SUPERIOR", "estado": "CONFIRMADO_ESPECIALISTA",
         "fontes_ids": ["FONTE-SEM-AUTOR"]}]}
    d["fontes"] = [{"id_fonte": "FONTE-SEM-AUTOR",
                    "tipo": "especialista_de_dominio",
                    "referencia": "curadoria/handoffs/e4d/estado_inicial_e4d.md",
                    "descricao": "sem autor", "estado": "CONFIRMADO_ESPECIALISTA"}]
    assert fontes.extrair_decisoes_confirmadas(d) == ()


def test_componente_confirmado_pelo_especialista_sem_autoria_reprova(biblioteca):
    """Papel de perfil "confirmado pelo especialista" sem dizer quem confirmou
    não pode abrir o cálculo."""
    from dataclasses import replace
    sem_autor = _componente_confirmado(
        fontes=(_fonte(responsavel=None),))
    assert not sem_autor.confirmado
    assert any("autoria" in p for p in sem_autor.pendencias())

    receita = replace(_receita_completa(),
                      componentes=(sem_autor,) + tuple(
                          _componente_confirmado(p) for p in PERFIS[1:]))
    r = validar.validar_prontidao_para_calculo(receita, biblioteca)
    assert not r.ok
    assert any("autoria completa" in str(f["encontrado"]) or "autoria" in f["regra"]
               for f in r.falhas), r.descrever()


def test_receita_de_teste_e_estruturalmente_completa(biblioteca):
    """A fixture dos gates precisa passar na cobertura — senão os testes de
    gate reprovariam por motivo diferente do que querem provar."""
    assert validar.validar_cobertura_estrutural_receita(_receita_completa()).ok


def test_calculo_bloqueado_sem_regras_de_acessorios(biblioteca):
    """Lista de fabricação completa em perfis e vidro, e silenciosa sobre
    quantas roldanas a janela leva, não é lista de fabricação."""
    from dataclasses import replace
    sem_acessorios = replace(_receita_completa(), regras_acessorios=())
    r = validar.validar_prontidao_para_calculo(sem_acessorios, biblioteca)
    assert not r.ok
    assert any("acessório" in f["regra"] for f in r.falhas)

    pendente = replace(_receita_completa(),
                       regras_acessorios=(RegraAcessorio(
                           identificador="X", item="roldanas"),))
    r = validar.validar_prontidao_para_calculo(pendente, biblioteca)
    assert not r.ok
    assert any("quantidade ou posição" in f["regra"] for f in r.falhas)


def test_acessorio_confirmado_exige_quantidade_e_posicao():
    with pytest.raises(ReceitaErro, match="sem quantidade"):
        RegraAcessorio(identificador="X", item="roldanas",
                       estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                       fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))
    with pytest.raises(ReceitaErro, match="sem posição"):
        RegraAcessorio(identificador="X", item="roldanas",
                       quantidade_expressao="PLACEHOLDER",
                       estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                       fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))


def test_tres_casos_duplicados_nao_abrem_producao(biblioteca):
    """Uma fórmula conferida três vezes contra a mesma janela não foi
    conferida."""
    from dataclasses import replace
    repetido = _caso_validado("CASO_A_PEQUENO", "800", "600")
    receita = replace(_receita_completa(),
                      casos_reais=(repetido, repetido, repetido),
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("duplicados" in f["regra"] for f in r.falhas)
    assert any("canônicos ausentes" in f["regra"] for f in r.falhas)


def test_tres_casos_sem_a_b_c_nao_abrem_producao(biblioteca):
    from dataclasses import replace
    receita = replace(_receita_completa(),
                      casos_reais=(_caso_validado("CASO_A_PEQUENO", "800", "600"),
                                   _caso_validado("CASO_B_MEDIO", "1500", "1200")),
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    falha = next(f for f in r.falhas if "canônicos ausentes" in f["regra"])
    assert falha["encontrado"] == ["CASO_C_GRANDE"]


def test_casos_com_dimensoes_identicas_nao_abrem_producao(biblioteca):
    from dataclasses import replace
    receita = replace(_receita_completa(),
                      casos_reais=(_caso_validado("CASO_A_PEQUENO", "1500", "1200"),
                                   _caso_validado("CASO_B_MEDIO", "1500", "1200"),
                                   _caso_validado("CASO_C_GRANDE", "2400", "2100")),
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("dimensões idênticas" in f["regra"] for f in r.falhas)


def test_caso_validado_sem_lista_de_corte_nao_abre_producao(biblioteca):
    from dataclasses import replace
    incompleto = replace(_caso_validado("CASO_C_GRANDE", "2400", "2100"),
                         cortes=())
    receita = replace(_receita_completa(),
                      casos_reais=_TRES_CASOS[:2] + (incompleto,),
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("sem lista de corte" in f["regra"] for f in r.falhas), r.descrever()


def test_aprovacao_como_string_solta_nao_abre_producao(biblioteca):
    """Aprovação sem autor, data e escopo não pode liberar corte de alumínio."""
    from dataclasses import replace
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      aprovacoes=())
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert sum("aprovação do especialista" in f["regra"] for f in r.falhas) == 2

    so_receita = replace(receita, aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),))
    r = validar.validar_prontidao_para_producao(so_receita, biblioteca)
    assert not r.ok, "aprovar a receita não aprova as fórmulas"


@pytest.mark.parametrize("campo", ["responsavel", "data", "escopo", "fonte_id"])
def test_aprovacao_exige_todos_os_campos(campo):
    base = dict(resultado=ResultadoAprovacao.APROVADO, responsavel="Bruno",
                data="2026-08-10", fonte_id="FONTE-APROVACAO",
                escopo=ESCOPO_APROVACAO_RECEITA)
    base[campo] = ""
    with pytest.raises(ReceitaErro):
        AprovacaoEspecialista(**base)


@pytest.mark.parametrize("referencia", [
    "/home/bruno/foto.jpg", "C:/dados/foto.jpg", "C:\\dados\\foto.jpg",
    "../fora-do-repositorio/foto.jpg", "curadoria/../../fora/foto.jpg",
    "~/foto.jpg",
])
def test_referencia_de_arquivo_insegura_e_rejeitada(referencia):
    with pytest.raises(ReceitaErro):
        FonteEvidencia(id_fonte="FONTE-X", tipo="foto", referencia=referencia,
                       descricao="", estado=EstadoConhecimento.PENDENTE)


@pytest.mark.parametrize("referencia,forma", [
    ("https://exemplo.com/catalogo.pdf", "url"),
    ("PEDIDO-2026-0451", "identificador_externo"),
])
def test_identificador_externo_e_url_nao_sao_tratados_como_caminho(referencia,
                                                                   forma):
    """A regra de caminho relativo vale para arquivo; um DOI ou uma URL não são
    caminhos e não podem ser recusados por isso."""
    f = FonteEvidencia(id_fonte="FONTE-X", tipo="software_externo",
                       referencia=referencia, descricao="",
                       estado=EstadoConhecimento.PENDENTE,
                       forma_referencia=forma)
    assert f.referencia == referencia


def test_referencia_relativa_e_aceita():
    f = FonteEvidencia(id_fonte="FONTE-X", tipo="foto",
                       referencia="curadoria/campo/a/frente.jpg",
                       descricao="", estado=EstadoConhecimento.PENDENTE)
    assert f.forma_referencia == "arquivo"


def test_ficha_rejeita_referencia_insegura(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"tipo": "foto", "referencia": "../fora/foto.jpg"}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("referência insegura" in f["regra"] for f in r.falhas)


def test_data_fora_do_formato_reprova(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"tipo": "foto", "referencia": "curadoria/a.jpg",
                    "data": "10/08/2026"}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("data fora do formato" in f["regra"] for f in r.falhas)


def test_manifesto_e4c_nao_e_catalogo_nem_tabela_de_fabricacao():
    """O manifesto prova que os perfis existem — não diz nada sobre corte,
    montagem ou papel na janela. Classificá-lo como catálogo criaria
    procedência enganosa."""
    fonte = receita_mod.FONTE_PROMOCAO_E4C
    assert fonte.tipo == "manifesto_promocao"
    assert fonte.tipo not in ("catalogo", "tabela_de_fabricacao")
    assert fonte.estado is EstadoConhecimento.CONFIRMADO_BIBLIOTECA_OFICIAL
    assert "NÃO PROVA" in fonte.descricao
    for palavra in ("papel", "quantidade", "orientação", "corte", "vidro",
                    "acessório"):
        assert palavra in fonte.descricao


def test_pyyaml_declarado_na_fronteira_correta():
    """`composicao/` é pacote de aplicação; declarar sua dependência num
    arquivo que diz "nunca dependências de runtime" seria contradição."""
    runtime = (RAIZ / "requirements.txt").read_text(encoding="utf-8").lower()
    curadoria = (RAIZ / "requirements-curadoria.txt").read_text(encoding="utf-8").lower()
    assert "pyyaml" in runtime
    assert "pyyaml" not in curadoria


def test_cli_recomendada_funciona_com_as_dependencias_documentadas():
    """Prova de ambiente: o comando que o handoff recomenda roda de verdade."""
    import importlib
    assert importlib.import_module("yaml")
    from composicao import cli
    assert cli.main(["validar-ficha", str(MODELO_FICHA)]) == 0


def test_modelo_de_ficha_continua_valido_e_totalmente_pendente(ficha_em_branco):
    """O modelo distribuído tem de continuar válido e sem nenhuma resposta —
    um modelo com campo preenchido induziria resposta."""
    assert ficha_em_branco["versao_ficha"] == fontes.VERSAO_FICHA_SUPORTADA
    assert ficha_em_branco["tipologia"]["codigo"] == fontes.CODIGO_TIPOLOGIA_ESPERADO
    r = fontes.validar_estrutura_ficha(ficha_em_branco, "modelo")
    assert r.ok, r.descrever()
    assert fontes.extrair_campos_preenchidos(ficha_em_branco) == ()
    assert fontes.extrair_decisoes_confirmadas(ficha_em_branco) == ()
    caso = fontes.converter_ficha_em_caso_real(ficha_em_branco, "modelo")
    assert caso.secoes_preenchidas == ()
    assert caso.estado_recebimento == ESTADO_CASO_AGUARDANDO


# ===========================================================================
# Fechamento estrutural do schema
#
# Evidência tem identidade, cada afirmação carrega a sua, aprovação tem
# resultado semântico, e validar é um ato registrado — não uma string.
# ===========================================================================

def _ficha_com_fontes(ficha_em_branco, *fontes_brutas):
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = list(fontes_brutas)
    return d


def _fonte_bruta(id_fonte, tipo="foto", **kw):
    base = {"id_fonte": id_fonte, "tipo": tipo,
            "referencia": f"curadoria/campo/{id_fonte.lower()}.jpg",
            "descricao": "evidência de teste",
            "estado": "CONFIRMADO_CASO_REAL"}
    base.update(kw)
    return base


# ---- identidade da evidência ----------------------------------------------

def test_duas_fontes_do_mesmo_tipo_continuam_distintas(ficha_em_branco):
    """Um índice por `tipo` faria a segunda foto apagar a primeira."""
    d = _ficha_com_fontes(ficha_em_branco,
                          _fonte_bruta("FONTE-FOTO-FRENTE"),
                          _fonte_bruta("FONTE-FOTO-VERSO"))
    assert fontes.validar_estrutura_ficha(d, "x").ok
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert len(caso.fontes) == 2
    assert {f.id_fonte for f in caso.fontes} == {"FONTE-FOTO-FRENTE",
                                                 "FONTE-FOTO-VERSO"}
    assert {f.tipo for f in caso.fontes} == {"foto"}
    assert len(caso.indice_fontes) == 2


def test_fonte_sem_id_reprova(ficha_em_branco):
    """Sem ID não há como citar — e gerar um automaticamente inventaria a
    identidade da evidência."""
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"tipo": "foto", "referencia": "curadoria/campo/a.jpg"}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("fonte sem id_fonte" in f["regra"] for f in r.falhas)


@pytest.mark.parametrize("id_fonte", ["fonte-001", "F1", "FONTE 001", "001"])
def test_id_fonte_fora_do_formato_reprova(ficha_em_branco, id_fonte):
    d = _ficha_com_fontes(ficha_em_branco, _fonte_bruta(id_fonte))
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("id_fonte" in str(f["alvo"]) for f in r.falhas)


def test_id_fonte_duplicado_reprova(ficha_em_branco):
    d = _ficha_com_fontes(ficha_em_branco,
                          _fonte_bruta("FONTE-A"),
                          _fonte_bruta("FONTE-A", tipo="croqui"))
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("id_fonte duplicado" in f["regra"] for f in r.falhas)


def test_referencia_a_fonte_inexistente_reprova(ficha_em_branco):
    d = _ficha_com_fontes(ficha_em_branco, _fonte_bruta("FONTE-A"))
    d["cortes"] = [{"perfil": "SU-001", "comprimento_mm": 700,
                    "estado": "CONFIRMADO_CASO_REAL",
                    "fontes_ids": ["FONTE-QUE-NAO-EXISTE"]}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("fonte inexistente" in f["regra"] for f in r.falhas)


def test_fonte_repetida_na_mesma_afirmacao_reprova(ficha_em_branco):
    d = _ficha_com_fontes(ficha_em_branco, _fonte_bruta("FONTE-A"))
    d["folgas"] = [{"entre": "folha e marco", "valor_mm": 3,
                    "estado": "CONFIRMADO_CASO_REAL",
                    "fontes_ids": ["FONTE-A", "FONTE-A"]}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("fonte repetida" in f["regra"] for f in r.falhas)


def test_uma_fonte_serve_a_varias_afirmacoes(ficha_em_branco):
    d = _ficha_com_fontes(ficha_em_branco,
                          _fonte_bruta("FONTE-LISTA", tipo="lista_de_corte_real"))
    d["cortes"] = [{"perfil": "SU-001", "comprimento_mm": 700,
                    "estado": "CONFIRMADO_CASO_REAL",
                    "fontes_ids": ["FONTE-LISTA"]},
                   {"perfil": "SU-002", "comprimento_mm": 500,
                    "estado": "CONFIRMADO_CASO_REAL",
                    "fontes_ids": ["FONTE-LISTA"]}]
    assert fontes.validar_estrutura_ficha(d, "x").ok
    assert len(fontes.extrair_decisoes_confirmadas(d)) >= 4


def test_ordem_das_fontes_nao_muda_o_resultado(ficha_em_branco):
    a, b = _fonte_bruta("FONTE-A"), _fonte_bruta("FONTE-B", tipo="croqui")
    d1 = _ficha_com_fontes(ficha_em_branco, a, b)
    d2 = _ficha_com_fontes(ficha_em_branco, b, a)
    for d in (d1, d2):
        d["folgas"] = [{"entre": "folha e marco", "valor_mm": 3,
                        "estado": "CONFIRMADO_CASO_REAL",
                        "fontes_ids": ["FONTE-B"]}]
    assert (fontes.validar_estrutura_ficha(d1, "x").ok
            == fontes.validar_estrutura_ficha(d2, "x").ok)
    assert (fontes.extrair_decisoes_confirmadas(d1)
            == fontes.extrair_decisoes_confirmadas(d2))


def test_decisao_de_perfil_usa_a_fonte_pelo_id(ficha_em_branco):
    """Duas fontes `especialista_de_dominio`: só a citada vale."""
    d = _ficha_com_fontes(
        ficha_em_branco,
        _fonte_bruta("FONTE-ESP-SEM-AUTOR", tipo="especialista_de_dominio",
                     referencia="curadoria/campo/rascunho.md",
                     estado="CONFIRMADO_ESPECIALISTA"),
        _fonte_bruta("FONTE-ESP-COM-AUTOR", tipo="especialista_de_dominio",
                     referencia="curadoria/campo/arbitragem.md",
                     estado="CONFIRMADO_ESPECIALISTA",
                     responsavel="Bruno", data="2026-08-10"))
    d["perfis"]["SU-001"] = {"aplicacoes": [
        {"funcao": "MARCO_SUPERIOR", "estado": "CONFIRMADO_ESPECIALISTA",
         "fontes_ids": ["FONTE-ESP-SEM-AUTOR"]}]}
    assert fontes.extrair_decisoes_confirmadas(d) == (), \
        "a fonte citada não tem autoria — a outra não pode salvá-la"

    d["perfis"]["SU-001"]["aplicacoes"][0]["fontes_ids"] = ["FONTE-ESP-COM-AUTOR"]
    confirmadas = fontes.extrair_decisoes_confirmadas(d)
    assert [c["campo"] for c in confirmadas] == ["funcao"]
    assert confirmadas[0]["fontes_ids"] == ["FONTE-ESP-COM-AUTOR"]


# ---- evidência por afirmação ----------------------------------------------

@pytest.mark.parametrize("secao,item", [
    ("cortes", {"perfil": "SU-001", "comprimento_mm": 700}),
    ("vidros", {"folha": "1", "largura_mm": 500, "altura_mm": 900}),
    ("folgas", {"entre": "folha e marco", "valor_mm": 3}),
])
def test_item_confirmado_sem_fonte_nao_conta(ficha_em_branco, secao, item):
    """Estado confirmado sem evidência é palavra solta."""
    d = copy.deepcopy(ficha_em_branco)
    d[secao] = [dict(item, estado="CONFIRMADO_CASO_REAL")]
    assert fontes.validar_estrutura_ficha(d, "x").ok, "sem fonte não é erro de forma"
    assert fontes.extrair_decisoes_confirmadas(d) == ()
    assert len(fontes.extrair_campos_preenchidos(d)) >= 1


def test_vista_confirmada_sem_fonte_nao_conta(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["vista"]["lado_de_referencia"] = "interno"
    d["vista"]["estado"] = "CONFIRMADO_ESPECIALISTA"
    assert fontes.extrair_decisoes_confirmadas(d) == ()


def test_item_com_fonte_valida_aparece_em_decisoes(ficha_em_branco):
    d = _ficha_com_fontes(ficha_em_branco,
                          _fonte_bruta("FONTE-LISTA-A",
                                       tipo="lista_de_corte_real"))
    d["cortes"] = [{"perfil": "SU-001", "comprimento_mm": 1460, "quantidade": 1,
                    "estado": "CONFIRMADO_CASO_REAL",
                    "fontes_ids": ["FONTE-LISTA-A"]}]
    confirmadas = fontes.extrair_decisoes_confirmadas(d)
    campos = {c["campo"] for c in confirmadas}
    assert campos == {"perfil", "comprimento_mm", "quantidade"}
    assert all(c["escopo"] == "cortes[0]" for c in confirmadas)


def test_folga_sem_estado_aparece_so_em_campos_preenchidos(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["folgas"] = [{"entre": "folha e marco", "valor_mm": 3}]
    assert fontes.extrair_decisoes_confirmadas(d) == ()
    assert any(p["escopo"] == "folgas" for p in
               fontes.extrair_campos_preenchidos(d))


def test_dimensoes_do_caso_confirmadas_com_evidencia(ficha_em_branco):
    d = _ficha_com_fontes(ficha_em_branco,
                          _fonte_bruta("FONTE-MEDICAO", tipo="medicao_fisica"))
    d["caso_real"] = {"identificador": "CASO_A_PEQUENO",
                      "largura_total_mm": 800, "altura_total_mm": 600,
                      "estado": "CONFIRMADO_CASO_REAL",
                      "fontes_ids": ["FONTE-MEDICAO"]}
    confirmadas = fontes.extrair_decisoes_confirmadas(d)
    assert {c["campo"] for c in confirmadas} == {"largura_total_mm",
                                                 "altura_total_mm"}


# ---- aprovação com resultado semântico ------------------------------------

@pytest.mark.parametrize("resultado", [ResultadoAprovacao.REPROVADO,
                                       ResultadoAprovacao.REVOGADO])
def test_aprovacao_negativa_nao_abre_producao(biblioteca, resultado):
    """`REPROVADO` nunca é aprovação — antes, a mera existência do registro
    abria o mesmo portão que um parecer positivo."""
    from dataclasses import replace
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA, resultado),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("não é APROVADO" in f["regra"] for f in r.falhas)


def test_aprovacoes_conflitantes_nao_abrem_producao(biblioteca):
    """Duas aprovações do mesmo escopo não se resolvem pela ordem da tupla."""
    from dataclasses import replace
    conflito = (_aprovacao(ESCOPO_APROVACAO_RECEITA),
                _aprovacao(ESCOPO_APROVACAO_RECEITA,
                           ResultadoAprovacao.REVOGADO),
                _aprovacao(ESCOPO_APROVACAO_FORMULAS))
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      aprovacoes=conflito)
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("mais de uma aprovação" in f["regra"] for f in r.falhas)

    invertida = replace(receita, aprovacoes=(conflito[1], conflito[0],
                                             conflito[2]))
    r2 = validar.validar_prontidao_para_producao(invertida, biblioteca)
    assert not r2.ok
    assert [f["regra"] for f in r.falhas] == [f["regra"] for f in r2.falhas], \
        "a ordem não pode mudar o veredito"


def test_aprovacoes_por_escopo_devolve_todas():
    from composicao.modelos import aprovacoes_por_escopo
    from dataclasses import replace
    receita = replace(_receita_completa(),
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_RECEITA,
                                             ResultadoAprovacao.REPROVADO)))
    assert len(aprovacoes_por_escopo(receita, ESCOPO_APROVACAO_RECEITA)) == 2
    assert aprovacoes_por_escopo(receita, ESCOPO_APROVACAO_FORMULAS) == ()


def test_responsavel_da_aprovacao_divergente_da_fonte_reprova(biblioteca):
    """Assinatura e evidência têm de ser da mesma pessoa."""
    from dataclasses import replace
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA,
                                             responsavel="Anderson"),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("assinada por" in str(f["encontrado"]) for f in r.falhas)


def test_aprovacao_com_fonte_que_nao_e_de_especialista_reprova(biblioteca):
    from dataclasses import replace
    foto = FonteEvidencia(id_fonte="FONTE-FOTO", tipo="foto",
                          referencia="curadoria/campo/a.jpg", descricao="",
                          estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                          responsavel="Bruno", data="2026-08-10")
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      fontes=(FONTE_APROVACAO, foto),
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA,
                                             fonte_id="FONTE-FOTO"),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("especialista_de_dominio" in str(f["encontrado"])
               for f in r.falhas)


def test_escopo_de_aprovacao_desconhecido_reprova():
    with pytest.raises(ReceitaErro, match="escopo de aprovação desconhecido"):
        _aprovacao("qualquer_coisa")


# ---- validação estruturada do caso ----------------------------------------

def test_caso_nao_pode_se_declarar_validado():
    """`VALIDADO` deixou de ser uma string que qualquer código escreve."""
    with pytest.raises(ReceitaErro, match="NÃO se escreve"):
        CasoRealFabricacao(identificador="CASO_A_PEQUENO",
                           estado_recebimento=ESTADO_CASO_VALIDADO)


def test_caso_sem_validacao_estruturada_nao_abre_producao(biblioteca):
    from dataclasses import replace
    sem_validacao = tuple(replace(c, validacao=None) for c in _TRES_CASOS)
    assert all(not validar.caso_validado(c, PERFIS) for c in sem_validacao)
    assert all(validar.estado_validacao_caso(c, PERFIS) == ESTADO_CASO_RECEBIDO
               for c in sem_validacao)
    receita = replace(_receita_completa(), casos_reais=sem_validacao,
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("canônicos ausentes" in f["regra"] for f in r.falhas)


def test_caso_com_validacao_aprovada_e_considerado_validado(biblioteca):
    caso = _TRES_CASOS[0]
    assert caso.validacao.aprovada
    assert validar.estado_validacao_caso(caso, PERFIS) == ESTADO_CASO_VALIDADO
    assert validar.caso_validado(caso, PERFIS)
    # O caso está validado; a produção continua bloqueada por falta de
    # resultado calculado — são coisas diferentes.
    assert validar.caso_validado(_TRES_CASOS_HOMOLOGAVEIS[0], PERFIS)
    r = validar.validar_prontidao_para_producao(_receita_homologavel(),
                                                biblioteca)
    assert not r.ok
    assert any("nenhum resultado calculado" in f["regra"] for f in r.falhas)


def test_validacao_reprovada_nao_torna_o_caso_validado():
    caso = _caso_validado("CASO_A_PEQUENO", "800", "600",
                          validacao=_validacao_aprovada(
                              ResultadoAprovacao.REPROVADO))
    assert not caso.validacao_declarada_aprovada
    assert not validar.caso_validado(caso, PERFIS)
    assert validar.estado_validacao_caso(caso, PERFIS) == ESTADO_CASO_RECEBIDO


def test_validacao_de_caso_exige_responsavel_data_e_fontes():
    with pytest.raises(ReceitaErro, match="sem responsável"):
        ValidacaoCasoReal(resultado=ResultadoAprovacao.APROVADO,
                          responsavel="", data="2026-08-10",
                          fontes_ids=("FONTE-A",))
    with pytest.raises(ReceitaErro, match="sem fontes"):
        ValidacaoCasoReal(resultado=ResultadoAprovacao.APROVADO,
                          responsavel="Bruno", data="2026-08-10",
                          fontes_ids=())


def test_validacao_citando_fonte_inexistente_reprova_producao(biblioteca):
    from dataclasses import replace
    ruim = replace(_TRES_CASOS[0],
                   validacao=ValidacaoCasoReal(
                       resultado=ResultadoAprovacao.APROVADO,
                       responsavel="Bruno", data="2026-08-10",
                       fontes_ids=("FONTE-INEXISTENTE",)))
    receita = replace(_receita_completa(),
                      casos_reais=(ruim,) + _TRES_CASOS[1:],
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("fonte inexistente" in str(f["encontrado"]) for f in r.falhas), \
        r.descrever()


# ---- datas reais -----------------------------------------------------------

@pytest.mark.parametrize("data", ["2026-02-30", "2026-13-10", "2026-00-01",
                                  "2026-04-31", "10/08/2026", "20260810"])
def test_data_invalida_reprova(data):
    """Conferir só o formato aceitaria 2026-02-30 — que parece data e não é."""
    from composicao.modelos import data_invalida
    assert data_invalida(data) is not None
    with pytest.raises(ReceitaErro):
        _fonte(data=data)


@pytest.mark.parametrize("data", ["2026-08-10", "2024-02-29", "2026-12-31"])
def test_data_valida_e_aceita(data):
    from composicao.modelos import data_invalida
    assert data_invalida(data) is None
    assert _fonte(data=data).data == data


def test_data_invalida_na_ficha_reprova(ficha_em_branco):
    d = _ficha_com_fontes(ficha_em_branco,
                          _fonte_bruta("FONTE-A", data="2026-02-30"))
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("não é uma data real" in f["regra"] for f in r.falhas)


def test_validacao_e_aprovacao_recusam_data_irreal():
    with pytest.raises(ReceitaErro, match="data real"):
        ValidacaoCasoReal(resultado=ResultadoAprovacao.APROVADO,
                          responsavel="Bruno", data="2026-02-30",
                          fontes_ids=("FONTE-A",))


# ---- modelo YAML -----------------------------------------------------------

def test_modelo_yaml_declara_os_campos_do_schema(ficha_em_branco):
    """O modelo distribuído tem de mostrar onde vai id_fonte, estado,
    fontes_ids e dados_adicionais — senão ninguém os preencheria."""
    texto = MODELO_FICHA.read_text(encoding="utf-8")
    for campo in ("id_fonte", "estado:", "fontes_ids", "dados_adicionais"):
        assert campo in texto, campo
    assert ficha_em_branco["caso_real"]["fontes_ids"] == []
    assert ficha_em_branco["vista"]["dados_adicionais"] == {}
    for p in PERFIS:
        assert ficha_em_branco["perfis"][p]["fontes_ids"] == []
    assert ficha_em_branco["dados_adicionais"] == {}


def test_modelo_yaml_vazio_continua_valido_e_sem_decisoes(ficha_em_branco):
    r = fontes.validar_estrutura_ficha(ficha_em_branco, "modelo")
    assert r.ok, r.descrever()
    assert fontes.extrair_decisoes_confirmadas(ficha_em_branco) == ()
    caso = fontes.converter_ficha_em_caso_real(ficha_em_branco, "modelo")
    assert caso.identificador is None
    assert caso.estado_recebimento == ESTADO_CASO_AGUARDANDO
    assert caso.secoes_preenchidas == ()


def test_modelo_yaml_nao_cria_valor_tecnico(ficha_em_branco):
    """Nenhum número, papel, quantidade ou fórmula nasce do modelo."""
    caso = fontes.converter_ficha_em_caso_real(ficha_em_branco, "modelo")
    assert caso.largura_total_mm is None and caso.altura_total_mm is None
    assert caso.estado_dimensoes is None and caso.fontes_ids_dimensoes == ()
    assert caso.vista.vazia
    assert all(p.vazio for p in caso.perfis)
    assert all(p.aplicacoes == () for p in caso.perfis)
    for secao in ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                  "sobreposicoes", "croquis", "fontes", "duvidas"):
        assert getattr(caso, secao) == (), secao
    assert caso.validacao is None


# ===========================================================================
# Invariantes de evidência
#
# Existir não é sustentar. Uma fonte PENDENTE não confirma nada, um catálogo
# não prova o que foi medido, e um objeto vazio numa lista não é uma peça.
# ===========================================================================

def _fonte_com(id_fonte, tipo, estado, responsavel="Bruno", data="2026-08-10"):
    return FonteEvidencia(
        id_fonte=id_fonte, tipo=tipo,
        referencia=f"curadoria/campo/{id_fonte.lower()}.pdf",
        descricao="evidência de teste",
        estado=EstadoConhecimento(estado), responsavel=responsavel, data=data)


def _indice(*fontes):
    return {f.id_fonte: f for f in fontes}


# ---- matriz de compatibilidade --------------------------------------------

@pytest.mark.parametrize("estado_fonte", ["PENDENTE", "HIPOTESE"])
def test_fonte_sem_confirmacao_nao_sustenta_afirmacao(estado_fonte):
    """Uma afirmação firme apoiada em fonte pendente diria que a janela foi
    medida quando ninguém mediu."""
    from composicao.modelos import incompatibilidades_da_afirmacao
    f = _fonte_com("FONTE-X", "lista_de_corte_real", estado_fonte)
    problemas = incompatibilidades_da_afirmacao(
        EstadoConhecimento.CONFIRMADO_CASO_REAL, ("FONTE-X",), _indice(f))
    assert problemas
    assert any(estado_fonte in p for p in problemas)


def test_caso_real_com_fonte_so_de_catalogo_reprova():
    from composicao.modelos import incompatibilidades_da_afirmacao
    f = _fonte_com("FONTE-CAT", "catalogo", "CONFIRMADO_CATALOGO")
    problemas = incompatibilidades_da_afirmacao(
        EstadoConhecimento.CONFIRMADO_CASO_REAL, ("FONTE-CAT",), _indice(f))
    assert any("nenhuma fonte compatível" in p for p in problemas)


def test_especialista_com_fonte_de_caso_real_reprova():
    from composicao.modelos import incompatibilidades_da_afirmacao
    f = _fonte_com("FONTE-MED", "medicao_fisica", "CONFIRMADO_CASO_REAL")
    problemas = incompatibilidades_da_afirmacao(
        EstadoConhecimento.CONFIRMADO_ESPECIALISTA, ("FONTE-MED",), _indice(f))
    assert any("nenhuma fonte compatível" in p for p in problemas)


@pytest.mark.parametrize("estado,tipo", [
    ("CONFIRMADO_CATALOGO", "catalogo"),
    ("CONFIRMADO_BIBLIOTECA_OFICIAL", "manifesto_promocao"),
    ("CONFIRMADO_ESPECIALISTA", "especialista_de_dominio"),
    ("CONFIRMADO_CASO_REAL", "medicao_fisica"),
    ("DERIVADO_DE_REGRA_APROVADA", "tabela_de_fabricacao"),
])
def test_fonte_compativel_confirma(estado, tipo):
    from composicao.modelos import (afirmacao_confirmada,
                                    fonte_compativel_com_afirmacao)
    f = _fonte_com("FONTE-OK", tipo, estado)
    assert fonte_compativel_com_afirmacao(f, EstadoConhecimento(estado))
    assert afirmacao_confirmada(EstadoConhecimento(estado), ("FONTE-OK",),
                                _indice(f))


def test_especialista_sem_autoria_nao_e_fonte_compativel():
    from composicao.modelos import fonte_compativel_com_afirmacao
    f = _fonte_com("FONTE-ESP", "especialista_de_dominio",
                   "CONFIRMADO_ESPECIALISTA", responsavel=None)
    assert not fonte_compativel_com_afirmacao(
        f, EstadoConhecimento.CONFIRMADO_ESPECIALISTA)


def test_uma_fonte_pendente_entre_duas_nao_passa_em_silencio():
    """A compatível não apaga o problema da outra: citar uma fonte pendente é
    citar algo que ainda não foi confirmado."""
    from composicao.modelos import incompatibilidades_da_afirmacao
    boa = _fonte_com("FONTE-BOA", "lista_de_corte_real", "CONFIRMADO_CASO_REAL")
    ruim = _fonte_com("FONTE-RUIM", "foto", "PENDENTE")
    problemas = incompatibilidades_da_afirmacao(
        EstadoConhecimento.CONFIRMADO_CASO_REAL,
        ("FONTE-BOA", "FONTE-RUIM"), _indice(boa, ruim))
    assert problemas
    assert any("FONTE-RUIM" in p and "PENDENTE" in p for p in problemas)


def test_ficha_com_fonte_incompativel_reprova_a_estrutura(ficha_em_branco):
    """Não basta sumir da lista de confirmações: tem de aparecer como erro."""
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"id_fonte": "FONTE-CAT", "tipo": "catalogo",
                    "referencia": "dados_exemplo/catalogo.pdf",
                    "descricao": "catálogo", "estado": "CONFIRMADO_CATALOGO"}]
    d["folgas"] = [{"entre": "folha e marco", "valor_mm": 3,
                    "estado": "CONFIRMADO_CASO_REAL",
                    "fontes_ids": ["FONTE-CAT"]}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("evidência não sustenta o estado" in f["regra"] for f in r.falhas)
    assert fontes.extrair_decisoes_confirmadas(d) == ()


# ---- integridade do caso real ---------------------------------------------

def _caso_com(**kw):
    return _caso_validado("CASO_A_PEQUENO", "800", "600", **kw)


@pytest.mark.parametrize("cortes,motivo", [
    ((CorteReal(),), "campos mínimos"),
    ((CorteReal(perfil="SU-001", estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                fontes_ids=("FONTE-CASO-01",)),), "campos mínimos"),
    ((CorteReal(perfil="SU-001", comprimento_mm=Decimal("700"),
                estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                fontes_ids=("FONTE-CASO-01",)),), "campos mínimos"),
    ((CorteReal(perfil="SU-001", comprimento_mm=Decimal("700"), quantidade=1),),
     "evidência apta"),
    ((CorteReal(perfil="SU-001", comprimento_mm=Decimal("700"), quantidade=1,
                estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                fontes_ids=("FONTE-FANTASMA",)),), "evidência apta"),
])
def test_corte_incompleto_nao_valida_o_caso(cortes, motivo):
    """`bool(caso.cortes)` aceitava uma tupla com objetos vazios: o gate abria
    porque a lista não estava vazia, sem uma única peça descrita."""
    caso = _caso_com(cortes=cortes)
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert not r.ok
    assert any(motivo in f["regra"] for f in r.falhas), r.descrever()


def test_corte_de_perfil_fora_do_microlote_nao_valida_o_caso():
    caso = _caso_com(cortes=(_corte_confirmado(perfil="SU-999"),))
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert not r.ok
    assert any("fora do microlote" in f["regra"] for f in r.falhas)


@pytest.mark.parametrize("vidros", [
    (VidroReal(),),
    (VidroReal(folha="1", largura_mm=Decimal("500"), altura_mm=Decimal("900"),
               estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
               fontes_ids=("FONTE-CASO-01",)),),   # sem espessura
])
def test_vidro_incompleto_nao_valida_o_caso(vidros):
    caso = _caso_com(vidros=vidros)
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert not r.ok
    assert any("campos mínimos" in f["regra"] for f in r.falhas)


@pytest.mark.parametrize("kw", [
    {"estado_dimensoes": None},
    {"estado_dimensoes": EstadoConhecimento.HIPOTESE},
    {"fontes_ids_dimensoes": ()},
    {"fontes_ids_dimensoes": ("FONTE-FANTASMA",)},
])
def test_dimensoes_sem_evidencia_apta_nao_validam_o_caso(kw):
    caso = _caso_com(**kw)
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert not r.ok
    assert any("dimensões sem evidência apta" in f["regra"] for f in r.falhas)


def test_validacao_aprovada_nao_salva_caso_incompleto(biblioteca):
    """As duas condições são necessárias ao mesmo tempo: dados íntegros E
    validação aprovada."""
    from dataclasses import replace
    vazio = _caso_com(cortes=(CorteReal(),))
    assert vazio.validacao_declarada_aprovada, "a validação está declarada"
    assert not validar.caso_validado(vazio, PERFIS), "declarar não é validar"
    assert not validar.validar_integridade_caso_real(vazio, PERFIS).ok

    receita = replace(_receita_completa(),
                      casos_reais=(vazio,) + _TRES_CASOS[1:],
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("campos mínimos" in f["regra"] for f in r.falhas), r.descrever()


def test_validacao_com_fonte_duplicada_reprova():
    with pytest.raises(ReceitaErro, match="fonte repetida"):
        ValidacaoCasoReal(resultado=ResultadoAprovacao.APROVADO,
                          responsavel="Bruno", data="2026-08-10",
                          fontes_ids=("FONTE-CASO-01", "FONTE-CASO-01"))


def test_responsavel_da_validacao_divergente_da_fonte_reprova():
    caso = _caso_com(validacao=ValidacaoCasoReal(
        resultado=ResultadoAprovacao.APROVADO, responsavel="Anderson",
        data="2026-08-10", fontes_ids=("FONTE-CASO-01",)))
    problemas = validar.problemas_da_validacao_caso(caso)
    assert any("responsável da validação" in p for p in problemas)
    assert not validar.caso_validado(caso, PERFIS)


def test_data_da_validacao_divergente_da_evidencia_reprova():
    caso = _caso_com(validacao=ValidacaoCasoReal(
        resultado=ResultadoAprovacao.APROVADO, responsavel="Bruno",
        data="2026-09-01", fontes_ids=("FONTE-CASO-01",)))
    problemas = validar.problemas_da_validacao_caso(caso)
    assert any("data da validação" in p for p in problemas)
    assert not validar.caso_validado(caso, PERFIS)


def test_caso_integro_passa_na_validacao_completa():
    caso = _caso_validado("CASO_A_PEQUENO", "800", "600")
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert r.ok, r.descrever()


def test_item_parcial_permanece_no_caso_mas_nao_valida(biblioteca):
    """Dado parcial é registro legítimo; o que ele não pode é virar prova."""
    from dataclasses import replace
    parcial = _caso_com(folgas=(FolgaReal(entre="folha e marco"),))
    assert parcial.folgas, "o item continua guardado"
    r = validar.validar_integridade_caso_real(parcial, PERFIS)
    assert not r.ok
    assert any("folgas[0]" in f["alvo"] for f in r.falhas)


# ---- aprovação vinculada ao registro central -------------------------------

def test_aprovacao_com_fonte_fora_da_receita_reprova(biblioteca):
    from dataclasses import replace
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      fontes=(),      # a fonte da aprovação não está registrada
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("não está registrada" in str(f["encontrado"]) for f in r.falhas)


def test_aprovacao_com_fonte_pendente_reprova(biblioteca):
    from dataclasses import replace
    pendente = FonteEvidencia(
        id_fonte="FONTE-APROVACAO", tipo="especialista_de_dominio",
        referencia="curadoria/handoffs/e4d/estado_inicial_e4d.md",
        descricao="rascunho", estado=EstadoConhecimento.PENDENTE,
        responsavel="Bruno", data="2026-08-10")
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      fontes=(pendente,),
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("PENDENTE" in str(f["encontrado"]) for f in r.falhas)


def test_aprovacao_com_data_divergente_da_evidencia_reprova(biblioteca):
    from dataclasses import replace
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA,
                                             data="2026-09-15"),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("datas divergentes" in str(f["encontrado"]) for f in r.falhas)


def test_duas_fontes_com_mesmo_id_e_conteudo_diferente_reprovam():
    from composicao.modelos import indice_fontes_receita
    from dataclasses import replace
    outra = replace(FONTE_APROVACAO, descricao="outra coisa")
    receita = replace(_receita_completa(),
                      fontes=(FONTE_APROVACAO,),
                      casos_reais=(_caso_validado("CASO_A_PEQUENO", "800", "600",
                                                  fontes=(FONTE_CASO, outra)),))
    with pytest.raises(ReceitaErro, match="duas fontes diferentes"):
        indice_fontes_receita(receita)


def test_indice_de_fontes_nao_depende_da_ordem():
    from composicao.modelos import indice_fontes_receita
    from dataclasses import replace
    r1 = replace(_receita_completa(), fontes=(FONTE_APROVACAO, FONTE_CASO))
    r2 = replace(_receita_completa(), fontes=(FONTE_CASO, FONTE_APROVACAO))
    assert indice_fontes_receita(r1) == indice_fontes_receita(r2)


# ---- imutabilidade profunda ------------------------------------------------

def test_alterar_o_dict_original_nao_altera_o_modelo():
    """`frozen=True` congela os atributos, não o conteúdo de um dict."""
    original = {"nota": "primeira", "medidas": [1, 2]}
    corte = CorteReal(perfil="SU-001", dados_adicionais=original)
    original["nota"] = "alterada depois"
    original["medidas"].append(3)
    assert corte.dados_adicionais["nota"] == "primeira"
    assert corte.dados_adicionais["medidas"] == (1, 2)


def test_mutar_dados_adicionais_do_modelo_falha():
    corte = CorteReal(perfil="SU-001",
                      dados_adicionais={"nota": "x", "aninhado": {"a": 1}})
    with pytest.raises(TypeError):
        corte.dados_adicionais["nota"] = "y"
    with pytest.raises(TypeError):
        corte.dados_adicionais["aninhado"]["a"] = 2


def test_mutar_o_retorno_de_para_dict_nao_altera_o_modelo():
    caso = _caso_com(dados_adicionais={"obs": "original", "lista": [1]})
    d = caso.para_dict()
    d["dados_adicionais"]["obs"] = "mexido"
    d["dados_adicionais"]["lista"].append(2)
    assert caso.dados_adicionais["obs"] == "original"
    assert caso.dados_adicionais["lista"] == (1,)
    assert caso.para_dict()["dados_adicionais"]["obs"] == "original"


def test_congelamento_e_recursivo_em_listas_e_conjuntos():
    from composicao.modelos import (congelar_dados_adicionais,
                                    descongelar_dados_adicionais)
    congelado = congelar_dados_adicionais(
        {"a": [1, {"b": {2, 3}}], "c": ("x",)})
    assert isinstance(congelado["a"], tuple)
    assert isinstance(congelado["a"][1]["b"], frozenset)
    devolvido = descongelar_dados_adicionais(congelado)
    assert devolvido["a"][0] == 1
    assert isinstance(devolvido, dict) and isinstance(devolvido["a"], list)
    devolvido["a"].append("novo")
    assert len(congelado["a"]) == 2


def test_serializacao_permanece_deterministica():
    a = _caso_com(dados_adicionais={"z": 1, "a": 2})
    b = _caso_com(dados_adicionais={"a": 2, "z": 1})
    assert a.dados_adicionais == b.dados_adicionais
    assert json.dumps(a.para_dict(), sort_keys=True) == \
        json.dumps(b.para_dict(), sort_keys=True)


# ---- o modelo continua inerte ---------------------------------------------

def test_modelo_vazio_e_gates_permanecem(receita, biblioteca, ficha_em_branco):
    assert fontes.validar_estrutura_ficha(ficha_em_branco, "modelo").ok
    assert fontes.extrair_decisoes_confirmadas(ficha_em_branco) == ()
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    assert rel["gates"]["calculo"]["aberto"] is False
    assert rel["gates"]["producao"]["aberto"] is False
    # Os componentes confirmados vêm da arbitragem de topologia, nunca de uma
    # ficha em branco — e não abrem gate nenhum.
    assert rel["regras"]["confirmadas"] == []
    assert rel["acessorios"]["confirmados"] == []


# ===========================================================================
# Invariantes globais da receita
#
# A matriz de evidência vale para a receita inteira, a tipologia tem cobertura
# obrigatória, VALIDADO é estado derivado, e nenhuma coleção guarda referência
# externa.
# ===========================================================================

FONTE_CATALOGO = FonteEvidencia(
    id_fonte="FONTE-CATALOGO", tipo="catalogo",
    referencia="CATALOGO-ALCOA-TESTE", descricao="catálogo",
    estado=EstadoConhecimento.CONFIRMADO_CATALOGO,
    forma_referencia="identificador_externo")


# ---- compatibilidade aplicada à receita inteira ----------------------------

def test_componente_de_caso_real_com_catalogo_nao_confirma():
    """A ficha do especialista era cobrada pela matriz e a receita não: um
    componente CONFIRMADO_CASO_REAL apoiado só num catálogo passava."""
    comp = _componente_confirmado(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                                  fontes=(FONTE_CATALOGO,))
    assert not comp.confirmado
    assert any("nenhuma fonte compatível" in p for p in comp.pendencias())


def test_componente_de_especialista_com_fonte_de_caso_nao_confirma():
    comp = _componente_confirmado(
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        fontes=(FONTE_CASO,))
    assert not comp.confirmado
    assert any("nenhuma fonte compatível" in p for p in comp.pendencias())


def test_componente_com_fonte_compativel_confirma():
    comp = _componente_confirmado()
    assert comp.confirmado and comp.pendencias() == ()


@pytest.mark.parametrize("estado_fonte", ["PENDENTE", "HIPOTESE"])
def test_regra_dimensional_com_fonte_nao_confirmada_nao_calcula(estado_fonte):
    ruim = FonteEvidencia(
        id_fonte="FONTE-RASCUNHO", tipo="lista_de_corte_real",
        referencia="curadoria/campo/rascunho.pdf", descricao="",
        estado=EstadoConhecimento(estado_fonte))
    regra = RegraDimensional(
        identificador="R", descricao="d", alvo="largura_folha",
        expressao="PLACEHOLDER_DE_TESTE", variaveis=("largura_total_mm",),
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL, fontes=(ruim,))
    assert not regra.calculavel
    assert any(estado_fonte in p for p in regra.impedimentos())


def test_regra_derivada_nao_se_sustenta_em_manifesto():
    """Uma fórmula derivada não é provada pelo manifesto da promoção: ele diz
    que os perfis existem, não como a janela se monta."""
    manifesto = FonteEvidencia(
        id_fonte="FONTE-MANIF", tipo="manifesto_promocao",
        referencia="curadoria/promocoes/e4c/manifesto_promocao_e4b.json",
        descricao="", estado=EstadoConhecimento.DERIVADO_DE_REGRA_APROVADA)
    regra = RegraDimensional(
        identificador="R", descricao="d", alvo="altura_folha",
        expressao="PLACEHOLDER_DE_TESTE", variaveis=("altura_total_mm",),
        estado=EstadoConhecimento.DERIVADO_DE_REGRA_APROVADA,
        fontes=(manifesto,))
    assert not regra.calculavel
    assert any("nenhuma fonte compatível" in p for p in regra.impedimentos())


def test_regra_confirmada_sem_variaveis_nao_calcula():
    """Fórmula sem variáveis declaradas é constante disfarçada."""
    regra = RegraDimensional(
        identificador="R", descricao="d", alvo="largura_folha",
        expressao="PLACEHOLDER_DE_TESTE", variaveis=(),
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes=(FONTE_CASO,))
    assert not regra.calculavel
    assert any("variáveis" in p for p in regra.impedimentos())


def test_acessorio_com_fonte_hipotetica_nao_calcula():
    hipotese = FonteEvidencia(
        id_fonte="FONTE-HIP", tipo="foto", referencia="curadoria/campo/a.jpg",
        descricao="", estado=EstadoConhecimento.HIPOTESE)
    regra = RegraAcessorio(
        identificador="A", item="roldanas",
        quantidade_expressao="PLACEHOLDER_DE_TESTE", posicao="base",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL, fontes=(hipotese,))
    assert not regra.calculavel
    assert any("HIPOTESE" in p for p in regra.impedimentos())


def test_validar_fontes_reporta_o_item_o_estado_e_a_fonte(biblioteca):
    from dataclasses import replace
    ruim = _componente_confirmado(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                                  fontes=(FONTE_CATALOGO,))
    receita = replace(_receita_completa(),
                      componentes=(ruim,) + tuple(_componente_confirmado(p)
                                                  for p in PERFIS[1:]))
    r = validar.validar_fontes(receita)
    assert not r.ok
    falha = r.falhas[0]
    assert falha["alvo"] == ruim.identificador
    assert falha["encontrado"]["estado"] == "CONFIRMADO_CASO_REAL"
    assert "FONTE-CATALOGO:catalogo/CONFIRMADO_CATALOGO" in \
        falha["encontrado"]["fontes"]
    assert "compatíveis" in falha["esperado"]


# ---- cobertura estrutural --------------------------------------------------

def test_receita_preliminar_oficial_tem_cobertura_completa(receita):
    r = validar.validar_cobertura_estrutural_receita(receita)
    assert r.ok, r.descrever()


def test_receita_sem_inventario_reprova():
    from dataclasses import replace
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(), perfis_disponiveis=()))
    assert not r.ok
    assert any("ausentes do inventário" in f["regra"] for f in r.falhas)


def test_receita_sem_ocorrencias_passa_a_cobertura_mas_nao_calcula(biblioteca):
    """Inventário completo e nenhuma ocorrência é o estado preliminar legítimo."""
    from dataclasses import replace
    preliminar = replace(_receita_completa(), componentes=())
    assert validar.validar_cobertura_estrutural_receita(preliminar).ok
    assert not validar.validar_prontidao_para_calculo(preliminar, biblioteca).ok


def test_receita_com_sete_perfis_no_inventario_reprova():
    from dataclasses import replace
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(),
                perfis_disponiveis=tuple(fontes.referencia_oficial(p)
                                         for p in PERFIS[:7])))
    assert not r.ok
    falha = next(f for f in r.falhas if "ausentes do inventário" in f["regra"])
    assert falha["encontrado"] == ["SU-102"]


def test_perfil_duplicado_no_inventario_reprova():
    from dataclasses import replace
    inv = tuple(fontes.referencia_oficial(p) for p in PERFIS) + (
        fontes.referencia_oficial("SU-001"),)
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(), perfis_disponiveis=inv))
    assert not r.ok
    assert any("duplicado no inventário" in f["regra"] for f in r.falhas)


def test_identificador_de_componente_duplicado_reprova():
    from dataclasses import replace
    comps = tuple(_componente_confirmado(p, identificador="MESMO-ID")
                  for p in PERFIS)
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(), componentes=comps))
    assert not r.ok
    assert any("identificador de componente duplicado" in f["regra"]
               for f in r.falhas)


def test_perfil_fora_do_microlote_reprova():
    from dataclasses import replace
    from composicao.modelos import ReferenciaPerfilOficial
    intruso = ReferenciaPerfilOficial("SU-999", "GEO-SU-999", "ALCOA-SU-999")
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(),
                perfis_disponiveis=tuple(fontes.referencia_oficial(p)
                                         for p in PERFIS) + (intruso,)))
    assert not r.ok
    assert any("fora do microlote" in f["regra"] for f in r.falhas)


def test_componente_com_perfil_fora_do_inventario_reprova():
    from dataclasses import replace
    from composicao.modelos import ReferenciaPerfilOficial
    intruso = ComponenteReceita(
        identificador="TESTE:SU-999",
        perfil=ReferenciaPerfilOficial("SU-999", "GEO-SU-999", "ALCOA-SU-999"))
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(),
                componentes=_receita_completa().componentes + (intruso,)))
    assert not r.ok
    assert any("fora do inventário" in f["regra"] for f in r.falhas)


def test_referencia_geo_divergente_reprova():
    from dataclasses import replace
    from composicao.modelos import ReferenciaPerfilOficial
    torto = ReferenciaPerfilOficial("SU-001", "GEO-SU-005", "ALCOA-SU-001")
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(),
                perfis_disponiveis=(torto,) + tuple(
                    fontes.referencia_oficial(p) for p in PERFIS[1:])))
    assert not r.ok
    assert any("referência GEO divergente" in f["regra"] for f in r.falhas)


@pytest.mark.parametrize("campo,valor", [
    ("quantidade_folhas", 3), ("quantidade_folhas", 1), ("sistema", "Gold")])
def test_tipologia_divergente_reprova(campo, valor):
    from dataclasses import replace
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(), **{campo: valor}))
    assert not r.ok
    assert any("divergente" in f["regra"] for f in r.falhas)


def test_alvo_dimensional_ausente_reprova():
    from dataclasses import replace
    completa = _receita_completa()
    r = validar.validar_cobertura_estrutural_receita(
        replace(completa, regras_vidro=()))
    assert not r.ok
    falha = next(f for f in r.falhas if "alvo dimensional base ausente" in f["regra"])
    assert falha["encontrado"] == ["largura_vidro", "altura_vidro"]


def test_alvo_dimensional_duplicado_reprova():
    from dataclasses import replace
    completa = _receita_completa()
    r = validar.validar_cobertura_estrutural_receita(
        replace(completa,
                regras_vidro=completa.regras_vidro + (_regra_confirmada(
                    "largura_vidro"),)))
    assert not r.ok
    assert any("alvo dimensional duplicado" in f["regra"] for f in r.falhas)
    assert any("identificador de regra duplicado" in f["regra"]
               for f in r.falhas)


def test_acessorio_obrigatorio_ausente_reprova():
    from dataclasses import replace
    completa = _receita_completa()
    r = validar.validar_cobertura_estrutural_receita(
        replace(completa, regras_acessorios=completa.regras_acessorios[:-1]))
    assert not r.ok
    falha = next(f for f in r.falhas if "acessório base ausente" in f["regra"])
    assert falha["encontrado"] == ["fixacoes"]


def test_acessorio_duplicado_reprova():
    from dataclasses import replace
    completa = _receita_completa()
    r = validar.validar_cobertura_estrutural_receita(
        replace(completa,
                regras_acessorios=completa.regras_acessorios
                + (_regra_acessorio_confirmada("roldanas"),)))
    assert not r.ok
    assert any("acessório duplicado" in f["regra"] for f in r.falhas)


def test_cobertura_incompleta_fecha_ate_a_visualizacao(receita, biblioteca):
    """Preliminar pode ter tudo pendente; não pode estar incompleta."""
    from dataclasses import replace
    mutilada = replace(receita,
                       perfis_disponiveis=receita.perfis_disponiveis[:5])
    r = validar.validar_prontidao_para_visualizacao(mutilada, biblioteca)
    assert not r.ok
    assert any("ausentes do inventário" in f["regra"] for f in r.falhas)


# ---- VALIDADO é estado derivado -------------------------------------------

def _fonte_de_validacao(**kw):
    base = dict(id_fonte="FONTE-CASO-01", tipo="lista_de_corte_real",
                referencia="curadoria/campo/lista_a.pdf", descricao="conferência",
                estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                responsavel="Bruno", data="2026-08-10")
    base.update(kw)
    return FonteEvidencia(**base)


@pytest.mark.parametrize("kw,motivo", [
    ({"estado": EstadoConhecimento.PENDENTE}, "está PENDENTE"),
    ({"tipo": "catalogo", "estado": EstadoConhecimento.CONFIRMADO_CATALOGO},
     "nenhuma fonte apta"),
    ({"tipo": "manifesto_promocao",
      "estado": EstadoConhecimento.CONFIRMADO_BIBLIOTECA_OFICIAL},
     "nenhuma fonte apta"),
    ({"responsavel": None}, "nenhuma fonte apta"),
])
def test_fonte_inapta_nao_valida_o_caso(kw, motivo):
    """Uma foto prova que a janela existe; ela não registra que alguém
    conferiu a lista de corte contra a peça."""
    caso = _caso_com(fontes=(_fonte_de_validacao(**kw),))
    problemas = validar.problemas_da_validacao_caso(caso)
    assert any(motivo in p for p in problemas), problemas
    assert not validar.caso_validado(caso, PERFIS)


def test_fonte_apta_valida_o_caso_quando_os_dados_sao_integros():
    caso = _caso_validado("CASO_A_PEQUENO", "800", "600")
    assert validar.problemas_da_validacao_caso(caso) == ()
    assert validar.caso_validado(caso, PERFIS)


def test_fonte_de_especialista_tambem_valida_o_caso():
    caso = _caso_com(fontes=(_fonte_de_validacao(
        tipo="especialista_de_dominio",
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA),))
    assert validar.problemas_da_validacao_caso(caso) == ()


def test_validacao_aprovada_nao_valida_caso_com_dados_incompletos():
    caso = _caso_com(cortes=())
    assert caso.validacao_declarada_aprovada
    assert validar.problemas_da_validacao_caso(caso) == (), \
        "a validação em si está bem formada"
    assert not validar.caso_validado(caso, PERFIS), \
        "mas os dados não sustentam"


# ---- recebimento parcial × completo ---------------------------------------

def _ficha_com_caso(ficha_em_branco, cortes, vidros):
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"id_fonte": "FONTE-LISTA", "tipo": "lista_de_corte_real",
                    "referencia": "curadoria/campo/lista.pdf",
                    "descricao": "lista", "estado": "CONFIRMADO_CASO_REAL",
                    "responsavel": "Bruno", "data": "2026-08-10"}]
    d["caso_real"] = {"identificador": "CASO_A_PEQUENO",
                      "largura_total_mm": 800, "altura_total_mm": 600,
                      "estado": "CONFIRMADO_CASO_REAL",
                      "fontes_ids": ["FONTE-LISTA"]}
    d["cortes"], d["vidros"] = cortes, vidros
    return d


CORTE_MINIMO = {"perfil": "SU-001", "comprimento_mm": 700, "quantidade": 1,
                "estado": "CONFIRMADO_CASO_REAL", "fontes_ids": ["FONTE-LISTA"]}
VIDRO_MINIMO = {"folha": "1", "largura_mm": 500, "altura_mm": 900,
                "espessura_mm": 6, "estado": "CONFIRMADO_CASO_REAL",
                "fontes_ids": ["FONTE-LISTA"]}


@pytest.mark.parametrize("cortes,vidros", [
    ([{}], [VIDRO_MINIMO]),
    ([CORTE_MINIMO], [{}]),
    ([{"perfil": "SU-001"}], [VIDRO_MINIMO]),
    ([CORTE_MINIMO], [{"folha": "1", "largura_mm": 500, "altura_mm": 900}]),
])
def test_item_vazio_mantem_recebido_parcial(ficha_em_branco, cortes, vidros):
    """`bool(cortes) and bool(vidros)` classificava como recebida por completo
    uma ficha sem uma única peça descrita."""
    d = _ficha_com_caso(ficha_em_branco, cortes, vidros)
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.estado_recebimento == ESTADO_CASO_PARCIAL
    assert not caso.completo_para_derivacao


def test_corte_e_vidro_minimos_tornam_recebido_nao_validado(ficha_em_branco):
    d = _ficha_com_caso(ficha_em_branco, [CORTE_MINIMO], [VIDRO_MINIMO])
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.estado_recebimento == ESTADO_CASO_RECEBIDO
    assert caso.completo_para_derivacao
    # recebido completo ainda NÃO é validado
    assert caso.validacao is None
    assert not validar.caso_validado(caso, PERFIS)


# ---- imutabilidade de todas as coleções ------------------------------------

def test_lista_externa_de_componentes_nao_altera_receita():
    comps = [_componente_confirmado(p) for p in PERFIS]
    receita = ReceitaTipologia(codigo="T", nome="t", sistema="Suprema",
                               quantidade_folhas=2, componentes=comps)
    comps.append(_componente_confirmado("SU-001", identificador="OUTRO"))
    assert len(receita.componentes) == 8
    assert isinstance(receita.componentes, tuple)


def test_lista_externa_de_casos_nao_altera_receita():
    casos = [_caso_validado("CASO_A_PEQUENO", "800", "600")]
    receita = ReceitaTipologia(codigo="T", nome="t", sistema="Suprema",
                               quantidade_folhas=2, casos_reais=casos)
    casos.append(_caso_validado("CASO_B_MEDIO", "1500", "1200"))
    assert len(receita.casos_reais) == 1


def test_lista_externa_de_fontes_nao_altera_componente():
    fs = [FONTE_APROVACAO]
    comp = _componente_confirmado(fontes=fs)
    fs.append(FONTE_CASO)
    assert len(comp.fontes) == 1


def test_lista_externa_de_variaveis_nao_altera_regra():
    variaveis = ["largura_total_mm"]
    regra = RegraDimensional(identificador="R", descricao="d",
                             alvo="largura_folha", variaveis=variaveis)
    variaveis.append("intrusa")
    assert regra.variaveis == ("largura_total_mm",)


def test_lista_externa_de_fontes_ids_nao_altera_validacao():
    ids = ["FONTE-CASO-01"]
    val = ValidacaoCasoReal(resultado=ResultadoAprovacao.APROVADO,
                            responsavel="Bruno", data="2026-08-10",
                            fontes_ids=ids)
    ids.append("FONTE-INTRUSA")
    assert val.fontes_ids == ("FONTE-CASO-01",)


def test_lista_externa_de_cortes_nao_altera_caso():
    cortes = [_corte_confirmado()]
    caso = _caso_com(cortes=cortes)
    cortes.append(_corte_confirmado(perfil="SU-002"))
    assert len(caso.cortes) == 1


@pytest.mark.parametrize("obj,campo", [
    ("componente", "fontes"), ("componente", "observacoes"),
    ("regra", "variaveis"), ("regra", "fontes"),
    ("caso", "cortes"), ("caso", "fontes"), ("caso", "duvidas"),
    ("receita", "componentes"), ("receita", "casos_reais"),
    ("receita", "aprovacoes"),
])
def test_colecoes_do_modelo_nao_sao_mutaveis(obj, campo):
    alvos = {
        "componente": _componente_confirmado(),
        "regra": _regra_confirmada("largura_folha"),
        "caso": _caso_validado("CASO_A_PEQUENO", "800", "600"),
        "receita": _receita_completa(),
    }
    colecao = getattr(alvos[obj], campo)
    assert isinstance(colecao, tuple)
    with pytest.raises(AttributeError):
        colecao.append("intruso")


def test_receita_recusa_elemento_de_tipo_errado():
    with pytest.raises(ReceitaErro, match="tipo inesperado"):
        ReceitaTipologia(codigo="T", nome="t", sistema="Suprema",
                         quantidade_folhas=2, componentes=("nao é componente",))


def test_como_tupla_recusa_texto_e_mapeamento():
    from composicao.modelos import como_tupla
    assert como_tupla(None) == ()
    assert como_tupla(["a", "b"]) == ("a", "b")
    with pytest.raises(ReceitaErro, match="texto"):
        como_tupla("SU-001", "perfis")
    with pytest.raises(ReceitaErro, match="mapeamento"):
        como_tupla({"a": 1}, "perfis")


def test_replace_continua_funcionando():
    from dataclasses import replace
    comp = _componente_confirmado()
    outro = replace(comp, quantidade=4)
    assert outro.quantidade == 4 and comp.quantidade == 1
    assert isinstance(outro.fontes, tuple)

    receita = replace(_receita_completa(), estado="OUTRO")
    assert receita.estado == "OUTRO"
    assert len(receita.componentes) == 8
    assert len(receita.perfis_disponiveis) == 8


def test_serializacao_continua_deterministica_apos_congelamento():
    a = _caso_validado("CASO_A_PEQUENO", "800", "600")
    b = _caso_validado("CASO_A_PEQUENO", "800", "600")
    assert json.dumps(a.para_dict(), sort_keys=True) == \
        json.dumps(b.para_dict(), sort_keys=True)


# ===========================================================================
# Contrato de campo — perfil × ocorrência, números, prova e artefatos
# ===========================================================================

# ---- perfil não é componente ----------------------------------------------

def test_mesmo_perfil_pode_aparecer_em_dois_componentes():
    """SU-003 pode ser marco esquerdo E direito. A arquitetura precisa aceitar
    a possibilidade — sem afirmar que é assim que a Suprema se monta."""
    esquerdo = _componente_confirmado(
        "SU-003", identificador="MARCO-LATERAL-ESQUERDO",
        papel=PapelComponente.MARCO_LATERAL_ESQUERDO, orientacao="vertical")
    direito = _componente_confirmado(
        "SU-003", identificador="MARCO-LATERAL-DIREITO",
        papel=PapelComponente.MARCO_LATERAL_DIREITO, orientacao="vertical")
    from dataclasses import replace
    receita = replace(_receita_completa(), componentes=(esquerdo, direito))
    assert validar.validar_cobertura_estrutural_receita(receita).ok
    assert len(receita.componentes_do_perfil("SU-003")) == 2
    assert esquerdo.confirmado and direito.confirmado


def test_identificador_de_componente_continua_unico():
    from dataclasses import replace
    dois = (_componente_confirmado("SU-003", identificador="MESMO"),
            _componente_confirmado("SU-041", identificador="MESMO"))
    r = validar.validar_cobertura_estrutural_receita(
        replace(_receita_completa(), componentes=dois))
    assert not r.ok
    assert any("identificador de componente duplicado" in f["regra"]
               for f in r.falhas)


def test_um_perfil_rende_varias_ocorrencias(receita):
    """Oito perfis no inventário, vinte peças na janela: perfil não é peça."""
    assert len(receita.perfis_disponiveis) == 8
    assert {p: len(receita.componentes_do_perfil(p)) for p in PERFIS} == {
        "SU-001": 1, "SU-002": 1, "SU-003": 2, "SU-039": 2,
        "SU-040": 1, "SU-041": 1, "SU-053": 4, "SU-102": 8}


def test_ficha_aceita_varias_aplicacoes_do_mesmo_perfil(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-003"] = {"aplicacoes": [
        {"id_componente": "MARCO-ESQ", "funcao": "MARCO_LATERAL_ESQUERDO",
         "quantidade": 1, "orientacao": "vertical"},
        {"id_componente": "MARCO-DIR", "funcao": "MARCO_LATERAL_DIREITO",
         "quantidade": 1, "orientacao": "vertical"}]}
    assert fontes.validar_estrutura_ficha(d, "x").ok
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    su003 = next(p for p in caso.perfis if p.codigo_perfil == "SU-003")
    assert len(su003.aplicacoes) == 2
    assert {a.id_componente for a in su003.aplicacoes} == {"MARCO-ESQ",
                                                           "MARCO-DIR"}


def test_ficha_recusa_id_componente_duplicado(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-003"] = {"aplicacoes": [{"id_componente": "MESMO"}]}
    d["perfis"]["SU-041"] = {"aplicacoes": [{"id_componente": "MESMO"}]}
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("id_componente duplicado" in f["regra"] for f in r.falhas)


# ---- listas base são cobertura mínima, não universo fechado ---------------

def _regra_adicional(alvo="corte_travessa_extra"):
    return RegraDimensional(
        identificador=f"TESTE:{alvo}", descricao="regra descoberta em campo",
        alvo=alvo, origem_do_alvo="DESCOBERTO_EM_CAMPO")


def test_alvo_adicional_registrado_nao_reprova():
    """A serralheria pode revelar uma regra que ninguém previu; recusá-la por
    não estar na lista jogaria fora conhecimento novo."""
    from dataclasses import replace
    completa = _receita_completa()
    r = validar.validar_cobertura_estrutural_receita(
        replace(completa,
                regras_corte=completa.regras_corte + (_regra_adicional(),)))
    assert r.ok, r.descrever()


def test_alvo_adicional_sem_procedencia_reprova():
    with pytest.raises(ReceitaErro, match="origem_do_alvo"):
        RegraDimensional(identificador="X", descricao="d",
                         alvo="corte_travessa_extra")


def test_alvo_adicional_sem_descricao_reprova():
    with pytest.raises(ReceitaErro, match="sem descrição"):
        RegraDimensional(identificador="X", descricao="",
                         alvo="corte_travessa_extra",
                         origem_do_alvo="DESCOBERTO_EM_CAMPO")


def test_acessorio_adicional_registrado_nao_reprova():
    from dataclasses import replace
    completa = _receita_completa()
    extra = RegraAcessorio(identificador="TESTE:acessorio:trinco",
                           item="trinco", descricao="trinco visto na visita",
                           origem_do_item="DESCOBERTO_EM_CAMPO")
    r = validar.validar_cobertura_estrutural_receita(
        replace(completa,
                regras_acessorios=completa.regras_acessorios + (extra,)))
    assert r.ok, r.descrever()


def test_acessorio_adicional_sem_procedencia_reprova():
    with pytest.raises(ReceitaErro, match="origem_do_item"):
        RegraAcessorio(identificador="X", item="trinco")


# ---- números protegidos no modelo -----------------------------------------

@pytest.mark.parametrize("valor", [Decimal("0"), Decimal("-1"),
                                   Decimal("NaN"), Decimal("Infinity"),
                                   Decimal("-Infinity"), 700, "700", 700.0])
def test_medida_invalida_reprova_na_construcao(valor):
    """O YAML já cobrava isso; objeto construído em código passava direto."""
    with pytest.raises(ReceitaErro):
        CorteReal(perfil="SU-001", comprimento_mm=valor)


@pytest.mark.parametrize("valor", [Decimal("Infinity"), Decimal("0")])
def test_vidro_com_medida_invalida_reprova(valor):
    with pytest.raises(ReceitaErro):
        VidroReal(folha="1", largura_mm=valor)


def test_folga_negativa_reprova():
    from composicao.modelos import FolgaReal
    with pytest.raises(ReceitaErro, match="positiva"):
        FolgaReal(entre="folha e marco", valor_mm=Decimal("-3"))


@pytest.mark.parametrize("valor", [0, -1, True, False, 1.5, "1"])
def test_quantidade_invalida_reprova_na_construcao(valor):
    """`isinstance(True, int)` é verdadeiro em Python: sem checagem explícita,
    `quantidade=True` viraria uma peça."""
    with pytest.raises(ReceitaErro):
        CorteReal(perfil="SU-001", quantidade=valor)


@pytest.mark.parametrize("valor", [0, True, -2])
def test_quantidade_invalida_no_componente_reprova(valor):
    with pytest.raises(ReceitaErro):
        _componente_confirmado(quantidade=valor)


def test_medida_do_caso_protegida_no_modelo():
    with pytest.raises(ReceitaErro):
        CasoRealFabricacao(identificador="CASO_A_PEQUENO",
                           largura_total_mm=Decimal("NaN"))


# ---- estudo × homologação --------------------------------------------------

def test_um_corte_e_um_vidro_servem_para_estudo(biblioteca):
    caso = _caso_validado("CASO_A_PEQUENO", "800", "600",
                          id_fonte="FONTE-CASO-A")
    assert validar.validar_caso_para_estudo(caso, PERFIS).ok
    assert caso.completo_para_derivacao


def test_um_corte_e_um_vidro_nao_homologam_a_receita():
    """Integridade responde 'os dados estão completos?'. Homologação responde
    'a receita produz ESTA janela?' — são perguntas diferentes."""
    caso = _caso_validado("CASO_A_PEQUENO", "800", "600",
                          id_fonte="FONTE-CASO-A")
    r = validar.validar_caso_contra_receita(caso, _receita_completa())
    assert not r.ok
    assert any("sem corte correspondente" in f["regra"] for f in r.falhas)


def test_corte_sem_componente_id_nao_homologa():
    from dataclasses import replace
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0],
                   cortes=(replace(_TRES_CASOS_HOMOLOGAVEIS[0].cortes[0],
                                   componente_id=None),)
                   + _TRES_CASOS_HOMOLOGAVEIS[0].cortes[1:])
    r = validar.validar_caso_contra_receita(caso, _receita_completa())
    assert not r.ok
    assert any("sem componente_id" in f["regra"] for f in r.falhas)


def test_corte_com_componente_desconhecido_nao_homologa():
    from dataclasses import replace
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0],
                   cortes=_TRES_CASOS_HOMOLOGAVEIS[0].cortes
                   + (_corte_confirmado(componente_id="NAO-EXISTE",
                                        id_fonte="FONTE-CASO-A"),))
    r = validar.validar_caso_contra_receita(caso, _receita_completa())
    assert not r.ok
    assert any("componente desconhecido" in f["regra"] for f in r.falhas)


def test_corte_com_perfil_diferente_do_componente_nao_homologa():
    from dataclasses import replace
    torto = replace(_TRES_CASOS_HOMOLOGAVEIS[0].cortes[0], perfil="SU-041")
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0],
                   cortes=(torto,) + _TRES_CASOS_HOMOLOGAVEIS[0].cortes[1:])
    r = validar.validar_caso_contra_receita(caso, _receita_completa())
    assert not r.ok
    assert any("perfil do corte diverge" in f["regra"] for f in r.falhas)


def test_quantidade_agregada_divergente_nao_homologa():
    from dataclasses import replace
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0],
                   cortes=(replace(_TRES_CASOS_HOMOLOGAVEIS[0].cortes[0],
                                   quantidade=5),)
                   + _TRES_CASOS_HOMOLOGAVEIS[0].cortes[1:])
    r = validar.validar_caso_contra_receita(caso, _receita_completa())
    assert not r.ok
    falha = next(f for f in r.falhas if "quantidade agregada" in f["regra"])
    assert falha["encontrado"] == 5 and falha["esperado"] == 1


def test_acessorio_calculado_ausente_nao_homologa():
    from dataclasses import replace
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0], acessorios=())
    r = validar.validar_caso_contra_receita(caso, _receita_completa())
    assert not r.ok
    assert any("acessório calculado ausente" in f["regra"] for f in r.falhas)


def test_caso_completo_homologa_a_receita():
    r = validar.validar_caso_contra_receita(_TRES_CASOS_HOMOLOGAVEIS[0],
                                            _receita_completa())
    assert r.ok, r.descrever()


def test_producao_exige_conferencia_por_caso(biblioteca):
    from dataclasses import replace
    sem_conferencia = replace(_receita_homologavel(), conferencias=())
    r = validar.validar_prontidao_para_producao(sem_conferencia, biblioteca)
    assert not r.ok
    assert any("sem conferência" in str(f["encontrado"]) for f in r.falhas)


def test_conferencia_negativa_nao_abre_producao(biblioteca):
    from dataclasses import replace
    negativa = replace(
        _receita_homologavel(),
        conferencias=(_conferencia("CASO_A_PEQUENO",
                                   resultado=ResultadoAprovacao.REPROVADO),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(negativa, biblioteca)
    assert not r.ok
    assert any("conferência REPROVADO" in str(f["encontrado"])
               for f in r.falhas)


def test_conferencia_com_divergencia_nao_abre_producao(biblioteca):
    from dataclasses import replace
    com_divergencia = replace(
        _receita_homologavel(),
        conferencias=(_conferencia("CASO_A_PEQUENO",
                                   divergencias=("marco superior 3 mm maior",)),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(com_divergencia, biblioteca)
    assert not r.ok
    assert any("divergências" in str(f["encontrado"]) for f in r.falhas)


# ---- independência documental ----------------------------------------------

def test_tres_casos_com_mesmo_exemplar_reprovam():
    """Medidas diferentes não provam três janelas: a mesma lista de corte pode
    ser reaproveitada com números trocados."""
    from dataclasses import replace
    mesmos = tuple(replace(c, id_exemplar="OP-UNICA")
                   for c in _TRES_CASOS_HOMOLOGAVEIS)
    r = validar.validar_independencia_dos_casos(mesmos)
    assert not r.ok
    assert any("mesmo exemplar" in f["regra"] for f in r.falhas)


def test_caso_sem_id_exemplar_reprova():
    from dataclasses import replace
    sem = tuple(replace(c, id_exemplar=None) for c in _TRES_CASOS_HOMOLOGAVEIS)
    r = validar.validar_independencia_dos_casos(sem)
    assert not r.ok
    assert any("sem id_exemplar" in f["regra"] for f in r.falhas)


def test_mesma_fonte_primaria_nos_tres_casos_reprova():
    from dataclasses import replace
    compartilhada = FonteEvidencia(
        id_fonte="FONTE-UNICA", tipo="lista_de_corte_real",
        referencia="curadoria/campo/unica/lista.pdf", descricao="",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        responsavel="Bruno", data="2026-08-10")
    mesmos = tuple(replace(c, fontes=(compartilhada,))
                   for c in _TRES_CASOS_HOMOLOGAVEIS)
    r = validar.validar_independencia_dos_casos(mesmos)
    assert not r.ok
    assert any("artefato primário reutilizado" in f["regra"] for f in r.falhas)


def test_assinatura_documental_repetida_reprova():
    from dataclasses import replace
    clone = replace(_TRES_CASOS_HOMOLOGAVEIS[0],
                    identificador="CASO_B_MEDIO")
    r = validar.validar_independencia_dos_casos(
        (_TRES_CASOS_HOMOLOGAVEIS[0], clone))
    assert not r.ok
    assert any("assinatura documental repetida" in f["regra"]
               for f in r.falhas)


def test_tres_exemplares_independentes_passam():
    r = validar.validar_independencia_dos_casos(_TRES_CASOS_HOMOLOGAVEIS)
    assert r.ok, r.descrever()


def test_assinatura_muda_com_o_exemplar():
    from composicao.modelos import assinatura_documental_caso
    from dataclasses import replace
    a = _TRES_CASOS_HOMOLOGAVEIS[0]
    b = replace(a, id_exemplar="OP-OUTRA")
    assert assinatura_documental_caso(a) != assinatura_documental_caso(b)
    assert assinatura_documental_caso(a) == assinatura_documental_caso(a)


# ---- artefatos de evidência ------------------------------------------------

@pytest.fixture
def artefato(tmp_path):
    """Arquivo real dentro de uma 'raiz de repositório' isolada."""
    import hashlib
    raiz = tmp_path / "repo"
    (raiz / "curadoria" / "campo").mkdir(parents=True)
    alvo = raiz / "curadoria" / "campo" / "foto.jpg"
    alvo.write_bytes(b"conteudo da foto")
    return raiz, "curadoria/campo/foto.jpg", hashlib.sha256(
        b"conteudo da foto").hexdigest(), len(b"conteudo da foto")


def _fonte_arquivo(referencia, sha256=None, tamanho=None,
                   estado=EstadoConhecimento.CONFIRMADO_CASO_REAL):
    return FonteEvidencia(
        id_fonte="FONTE-ARTEFATO", tipo="foto", referencia=referencia,
        descricao="", estado=estado, responsavel="Bruno", data="2026-08-10",
        sha256=sha256, tamanho_bytes=tamanho)


def test_artefato_existente_com_hash_correto_passa(artefato):
    raiz, ref, sha, tamanho = artefato
    r = validar.validar_artefato_de_evidencia(
        _fonte_arquivo(ref, sha, tamanho), raiz)
    assert r.ok, r.descrever()


def test_artefato_inexistente_reprova(artefato):
    raiz, _, sha, _ = artefato
    r = validar.validar_artefato_de_evidencia(
        _fonte_arquivo("curadoria/campo/nao_existe.jpg", sha), raiz)
    assert not r.ok
    assert any("inexistente" in f["regra"] for f in r.falhas)


def test_artefato_alterado_depois_do_registro_reprova(artefato):
    """Caminho bem formado não prova nada: o arquivo pode ter sido trocado."""
    raiz, ref, sha, tamanho = artefato
    (raiz / ref).write_bytes(b"conteudo trocado depois")
    r = validar.validar_artefato_de_evidencia(
        _fonte_arquivo(ref, sha, tamanho), raiz)
    assert not r.ok
    assert any("alterado após o registro" in f["regra"] for f in r.falhas)


def test_artefato_confirmado_sem_sha256_reprova(artefato):
    raiz, ref, _, _ = artefato
    r = validar.validar_artefato_de_evidencia(_fonte_arquivo(ref), raiz)
    assert not r.ok
    assert any("sem sha256" in f["regra"] for f in r.falhas)


def test_sha256_com_formato_invalido_reprova():
    for ruim in ("abc", "Z" * 64, "A" * 64, "0" * 63):
        with pytest.raises(ReceitaErro, match="sha256"):
            _fonte_arquivo("curadoria/campo/foto.jpg", ruim)


def test_tamanho_divergente_reprova(artefato):
    raiz, ref, sha, tamanho = artefato
    r = validar.validar_artefato_de_evidencia(
        _fonte_arquivo(ref, sha, tamanho + 10), raiz)
    assert not r.ok
    assert any("tamanho do artefato divergente" in f["regra"] for f in r.falhas)


def test_artefato_pendente_nao_exige_arquivo(artefato):
    raiz, _, _, _ = artefato
    r = validar.validar_artefato_de_evidencia(
        _fonte_arquivo("curadoria/campo/ainda_nao_existe.jpg",
                       estado=EstadoConhecimento.PENDENTE), raiz)
    assert r.ok


@pytest.mark.parametrize("forma,referencia", [
    ("url", "https://exemplo.com/catalogo.pdf"),
    ("identificador_externo", "PEDIDO-2026-0451"),
])
def test_url_e_identificador_externo_nao_exigem_arquivo(artefato, forma,
                                                        referencia):
    raiz, _, _, _ = artefato
    fonte = FonteEvidencia(
        id_fonte="FONTE-EXT", tipo="software_externo", referencia=referencia,
        descricao="", estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        responsavel="Bruno", data="2026-08-10", forma_referencia=forma)
    assert validar.validar_artefato_de_evidencia(fonte, raiz).ok


def test_artefatos_do_caso_e_da_receita(artefato):
    from dataclasses import replace
    raiz, ref, sha, tamanho = artefato
    boa = _fonte_arquivo(ref, sha, tamanho)
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0], fontes=(boa,))
    assert validar.validar_artefatos_do_caso(caso, raiz).ok

    ruim = replace(boa, sha256="0" * 64)
    caso_ruim = replace(_TRES_CASOS_HOMOLOGAVEIS[0], fontes=(ruim,))
    assert not validar.validar_artefatos_do_caso(caso_ruim, raiz).ok

    receita = replace(_receita_completa(), fontes=(boa,), componentes=(),
                      regras_corte=(), regras_vidro=(), regras_acessorios=())
    assert validar.validar_artefatos_da_receita(receita, raiz).ok


def test_comando_registrar_evidencia_calcula_sem_alterar_a_ficha(capsys):
    """Registrar evidência é ato do especialista: um comando que escrevesse
    sozinho carimbaria como conferido um arquivo que ninguém olhou."""
    import hashlib
    from composicao import cli
    antes = hashlib.sha256(MODELO_FICHA.read_bytes()).hexdigest()
    codigo = cli.main(["registrar-evidencia",
                       "composicao/insumos/suprema_2f_modelo_preenchimento.yaml",
                       "--id-fonte", "FONTE-MODELO"])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert f"sha256: {antes}" in saida
    assert "tamanho_bytes:" in saida
    assert hashlib.sha256(MODELO_FICHA.read_bytes()).hexdigest() == antes


def test_comando_registrar_evidencia_recusa_caminho_de_fora(capsys):
    from composicao import cli
    assert cli.main(["registrar-evidencia", "../fora/foto.jpg"]) == 1
    assert cli.main(["registrar-evidencia", "/etc/hostname"]) == 1


def test_modelo_yaml_continua_valido_com_o_novo_schema(ficha_em_branco):
    r = fontes.validar_estrutura_ficha(ficha_em_branco, "modelo")
    assert r.ok, r.descrever()
    assert fontes.extrair_decisoes_confirmadas(ficha_em_branco) == ()
    caso = fontes.converter_ficha_em_caso_real(ficha_em_branco, "modelo")
    assert caso.id_exemplar is None
    assert all(p.aplicacoes == () for p in caso.perfis)
    assert caso.secoes_preenchidas == ()


# ===========================================================================
# Fechamento antes dos dados reais
#
# Produção compara CÁLCULO com janela real. Sem cálculo, não há conferência —
# e nesta sprint não existe motor nenhum.
# ===========================================================================

def _receita_com_resultados():
    """Receita homologável + resultados calculados de FIXTURE.

    O conteúdo é `PLACEHOLDER_DE_TESTE`: existe para exercitar o encadeamento
    conferência → resultado, nunca para simular fabricação."""
    from dataclasses import replace
    return replace(_receita_homologavel(),
                   resultados_calculados=tuple(
                       _resultado_calculado(c.identificador)
                       for c in _TRES_CASOS_HOMOLOGAVEIS))


# ---- produção exige resultado calculado ------------------------------------

def test_producao_nao_abre_sem_resultado_calculado(biblioteca):
    """Documentação completa — três casos, duas aprovações, três conferências —
    e ZERO resultados calculados. A produção continua fechada."""
    receita = _receita_homologavel()
    assert len(receita.casos_reais) == 3
    assert len(receita.aprovacoes) == 2
    assert len(receita.conferencias) == 3
    assert receita.resultados_calculados == ()

    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("nenhum resultado calculado" in f["regra"] for f in r.falhas)


def test_receita_oficial_da_e4d_nao_tem_resultado_calculado(receita, biblioteca):
    assert receita.resultados_calculados == ()
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok


def test_conferencia_sem_resultado_calculo_id_reprova():
    from composicao.modelos import ConferenciaCasoContraReceita
    with pytest.raises(ReceitaErro, match="resultado_calculo_id"):
        ConferenciaCasoContraReceita(
            caso_id="CASO_A_PEQUENO", resultado=ResultadoAprovacao.APROVADO,
            responsavel="Bruno", data="2026-08-10",
            fonte_id="FONTE-CONFERENCIA")


def test_conferencia_com_resultado_inexistente_reprova(biblioteca):
    from dataclasses import replace
    receita = replace(_receita_com_resultados(),
                      conferencias=tuple(
                          _conferencia(c.identificador,
                                       resultado_calculo_id="RES-FANTASMA")
                          for c in _TRES_CASOS_HOMOLOGAVEIS))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("resultado calculado inexistente" in str(f["encontrado"])
               for f in r.falhas)


def test_resultado_de_outro_caso_reprova(biblioteca):
    from dataclasses import replace
    receita = replace(
        _receita_com_resultados(),
        conferencias=(_conferencia("CASO_A_PEQUENO",
                                   resultado_calculo_id="RES-CASO_B_MEDIO"),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("pertence ao caso" in str(f["encontrado"]) for f in r.falhas)


def test_resultado_de_outra_receita_reprova(biblioteca):
    from dataclasses import replace
    intruso = _resultado_calculado("CASO_A_PEQUENO", receita_codigo="OUTRA")
    receita = replace(_receita_com_resultados(),
                      resultados_calculados=(intruso,)
                      + _receita_com_resultados().resultados_calculados[1:])
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("pertence à receita" in str(f["encontrado"]) for f in r.falhas)


def test_resultado_vazio_nao_conta_como_calculo(biblioteca):
    from composicao.modelos import ResultadoCalculoCaso
    from dataclasses import replace
    from composicao.modelos import OrigemResultadoCalculo
    vazio = ResultadoCalculoCaso(id_resultado="RES-CASO_A_PEQUENO",
                                 caso_id="CASO_A_PEQUENO",
                                 receita_codigo="TESTE",
                                 gerado_por="fixture",
                                 origem=OrigemResultadoCalculo.FIXTURE_TESTE)
    assert not vazio.tem_conteudo
    receita = replace(_receita_com_resultados(),
                      resultados_calculados=(vazio,)
                      + _receita_com_resultados().resultados_calculados[1:])
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("sem componentes" in str(f["encontrado"]) for f in r.falhas)


def test_resultado_de_fixture_nunca_abre_producao(biblioteca):
    """O invariante da sprint: NENHUMA fixture abre produção.

    Um resultado montado em teste tem `origem=FIXTURE_TESTE` e não libera
    fabricação. A abertura real do gate pertence à sprint que integrar o motor
    de cálculo e reproduzir os três casos reais."""
    receita = _receita_com_resultados()
    assert all(not x.de_motor for x in receita.resultados_calculados)
    r = validar.validar_prontidao_para_producao(receita, biblioteca,
                                                fontes.RAIZ)
    assert not r.ok
    assert any("FIXTURE_TESTE" in str(f["encontrado"]) for f in r.falhas)


# ---- conferência: cobertura de componentes ---------------------------------

def test_componentes_conferidos_incompletos_reprovam(biblioteca):
    from dataclasses import replace
    parcial = tuple(f"TESTE:{p}" for p in PERFIS[:5])
    receita = replace(
        _receita_com_resultados(),
        conferencias=(_conferencia("CASO_A_PEQUENO", componentes=parcial),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("não conferidos" in str(f["encontrado"]) for f in r.falhas)


def test_componentes_conferidos_duplicados_reprovam(biblioteca):
    from dataclasses import replace
    dobrado = tuple(f"TESTE:{p}" for p in PERFIS) + ("TESTE:SU-001",)
    receita = replace(
        _receita_com_resultados(),
        conferencias=(_conferencia("CASO_A_PEQUENO", componentes=dobrado),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("duplicados" in str(f["encontrado"]) for f in r.falhas)


def test_componente_conferido_fora_do_resultado_reprova(biblioteca):
    from dataclasses import replace
    inventado = tuple(f"TESTE:{p}" for p in PERFIS) + ("TESTE:SU-999",)
    receita = replace(
        _receita_com_resultados(),
        conferencias=(_conferencia("CASO_A_PEQUENO", componentes=inventado),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("não estão no resultado" in str(f["encontrado"])
               for f in r.falhas)


# ---- conferência: quem pode assinar ----------------------------------------

@pytest.mark.parametrize("tipo,estado", [
    ("catalogo", EstadoConhecimento.CONFIRMADO_CATALOGO),
    ("manifesto_promocao", EstadoConhecimento.CONFIRMADO_BIBLIOTECA_OFICIAL),
    ("foto", EstadoConhecimento.CONFIRMADO_CASO_REAL),
    ("croqui", EstadoConhecimento.CONFIRMADO_CASO_REAL),
])
def test_conferencia_assinada_por_fonte_inapta_reprova(biblioteca, tipo, estado):
    """Uma foto mostra a janela; ela não registra que alguém comparou número a
    número o resultado calculado com a peça."""
    from dataclasses import replace
    inapta = FonteEvidencia(
        id_fonte="FONTE-INAPTA", tipo=tipo,
        referencia="curadoria/campo/evidencia.pdf", descricao="",
        estado=estado, responsavel="Bruno", data="2026-08-10")
    base = _receita_com_resultados()
    receita = replace(
        base, fontes=base.fontes + (inapta,),
        conferencias=(_conferencia("CASO_A_PEQUENO", id_fonte="FONTE-INAPTA"),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("conferência exige tipo" in str(f["encontrado"])
               for f in r.falhas)


def test_responsavel_da_conferencia_divergente_reprova(biblioteca):
    from dataclasses import replace
    base = _receita_com_resultados()
    conf = replace(_conferencia("CASO_A_PEQUENO"), responsavel="Anderson")
    receita = replace(base, conferencias=(conf,)
                      + tuple(_conferencia(c.identificador)
                              for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("assinada por" in str(f["encontrado"]) for f in r.falhas)


def test_data_da_conferencia_divergente_reprova(biblioteca):
    from dataclasses import replace
    base = _receita_com_resultados()
    conf = replace(_conferencia("CASO_A_PEQUENO"), data="2026-09-01")
    receita = replace(base, conferencias=(conf,)
                      + tuple(_conferencia(c.identificador)
                              for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("datada em" in str(f["encontrado"]) for f in r.falhas)


# ---- aplicações do perfil no caso real -------------------------------------

def _ficha_com_aplicacoes(ficha_em_branco, aplicacoes, codigo="SU-003"):
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"id_fonte": "FONTE-ARB", "tipo": "especialista_de_dominio",
                    "referencia": "curadoria/campo/arbitragem.md",
                    "descricao": "papéis", "estado": "CONFIRMADO_ESPECIALISTA",
                    "responsavel": "Bruno", "data": "2026-08-10"}]
    d["perfis"][codigo] = {"observacoes_gerais": "perfil em duas laterais",
                           "aplicacoes": aplicacoes}
    return d


def test_perfil_com_aplicacoes_passa_pelo_fluxo_completo(ficha_em_branco):
    """validar ficha → converter → validar integridade, com DUAS aplicações do
    mesmo perfil. Antes, a integridade procurava `perfil.funcao`, campo que
    deixou de existir."""
    d = _ficha_com_aplicacoes(ficha_em_branco, [
        {"id_componente": "MARCO-ESQ", "funcao": "MARCO_LATERAL_ESQUERDO",
         "quantidade": 1, "orientacao": "vertical",
         "estado": "CONFIRMADO_ESPECIALISTA", "fontes_ids": ["FONTE-ARB"]},
        {"id_componente": "MARCO-DIR", "funcao": "MARCO_LATERAL_DIREITO",
         "quantidade": 1, "orientacao": "vertical",
         "estado": "CONFIRMADO_ESPECIALISTA", "fontes_ids": ["FONTE-ARB"]}])
    assert fontes.validar_estrutura_ficha(d, "x").ok

    caso = fontes.converter_ficha_em_caso_real(d, "x")
    su003 = next(p for p in caso.perfis if p.codigo_perfil == "SU-003")
    assert len(su003.aplicacoes) == 2

    r = validar.validar_integridade_caso_real(caso, PERFIS)
    # reprova por falta de medidas/cortes, NUNCA por campos antigos do perfil
    motivos = " ".join(f["regra"] for f in r.falhas)
    assert "funcao" not in motivos
    assert not any("perfis.SU-003.aplicacoes" in str(f["alvo"])
                   for f in r.falhas), r.descrever()


@pytest.mark.parametrize("faltando", ["id_componente", "funcao", "quantidade",
                                      "orientacao"])
def test_aplicacao_confirmada_incompleta_reprova(ficha_em_branco, faltando):
    completa = {"id_componente": "MARCO-ESQ",
                "funcao": "MARCO_LATERAL_ESQUERDO", "quantidade": 1,
                "orientacao": "vertical", "estado": "CONFIRMADO_ESPECIALISTA",
                "fontes_ids": ["FONTE-ARB"]}
    completa.pop(faltando)
    caso = fontes.converter_ficha_em_caso_real(
        _ficha_com_aplicacoes(ficha_em_branco, [completa]), "x")
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    falhas = [f for f in r.falhas if "aplicacoes[0]" in str(f["alvo"])]
    assert falhas, r.descrever()
    assert faltando in str(falhas[0]["encontrado"])


def test_aplicacao_confirmada_sem_fonte_reprova(ficha_em_branco):
    """A ficha já barra: estado confirmado sem `fontes_ids` é afirmação firme
    apoiada em nada."""
    d = _ficha_com_aplicacoes(ficha_em_branco, [
        {"id_componente": "MARCO-ESQ", "funcao": "MARCO_LATERAL_ESQUERDO",
         "quantidade": 1, "orientacao": "vertical",
         "estado": "CONFIRMADO_ESPECIALISTA"}])
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("evidência não sustenta o estado" in f["regra"]
               for f in r.falhas)

    # e o modelo montado em código também é cobrado na integridade
    from composicao.modelos import AplicacaoPerfil, PerfilNoCasoReal
    from dataclasses import replace
    ap = AplicacaoPerfil(id_componente="MARCO-ESQ",
                         funcao=PapelComponente.MARCO_LATERAL_ESQUERDO,
                         quantidade=1, orientacao="vertical",
                         estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA)
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0],
                   perfis=(PerfilNoCasoReal(codigo_perfil="SU-003",
                                            aplicacoes=(ap,)),))
    res = validar.validar_integridade_caso_real(caso, PERFIS)
    assert any("sem evidência apta" in f["regra"] for f in res.falhas)


def test_aplicacao_parcial_fica_registrada_sem_provar(ficha_em_branco):
    caso = fontes.converter_ficha_em_caso_real(
        _ficha_com_aplicacoes(ficha_em_branco,
                              [{"funcao": "MARCO_LATERAL_ESQUERDO"}]), "x")
    su003 = next(p for p in caso.perfis if p.codigo_perfil == "SU-003")
    assert su003.aplicacoes[0].funcao is PapelComponente.MARCO_LATERAL_ESQUERDO
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert not any("aplicacoes[0]" in str(f["alvo"]) for f in r.falhas)


def test_id_componente_duplicado_reprova_programaticamente():
    """A unicidade não pode viver só no YAML: objeto montado em código também
    tem de ser cobrado."""
    from composicao.modelos import AplicacaoPerfil, PerfilNoCasoReal
    from dataclasses import replace
    ap = AplicacaoPerfil(id_componente="MESMO",
                         funcao=PapelComponente.MARCO_LATERAL_ESQUERDO,
                         quantidade=1, orientacao="vertical",
                         estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                         fontes_ids=("FONTE-CASO-A",))
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0],
                   perfis=(PerfilNoCasoReal(codigo_perfil="SU-003",
                                            aplicacoes=(ap,)),
                           PerfilNoCasoReal(codigo_perfil="SU-041",
                                            aplicacoes=(ap,))))
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert not r.ok
    assert any("id_componente duplicado" in f["regra"] for f in r.falhas)


# ---- integridade dos artefatos nos gates -----------------------------------

@pytest.fixture
def receita_com_artefato(tmp_path):
    """Receita cuja evidência é um arquivo real dentro de uma raiz isolada."""
    import hashlib
    from dataclasses import replace
    raiz = tmp_path / "repo"
    (raiz / "curadoria").mkdir(parents=True)
    alvo = raiz / "curadoria" / "arbitragem.md"
    alvo.write_bytes(b"decisao do especialista")
    fonte = FonteEvidencia(
        id_fonte="FONTE-APROVACAO", tipo="especialista_de_dominio",
        referencia="curadoria/arbitragem.md", descricao="",
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        responsavel="Bruno", data="2026-08-10",
        sha256=hashlib.sha256(b"decisao do especialista").hexdigest())
    base = _receita_completa()
    componentes = tuple(_componente_confirmado(p, fontes=(fonte,))
                        for p in PERFIS)
    # TODA evidência da receita aponta para o mesmo artefato: o teste isola a
    # verificação de integridade, sem ruído de outras fontes.
    regras_corte = tuple(replace(g, fontes=(fonte,),
                                 estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA)
                         for g in base.regras_corte)
    regras_vidro = tuple(replace(g, fontes=(fonte,),
                                 estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA)
                         for g in base.regras_vidro)
    acessorios = tuple(replace(a, fontes=(fonte,),
                               estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA)
                       for a in base.regras_acessorios)
    return raiz, replace(base, componentes=componentes, fontes=(fonte,),
                         regras_corte=regras_corte, regras_vidro=regras_vidro,
                         regras_acessorios=acessorios), alvo


def test_artefato_alterado_bloqueia_o_gate_de_calculo(receita_com_artefato,
                                                      biblioteca):
    raiz, receita, alvo = receita_com_artefato
    assert validar.validar_prontidao_para_calculo(receita, biblioteca, raiz).ok

    alvo.write_bytes(b"decisao trocada depois")
    r = validar.validar_prontidao_para_calculo(receita, biblioteca, raiz)
    assert not r.ok
    assert any("alterado após o registro" in f["regra"] for f in r.falhas)


def test_artefato_removido_bloqueia_o_gate_de_calculo(receita_com_artefato,
                                                      biblioteca):
    raiz, receita, alvo = receita_com_artefato
    alvo.unlink()
    r = validar.validar_prontidao_para_calculo(receita, biblioteca, raiz)
    assert not r.ok
    assert any("inexistente" in f["regra"] for f in r.falhas)


def test_symlink_para_fora_da_raiz_reprova(tmp_path):
    """`startswith` aceitaria um symlink que sai da árvore."""
    import hashlib
    fora = tmp_path / "repo-fora"
    fora.mkdir()
    (fora / "segredo.pdf").write_bytes(b"conteudo externo")
    raiz = tmp_path / "repo"
    raiz.mkdir()
    (raiz / "link").symlink_to(fora, target_is_directory=True)

    fonte = FonteEvidencia(
        id_fonte="FONTE-LINK", tipo="foto", referencia="link/segredo.pdf",
        descricao="", estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        responsavel="Bruno", data="2026-08-10",
        sha256=hashlib.sha256(b"conteudo externo").hexdigest())
    r = validar.validar_artefato_de_evidencia(fonte, raiz)
    assert not r.ok
    assert any("fora da raiz" in f["regra"] for f in r.falhas)


def test_diretorio_irmao_com_mesmo_prefixo_nao_e_descendente(tmp_path):
    """`/tmp/x/repo-fora` não é descendente de `/tmp/x/repo`, embora o texto
    comece igual — era exatamente o que `startswith` deixava passar."""
    raiz = tmp_path / "repo"
    raiz.mkdir()
    irmao = tmp_path / "repo-fora"
    irmao.mkdir()
    (irmao / "a.pdf").write_bytes(b"x")

    assert str(irmao).startswith(str(raiz)), "o prefixo textual coincide"
    assert not validar._dentro_da_raiz(irmao / "a.pdf", raiz)
    assert validar._dentro_da_raiz(raiz / "curadoria" / "a.pdf", raiz)


def test_registrar_evidencia_usa_contencao_por_componentes():
    from composicao import cli
    assert cli.main(["registrar-evidencia", "../fora/a.pdf"]) == 1


def test_fonte_do_manifesto_e4c_tem_hash_verificavel():
    """Artefato imutável do evento E.4C: o hash fica registrado, e qualquer
    alteração posterior aparece."""
    from composicao import receita as receita_mod
    fonte = receita_mod.FONTE_PROMOCAO_E4C
    assert fonte.sha256 and len(fonte.sha256) == 64
    assert fonte.tamanho_bytes
    assert validar.validar_artefato_de_evidencia(fonte, fontes.RAIZ).ok


# ---- independência por fingerprint -----------------------------------------

def _fonte_com_hash(id_fonte, tipo, referencia, conteudo):
    import hashlib
    return FonteEvidencia(
        id_fonte=id_fonte, tipo=tipo, referencia=referencia, descricao="",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL, responsavel="Bruno",
        data="2026-08-10", sha256=hashlib.sha256(conteudo).hexdigest())


def test_lista_compartilhada_com_foto_propria_ainda_reprova():
    """Ter uma foto própria ao lado não torna a lista compartilhada em
    evidência independente."""
    from dataclasses import replace
    lista = _fonte_com_hash("FONTE-LISTA-UNICA", "lista_de_corte_real",
                            "curadoria/campo/lista.pdf", b"lista unica")
    casos = tuple(
        replace(c, fontes=(lista,
                           _fonte_com_hash(f"FONTE-FOTO-{i}", "foto",
                                           f"curadoria/campo/foto{i}.jpg",
                                           f"foto {i}".encode())))
        for i, c in enumerate(_TRES_CASOS_HOMOLOGAVEIS))
    r = validar.validar_independencia_dos_casos(casos)
    assert not r.ok
    assert any("artefato primário reutilizado" in f["regra"] for f in r.falhas)


def test_mesmo_conteudo_em_caminhos_diferentes_reprova():
    """O mesmo croqui copiado para três pastas continua sendo um artefato."""
    from dataclasses import replace
    casos = tuple(
        replace(c, fontes=(_fonte_com_hash(
            f"FONTE-CROQUI-{i}", "croqui",
            f"curadoria/campo/caso{i}/croqui.jpg", b"mesmo croqui"),))
        for i, c in enumerate(_TRES_CASOS_HOMOLOGAVEIS))
    r = validar.validar_independencia_dos_casos(casos)
    assert not r.ok
    assert any("artefato primário reutilizado" in f["regra"] for f in r.falhas)


def test_artefatos_distintos_passam():
    from dataclasses import replace
    casos = tuple(
        replace(c, fontes=(_fonte_com_hash(
            f"FONTE-LISTA-{i}", "lista_de_corte_real",
            f"curadoria/campo/caso{i}/lista.pdf", f"lista {i}".encode()),))
        for i, c in enumerate(_TRES_CASOS_HOMOLOGAVEIS))
    assert validar.validar_independencia_dos_casos(casos).ok


def test_catalogo_pode_ser_compartilhado_entre_casos():
    """Catálogo fala do produto, não do exemplar."""
    from dataclasses import replace
    catalogo = FonteEvidencia(
        id_fonte="FONTE-CAT", tipo="catalogo",
        referencia="dados_exemplo/catalogo.pdf", descricao="",
        estado=EstadoConhecimento.CONFIRMADO_CATALOGO)
    casos = tuple(replace(c, fontes=c.fontes + (catalogo,))
                  for c in _TRES_CASOS_HOMOLOGAVEIS)
    assert validar.validar_independencia_dos_casos(casos).ok


# ---- procedência sobrevive à serialização ----------------------------------

def test_regra_adicional_preserva_origem_no_para_dict():
    """Nenhuma evidência descoberta em campo pode perder a procedência ao ser
    serializada."""
    regra = _regra_adicional()
    d = regra.para_dict()
    assert d["origem_do_alvo"] == "DESCOBERTO_EM_CAMPO"
    assert d["descricao"] == "regra descoberta em campo"
    reconstruida = RegraDimensional(
        identificador=d["identificador"], descricao=d["descricao"],
        alvo=d["alvo"], origem_do_alvo=d["origem_do_alvo"])
    assert reconstruida.origem_do_alvo == regra.origem_do_alvo
    assert reconstruida.descricao == regra.descricao
    assert json.dumps(d, ensure_ascii=False)


def test_acessorio_adicional_preserva_descricao_e_origem_no_para_dict():
    regra = RegraAcessorio(identificador="X", item="trinco",
                           descricao="trinco visto na visita",
                           origem_do_item="DECIDIDO_POR_ESPECIALISTA")
    d = regra.para_dict()
    assert d["descricao"] == "trinco visto na visita"
    assert d["origem_do_item"] == "DECIDIDO_POR_ESPECIALISTA"
    reconstruida = RegraAcessorio(
        identificador=d["identificador"], item=d["item"],
        descricao=d["descricao"], origem_do_item=d["origem_do_item"])
    assert reconstruida == regra
    assert json.dumps(d, ensure_ascii=False)


def test_receita_preliminar_continua_sem_valor_tecnico(receita):
    """O invariante da sprint, repetido depois de tudo.

    A E.4E registrou TOPOLOGIA. Nenhuma medida entrou junto."""
    for c in receita.componentes:
        assert c.quantidade == 1, "quantidade é a peça, não uma medida"
    assert receita.resultados_calculados == ()
    assert receita.conferencias == ()
    assert receita.casos_reais == ()
    for regra in receita.regras_dimensionais:
        assert regra.expressao is None and regra.variaveis == ()
    for a in receita.regras_acessorios:
        assert a.quantidade_expressao is None and a.posicao is None


# ===========================================================================
# Gate futuro de produção — a E.4D prepara a fronteira, não a atravessa
# ===========================================================================

def _cortes_calculados_do(caso):
    from composicao.modelos import CorteCalculado
    return tuple(CorteCalculado(componente_id=c.componente_id,
                                perfil=c.perfil,
                                comprimento_mm=c.comprimento_mm,
                                quantidade=c.quantidade)
                 for c in caso.cortes)


# ---- origem do resultado ---------------------------------------------------

def test_placeholder_de_texto_nao_e_saida_de_calculo():
    """`cortes=("PLACEHOLDER_DE_TESTE",)` deixou de ser aceito: uma tupla de
    strings não é lista de fabricação."""
    from composicao.modelos import (OrigemResultadoCalculo,
                                    ResultadoCalculoCaso)
    with pytest.raises(ReceitaErro, match="tipo inesperado"):
        ResultadoCalculoCaso(
            id_resultado="RES-X", caso_id="CASO_A_PEQUENO",
            receita_codigo="TESTE", gerado_por="teste",
            origem=OrigemResultadoCalculo.FIXTURE_TESTE,
            componentes=("TESTE:SU-001",),
            cortes=("PLACEHOLDER_DE_TESTE",))


def test_resultado_de_motor_exige_versao_do_motor():
    from composicao.modelos import (OrigemResultadoCalculo,
                                    ResultadoCalculoCaso)
    with pytest.raises(ReceitaErro, match="versao_motor"):
        ResultadoCalculoCaso(
            id_resultado="RES-X", caso_id="CASO_A_PEQUENO",
            receita_codigo="TESTE", gerado_por="motor",
            origem=OrigemResultadoCalculo.MOTOR_CALCULO)


def test_origem_invalida_reprova():
    from composicao.modelos import ResultadoCalculoCaso
    with pytest.raises(ReceitaErro, match="origem inválida"):
        ResultadoCalculoCaso(id_resultado="RES-X", caso_id="C",
                             receita_codigo="TESTE", gerado_por="x",
                             origem="MOTOR_CALCULO")


def test_receita_oficial_da_e4d_continua_sem_resultados(receita, biblioteca):
    assert receita.resultados_calculados == ()
    r = validar.validar_prontidao_para_producao(receita, biblioteca,
                                                fontes.RAIZ)
    assert not r.ok


def test_e4d_permanece_bloqueada_para_producao_em_qualquer_fixture(biblioteca):
    """O invariante durável da sprint."""
    for receita in (_receita_completa(), _receita_homologavel(),
                    _receita_com_resultados()):
        r = validar.validar_prontidao_para_producao(receita, biblioteca,
                                                    fontes.RAIZ)
        assert not r.ok, receita.codigo


def test_receita_preliminar_continua_bloqueada_para_calculo(receita,
                                                            biblioteca):
    r = validar.validar_prontidao_para_calculo(receita, biblioteca,
                                               fontes.RAIZ)
    assert not r.ok


# ---- DTOs tipados ----------------------------------------------------------

@pytest.mark.parametrize("kw", [
    {"comprimento_mm": Decimal("0")}, {"comprimento_mm": Decimal("NaN")},
    {"comprimento_mm": 1000}, {"quantidade": 0}, {"quantidade": True},
    {"componente_id": ""}, {"perfil": ""},
])
def test_corte_calculado_invalido_reprova(kw):
    from composicao.modelos import CorteCalculado
    base = dict(componente_id="TESTE:SU-001", perfil="SU-001",
                comprimento_mm=Decimal("1000"), quantidade=1)
    base.update(kw)
    with pytest.raises(ReceitaErro):
        CorteCalculado(**base)


@pytest.mark.parametrize("kw", [
    {"largura_mm": Decimal("-1")}, {"espessura_mm": Decimal("Infinity")},
    {"folha": ""}, {"altura_mm": 900},
])
def test_vidro_calculado_invalido_reprova(kw):
    from composicao.modelos import VidroCalculado
    base = dict(folha="1", largura_mm=Decimal("500"),
                altura_mm=Decimal("900"), espessura_mm=Decimal("6"))
    base.update(kw)
    with pytest.raises(ReceitaErro):
        VidroCalculado(**base)


@pytest.mark.parametrize("kw", [
    {"quantidade": 0}, {"quantidade": True}, {"item": ""}, {"posicao": ""},
])
def test_acessorio_calculado_invalido_reprova(kw):
    from composicao.modelos import AcessorioCalculado
    base = dict(item="roldanas", quantidade=2, posicao="base")
    base.update(kw)
    with pytest.raises(ReceitaErro):
        AcessorioCalculado(**base)


def test_resultado_serializa_os_dtos():
    d = _resultado_calculado("CASO_A_PEQUENO").para_dict()
    assert d["origem"] == "FIXTURE_TESTE"
    assert d["cortes"][0]["comprimento_mm"] == "1000"
    assert d["vidros"][0]["espessura_mm"] == "6"
    assert d["acessorios"][0]["quantidade"] == 2
    assert json.dumps(d, ensure_ascii=False)


# ---- resultado precisa conter acessórios -----------------------------------

def test_resultado_sem_acessorios_reprova_quando_a_receita_tem():
    from dataclasses import replace
    receita = _receita_completa()
    sem = replace(_resultado_calculado("CASO_A_PEQUENO"), acessorios=())
    r = validar.validar_resultado_calculado(sem, receita)
    assert not r.ok
    assert any("sem acessórios calculados" in f["regra"] for f in r.falhas)


def test_resultado_sem_acessorios_passa_quando_a_receita_nao_tem():
    from dataclasses import replace
    receita = replace(_receita_completa(), regras_acessorios=())
    sem = replace(_resultado_calculado("CASO_A_PEQUENO"), acessorios=())
    assert validar.validar_resultado_calculado(sem, receita).ok


# ---- comparação estrutural resultado × caso --------------------------------

def _caso_e_resultado():
    caso = _TRES_CASOS_HOMOLOGAVEIS[0]
    from dataclasses import replace
    resultado = replace(_resultado_calculado(caso.identificador),
                        cortes=_cortes_calculados_do(caso))
    return caso, resultado


def test_resultado_igual_ao_caso_passa_na_comparacao():
    caso, resultado = _caso_e_resultado()
    r = validar.validar_resultado_contra_caso(resultado, caso,
                                              _receita_completa())
    assert r.ok, r.descrever()


def test_corte_calculado_diferente_do_real_reprova():
    """Sem tolerância aprovada, a comparação é exata — inventar folga aqui
    esconderia justamente a divergência que o caso real revela."""
    from dataclasses import replace
    from composicao.modelos import CorteCalculado
    caso, resultado = _caso_e_resultado()
    torto = (replace(resultado.cortes[0],
                     comprimento_mm=Decimal("1001")),) + resultado.cortes[1:]
    r = validar.validar_resultado_contra_caso(replace(resultado, cortes=torto),
                                              caso, _receita_completa())
    assert not r.ok
    assert any("cortes calculados divergem" in f["regra"] for f in r.falhas)


def test_vidro_calculado_diferente_do_real_reprova():
    from dataclasses import replace
    caso, resultado = _caso_e_resultado()
    torto = (replace(resultado.vidros[0], espessura_mm=Decimal("8")),)
    r = validar.validar_resultado_contra_caso(replace(resultado, vidros=torto),
                                              caso, _receita_completa())
    assert not r.ok
    assert any("vidros calculados divergem" in f["regra"] for f in r.falhas)


def test_acessorio_calculado_diferente_do_real_reprova():
    from dataclasses import replace
    caso, resultado = _caso_e_resultado()
    torto = (replace(resultado.acessorios[0], quantidade=4),) \
        + resultado.acessorios[1:]
    r = validar.validar_resultado_contra_caso(
        replace(resultado, acessorios=torto), caso, _receita_completa())
    assert not r.ok
    assert any("acessórios calculados divergem" in f["regra"] for f in r.falhas)


def test_conferencia_aprovada_nao_salva_resultado_divergente(biblioteca):
    """Marcar `cortes_conferidos=True` registra que alguém olhou — não que os
    números batem."""
    from dataclasses import replace
    base = _receita_com_resultados()
    divergente = replace(
        base.resultados_calculados[0],
        cortes=(replace(base.resultados_calculados[0].cortes[0],
                        comprimento_mm=Decimal("9999")),)
        + base.resultados_calculados[0].cortes[1:])
    receita = replace(base, resultados_calculados=(divergente,)
                      + base.resultados_calculados[1:])
    r = validar.validar_prontidao_para_producao(receita, biblioteca,
                                                fontes.RAIZ)
    assert not r.ok
    assert any("divergem do caso real" in str(f["encontrado"])
               for f in r.falhas)


# ---- unicidade e vínculo dos resultados ------------------------------------

def test_ids_de_resultado_duplicados_reprovam():
    from dataclasses import replace
    base = _receita_com_resultados()
    clone = replace(base.resultados_calculados[1],
                    id_resultado=base.resultados_calculados[0].id_resultado)
    receita = replace(base,
                      resultados_calculados=(base.resultados_calculados[0],
                                             clone))
    r = validar.validar_resultados_calculados(receita)
    assert not r.ok
    assert any("id_resultado duplicado" in f["regra"] for f in r.falhas)


def test_resultados_distintos_do_mesmo_caso_coexistem():
    """Histórico de recálculos é legítimo — o que não pode é ID repetido."""
    from dataclasses import replace
    base = _receita_com_resultados()
    segundo = replace(base.resultados_calculados[0],
                      id_resultado="RES-CASO_A_PEQUENO-V2")
    receita = replace(base, resultados_calculados=base.resultados_calculados
                      + (segundo,))
    assert validar.validar_resultados_calculados(receita).ok
    assert receita.resultado_calculado("RES-CASO_A_PEQUENO-V2") is segundo


def test_conferencia_resolve_exatamente_o_id_citado(biblioteca):
    from dataclasses import replace
    base = _receita_com_resultados()
    segundo = replace(base.resultados_calculados[0],
                      id_resultado="RES-CASO_A_PEQUENO-V2",
                      cortes=(replace(base.resultados_calculados[0].cortes[0],
                                      comprimento_mm=Decimal("7777")),)
                      + base.resultados_calculados[0].cortes[1:])
    receita = replace(
        base, resultados_calculados=base.resultados_calculados + (segundo,),
        conferencias=(_conferencia("CASO_A_PEQUENO",
                                   resultado_calculo_id="RES-CASO_A_PEQUENO-V2"),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca,
                                                fontes.RAIZ)
    assert not r.ok
    assert any("7777" in str(f["encontrado"]) for f in r.falhas), \
        "a conferência tem de resolver o resultado que ela cita"


def test_resultado_de_caso_inexistente_reprova():
    from dataclasses import replace
    base = _receita_com_resultados()
    intruso = replace(base.resultados_calculados[0],
                      id_resultado="RES-FANTASMA", caso_id="CASO_C_GRANDE")
    receita = replace(base, casos_reais=_TRES_CASOS_HOMOLOGAVEIS[:2],
                      resultados_calculados=(intruso,))
    r = validar.validar_resultados_calculados(receita)
    assert not r.ok
    assert any("caso inexistente" in f["regra"] for f in r.falhas)


# ---- raiz obrigatória ------------------------------------------------------

def test_gate_de_calculo_sem_raiz_nao_ignora_artefatos(biblioteca):
    """`raiz=None` desligava a checagem em silêncio — pior que não tê-la."""
    from dataclasses import replace
    fonte_local = FonteEvidencia(
        id_fonte="FONTE-LOCAL", tipo="especialista_de_dominio",
        referencia="curadoria/handoffs/e4d/estado_inicial_e4d.md",
        descricao="", estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        responsavel="Bruno", data="2026-08-10")
    receita = replace(_receita_completa(),
                      fontes=(FONTE_APROVACAO, fonte_local))
    r = validar.validar_prontidao_para_calculo(receita, biblioteca)
    assert not r.ok
    assert any("sem raiz do repositório" in f["regra"] for f in r.falhas)


def test_gate_de_producao_sem_raiz_nao_ignora_artefatos(biblioteca):
    from dataclasses import replace
    fonte_local = FonteEvidencia(
        id_fonte="FONTE-LOCAL-CASO", tipo="lista_de_corte_real",
        referencia="curadoria/handoffs/e4d/estado_inicial_e4d.md",
        descricao="", estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        responsavel="Bruno", data="2026-08-10")
    caso = replace(_TRES_CASOS_HOMOLOGAVEIS[0],
                   fontes=_TRES_CASOS_HOMOLOGAVEIS[0].fontes + (fonte_local,))
    receita = replace(_receita_com_resultados(),
                      casos_reais=(caso,) + _TRES_CASOS_HOMOLOGAVEIS[1:])
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("sem raiz do repositório" in f["regra"] for f in r.falhas)


# ---- compatibilidade semântica da assinatura -------------------------------

@pytest.mark.parametrize("tipo,estado", [
    ("especialista_de_dominio", EstadoConhecimento.CONFIRMADO_CASO_REAL),
    ("conferencia_caso_receita", EstadoConhecimento.CONFIRMADO_ESPECIALISTA),
    ("validacao_caso_real", EstadoConhecimento.CONFIRMADO_CATALOGO),
])
def test_par_tipo_estado_incompativel_nao_assina(tipo, estado):
    """Um especialista afirma CONFIRMADO_ESPECIALISTA; uma conferência de campo
    afirma CONFIRMADO_CASO_REAL. Trocar os dois é procedência trocada."""
    from composicao.modelos import estado_incompativel_com_assinatura
    fonte = FonteEvidencia(
        id_fonte="FONTE-TROCADA", tipo=tipo, referencia="X-TESTE",
        descricao="", estado=estado, responsavel="Bruno", data="2026-08-10",
        forma_referencia="identificador_externo")
    assert estado_incompativel_com_assinatura(fonte) is not None


@pytest.mark.parametrize("tipo,estado", [
    ("especialista_de_dominio", EstadoConhecimento.CONFIRMADO_ESPECIALISTA),
    ("conferencia_caso_receita", EstadoConhecimento.CONFIRMADO_CASO_REAL),
    ("validacao_caso_real", EstadoConhecimento.CONFIRMADO_CASO_REAL),
])
def test_par_tipo_estado_compativel_assina(tipo, estado):
    from composicao.modelos import estado_incompativel_com_assinatura
    fonte = FonteEvidencia(
        id_fonte="FONTE-OK", tipo=tipo, referencia="X-TESTE", descricao="",
        estado=estado, responsavel="Bruno", data="2026-08-10",
        forma_referencia="identificador_externo")
    assert estado_incompativel_com_assinatura(fonte) is None


def test_especialista_com_estado_de_caso_real_nao_assina_conferencia(biblioteca):
    from dataclasses import replace
    trocada = FonteEvidencia(
        id_fonte="FONTE-TROCADA", tipo="especialista_de_dominio",
        referencia="ARBITRAGEM-TROCADA", descricao="",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        responsavel="Bruno", data="2026-08-10",
        forma_referencia="identificador_externo")
    base = _receita_com_resultados()
    receita = replace(
        base, fontes=base.fontes + (trocada,),
        conferencias=(_conferencia("CASO_A_PEQUENO", id_fonte="FONTE-TROCADA"),)
        + tuple(_conferencia(c.identificador)
                for c in _TRES_CASOS_HOMOLOGAVEIS[1:]))
    r = validar.validar_prontidao_para_producao(receita, biblioteca,
                                                fontes.RAIZ)
    assert not r.ok
    assert any("assina em" in str(f["encontrado"]) for f in r.falhas)


# ===========================================================================
# Sprint E.4E — topologia da Suprema de correr de duas folhas
#
# Esta rodada registra ONDE cada perfil fica. Nenhum teste aqui fixa medida,
# fórmula, folga, sobreposição ou desconto: um número inventado virando
# regressão protegida é exatamente o que estes testes existem para impedir.
# ===========================================================================

from composicao.modelos import (PAPEIS_DE_BAGUETE, PAPEIS_DE_QUADRO,  # noqa: E402
                                PAPEIS_ESTRUTURAIS_DE_FOLHA,
                                RelacaoEntreComponentes,
                                TipoRelacaoComponentes)
from composicao.receita import (ID_MONTANTE_CENTRAL, PLANO_EXTERNO,  # noqa: E402
                                PLANO_INTERNO)


def _relacao(participantes, tipo=TipoRelacaoComponentes.ENCONTRO_CENTRAL):
    return RelacaoEntreComponentes(
        tipo=tipo, participantes=participantes,
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        fontes=(receita_mod.FONTE_TOPOLOGIA_E4E,))


def _papeis_por_perfil(componentes):
    return sorted((c.perfil.codigo_perfil, c.papel.value) for c in componentes)


# ---- quadro ----------------------------------------------------------------

def test_quadro_tem_quatro_pecas_com_os_perfis_arbitrados(receita):
    quadro = [c for c in receita.componentes if c.papel in PAPEIS_DE_QUADRO]
    assert len(quadro) == 4
    assert _papeis_por_perfil(quadro) == [
        ("SU-001", "MARCO_SUPERIOR"), ("SU-002", "MARCO_INFERIOR"),
        ("SU-003", "MARCO_LATERAL"), ("SU-003", "MARCO_LATERAL")]
    assert all(c.folha is None for c in quadro), "quadro não pertence a folha"


def test_marcos_laterais_sao_duas_ocorrencias_do_mesmo_papel(receita):
    """Duas peças distintas, papel idêntico.

    Se o papel gravasse esquerda/direita, espelhar a janela exigiria trocar de
    tipologia — e a lateralidade é da instância, não da receita."""
    laterais = receita.componentes_do_perfil("SU-003")
    assert len(laterais) == 2
    assert len({c.identificador for c in laterais}) == 2
    assert {c.papel for c in laterais} == {PapelComponente.MARCO_LATERAL}


def test_nenhum_componente_grava_lateralidade(receita):
    """Nada na receita permite dizer qual lado é o esquerdo."""
    proibidos = {PapelComponente.MARCO_LATERAL_ESQUERDO,
                 PapelComponente.MARCO_LATERAL_DIREITO}
    assert not [c for c in receita.componentes if c.papel in proibidos]
    texto = " ".join(f"{c.identificador} {c.posicao} {c.folha} "
                     f"{' '.join(c.observacoes)}"
                     for c in receita.componentes).lower()
    for palavra in ("esquerd", "direit"):
        assert palavra not in texto, palavra


# ---- folhas ----------------------------------------------------------------

@pytest.mark.parametrize("plano,montante_central",
                         [(PLANO_INTERNO, "SU-040"), (PLANO_EXTERNO, "SU-041")])
def test_cada_folha_tem_a_mesma_estrutura(receita, plano, montante_central):
    estrutura = [c for c in receita.componentes_da_folha(plano)
                 if c.papel in PAPEIS_ESTRUTURAIS_DE_FOLHA]
    assert len(estrutura) == 4
    assert _papeis_por_perfil(estrutura) == sorted([
        ("SU-039", "MONTANTE_LATERAL_FOLHA"),
        (montante_central, "MONTANTE_CENTRAL_FOLHA"),
        ("SU-053", "TRAVESSA_SUPERIOR_FOLHA"),
        ("SU-053", "TRAVESSA_INFERIOR_FOLHA")])


def test_so_existem_dois_planos(receita):
    folhas = {c.folha for c in receita.componentes} - {None}
    assert folhas == {PLANO_INTERNO, PLANO_EXTERNO}
    assert len(folhas) == receita.quantidade_folhas


def test_mao_de_amigo_e_montante_nao_ferragem(receita):
    """SU-040 e SU-041 são perfis. O papel registrado é o estrutural."""
    for codigo in ("SU-040", "SU-041"):
        (comp,) = receita.componentes_do_perfil(codigo)
        assert comp.papel is PapelComponente.MONTANTE_CENTRAL_FOLHA
        assert comp.orientacao == "vertical"
    itens = {a.item for a in receita.regras_acessorios}
    assert not any("amigo" in i.lower() for i in itens)
    assert not [c for c in receita.componentes
                if c.papel is PapelComponente.MAO_DE_AMIGO]


# ---- baguetes --------------------------------------------------------------

def test_oito_baguetes_distinguiveis_do_estrutural(receita):
    baguetes = [c for c in receita.componentes if c.papel in PAPEIS_DE_BAGUETE]
    assert len(baguetes) == 8
    assert {c.perfil.codigo_perfil for c in baguetes} == {"SU-102"}
    for plano in (PLANO_INTERNO, PLANO_EXTERNO):
        da_folha = [c for c in baguetes if c.folha == plano]
        assert len(da_folha) == 4
        assert sorted(c.orientacao for c in da_folha) == [
            "horizontal", "horizontal", "vertical", "vertical"]


def test_contagem_estrutural_nao_inclui_acabamento(receita):
    estruturais = [c for c in receita.componentes
                   if c.papel not in PAPEIS_DE_BAGUETE]
    baguetes = [c for c in receita.componentes if c.papel in PAPEIS_DE_BAGUETE]
    assert (len(estruturais), len(baguetes)) == (12, 8)
    assert len(receita.componentes) == 20
    assert PAPEIS_DE_BAGUETE.isdisjoint(PAPEIS_DE_QUADRO)
    assert PAPEIS_DE_BAGUETE.isdisjoint(PAPEIS_ESTRUTURAIS_DE_FOLHA)


def test_identificadores_das_ocorrencias_sao_unicos(receita):
    ids = [c.identificador for c in receita.componentes]
    assert len(set(ids)) == len(ids) == 20


# ---- encontro central ------------------------------------------------------

def test_encontro_central_e_relacao_entre_as_duas_folhas(receita):
    (rel,) = receita.relacoes_do_tipo(TipoRelacaoComponentes.ENCONTRO_CENTRAL)
    assert rel.participantes == (ID_MONTANTE_CENTRAL[PLANO_INTERNO],
                                 ID_MONTANTE_CENTRAL[PLANO_EXTERNO])
    por_id = {c.identificador: c for c in receita.componentes}
    perfis = [por_id[p].perfil.codigo_perfil for p in rel.participantes]
    assert perfis == ["SU-040", "SU-041"]
    assert [por_id[p].folha for p in rel.participantes] == [PLANO_INTERNO,
                                                            PLANO_EXTERNO]


def test_encontro_central_nao_e_uma_terceira_peca(receita):
    """Nem peça, nem papel de peça, nem texto solto em observações."""
    assert not [c for c in receita.componentes
                if c.papel is PapelComponente.ENCONTRO_CENTRAL]
    assert len(receita.componentes) == 20
    for c in receita.componentes:
        assert not any("encontro" in o.lower() for o in c.observacoes)


def test_relacao_cita_ocorrencia_e_nao_codigo_de_perfil(receita):
    """"SU-040 encontra SU-041" seria ambíguo com o perfil repetido."""
    (rel,) = receita.relacoes
    ids = {c.identificador for c in receita.componentes}
    assert set(rel.participantes) <= ids
    assert not set(rel.participantes) & set(PERFIS)


# ---- validação da relação --------------------------------------------------

def test_relacao_recusa_participante_repetido():
    with pytest.raises(ReceitaErro, match="participante repetido"):
        _relacao(("MESMO", "MESMO"))


@pytest.mark.parametrize("participantes", [(), ("A",), ("A", "B", "C")])
def test_encontro_central_e_binario(participantes):
    with pytest.raises(ReceitaErro, match="esperado exatamente 2"):
        _relacao(participantes)


def test_relacao_recusa_participante_vazio():
    with pytest.raises(ReceitaErro, match="participante vazio"):
        _relacao(("A", "   "))


def test_relacao_recusa_tipo_fora_do_vocabulario():
    with pytest.raises(ReceitaErro, match="tipo inválido"):
        _relacao(("A", "B"), tipo="ENCONTRO_CENTRAL")


def test_validacao_recusa_referencia_fantasma(receita):
    from dataclasses import replace
    fantasma = _relacao((ID_MONTANTE_CENTRAL[PLANO_INTERNO],
                         "SUPREMA_CORRER_2F:PECA-QUE-NAO-EXISTE"))
    r2 = replace(receita, relacoes=(fantasma,))
    r = validar.validar_cobertura_estrutural_receita(r2)
    assert not r.ok
    assert any("componente inexistente" in f["regra"] for f in r.falhas)


def test_validacao_recusa_encontro_dentro_da_mesma_folha(receita):
    from dataclasses import replace
    mesma = _relacao((ID_MONTANTE_CENTRAL[PLANO_INTERNO],
                      "SUPREMA_CORRER_2F:FOLHA-INTERNA:MONTANTE-LATERAL"))
    r2 = replace(receita, relacoes=(mesma,))
    r = validar.validar_cobertura_estrutural_receita(r2)
    assert not r.ok
    assert any("mesma folha" in f["regra"] for f in r.falhas)


def test_validacao_recusa_relacao_duplicada(receita):
    from dataclasses import replace
    r2 = replace(receita, relacoes=receita.relacoes + receita.relacoes)
    r = validar.validar_cobertura_estrutural_receita(r2)
    assert not r.ok
    assert any("duplicada" in f["regra"] for f in r.falhas)


def test_validacao_recusa_relacao_com_evidencia_incompativel(receita):
    from dataclasses import replace
    sem_lastro = RelacaoEntreComponentes(
        tipo=TipoRelacaoComponentes.ENCONTRO_CENTRAL,
        participantes=receita.relacoes[0].participantes,
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        fontes=(FONTE_CATALOGO,))
    r = validar.validar_cobertura_estrutural_receita(
        replace(receita, relacoes=(sem_lastro,)))
    assert not r.ok
    assert any("não sustenta" in f["regra"] for f in r.falhas)


def test_relacao_com_participante_fantasma_fecha_a_visualizacao(receita,
                                                                biblioteca):
    from dataclasses import replace
    r2 = replace(receita, relacoes=(_relacao(("NAO-EXISTE-1", "NAO-EXISTE-2")),))
    assert not validar.validar_prontidao_para_visualizacao(r2, biblioteca).ok


# ---- imutabilidade e serialização -----------------------------------------

def test_relacao_e_imutavel(receita):
    (rel,) = receita.relacoes
    assert isinstance(rel.participantes, tuple)
    assert isinstance(rel.fontes, tuple)
    with pytest.raises(Exception):
        rel.participantes = ("X", "Y")
    with pytest.raises(AttributeError):
        rel.tipo = TipoRelacaoComponentes.ENCONTRO_CENTRAL


def test_lista_de_participantes_e_congelada_na_construcao():
    origem = ["A", "B"]
    rel = _relacao(origem)
    origem.append("C")
    assert rel.participantes == ("A", "B")


def test_relacoes_da_receita_sao_congeladas():
    lista = [_relacao(("A", "B"))]
    r = ReceitaTipologia(codigo="X", nome="n", sistema="Suprema",
                         quantidade_folhas=2, relacoes=lista)
    lista.clear()
    assert isinstance(r.relacoes, tuple) and len(r.relacoes) == 1


def test_receita_recusa_relacao_de_tipo_errado():
    with pytest.raises(ReceitaErro):
        ReceitaTipologia(codigo="X", nome="n", sistema="Suprema",
                         quantidade_folhas=2,
                         relacoes=({"tipo": "ENCONTRO_CENTRAL"},))


def test_relacao_sobrevive_ao_round_trip_yaml(receita):
    """A relação atravessa YAML e volta idêntica.

    A receita ainda não é persistida em disco — quem é serializado é a ficha de
    campo. Este teste prova o contrato de serialização da relação em si, para
    que a persistência futura não descubra tarde que ela não atravessa."""
    yaml = pytest.importorskip("yaml")
    (original,) = receita.relacoes
    texto = yaml.safe_dump(original.para_dict(), allow_unicode=True,
                           sort_keys=False)
    d = yaml.safe_load(texto)
    assert d["tipo"] == "ENCONTRO_CENTRAL"
    assert d["participantes"] == list(original.participantes)

    fontes_lidas = tuple(
        FonteEvidencia(id_fonte=f["id_fonte"], tipo=f["tipo"],
                       referencia=f["referencia"], descricao=f["descricao"],
                       estado=EstadoConhecimento(f["estado"]),
                       responsavel=f.get("responsavel"), data=f.get("data"),
                       forma_referencia=f["forma_referencia"],
                       sha256=f.get("sha256"),
                       tamanho_bytes=f.get("tamanho_bytes"))
        for f in d["fontes"])
    reconstruida = RelacaoEntreComponentes(
        tipo=TipoRelacaoComponentes(d["tipo"]),
        participantes=tuple(d["participantes"]),
        estado=EstadoConhecimento(d["estado"]),
        fontes=fontes_lidas, observacao=d["observacao"])
    assert reconstruida == original


def test_topologia_inteira_sobrevive_ao_round_trip_yaml(receita):
    yaml = pytest.importorskip("yaml")
    def retrato(r):
        return [[c.identificador, c.perfil.codigo_perfil, c.papel.value,
                 c.orientacao, c.folha, c.posicao, c.quantidade]
                for c in r.componentes]
    lido = yaml.safe_load(yaml.safe_dump(retrato(receita), allow_unicode=True))
    assert lido == retrato(receita)


# ---- o que a topologia NÃO autoriza ---------------------------------------

def test_registrar_topologia_nao_abre_calculo_nem_producao(receita, biblioteca):
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    assert rel["gates"]["visualizacao_preliminar"]["aberto"] is True
    assert rel["gates"]["calculo"]["aberto"] is False
    assert rel["gates"]["producao"]["aberto"] is False


def test_topologia_nao_trouxe_nenhuma_medida(receita):
    for c in receita.componentes:
        assert c.quantidade == 1
        for texto in (c.orientacao, c.posicao, c.folha):
            assert not any(ch.isdigit() for ch in texto or "")
    for regra in receita.regras_dimensionais:
        assert regra.expressao is None and regra.variaveis == ()


def test_perguntas_dimensionais_continuam_abertas(receita):
    texto = " ".join(receita.perguntas_abertas).lower()
    for tema in ("desconto", "folga", "sobreposição", "vidro", "acessório"):
        assert tema in texto, tema


def test_papeis_antigos_continuam_disponiveis():
    """Nada foi removido do vocabulário: receitas anteriores seguem válidas."""
    for nome in ("MARCO_LATERAL_ESQUERDO", "MARCO_LATERAL_DIREITO",
                 "MAO_DE_AMIGO", "ENCONTRO_CENTRAL"):
        assert PapelComponente(nome).value == nome


def test_fonte_da_topologia_aponta_para_arquivo_existente(receita):
    fonte = receita_mod.FONTE_TOPOLOGIA_E4E
    caminho = RAIZ / fonte.referencia
    assert caminho.is_file(), fonte.referencia
    import hashlib
    dados = caminho.read_bytes()
    assert hashlib.sha256(dados).hexdigest() == fonte.sha256
    assert len(dados) == fonte.tamanho_bytes


def test_receita_e_deterministica_com_a_topologia():
    a = receita_mod.construir_receita_preliminar()
    b = receita_mod.construir_receita_preliminar()
    assert a.componentes == b.componentes
    assert a.relacoes == b.relacoes
