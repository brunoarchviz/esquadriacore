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
    return FonteEvidencia(
        id_fonte=id_fonte, tipo=tipo,
        referencia="curadoria/handoffs/e4d/estado_inicial_e4d.md",
        descricao="decisão registrada em teste", estado=estado,
        responsavel=responsavel, data=data)


def _regra_acessorio_confirmada(item="roldanas"):
    return RegraAcessorio(
        identificador=f"TESTE:acessorio:{item}", item=item,
        quantidade_expressao="PLACEHOLDER_DE_TESTE", posicao="base da folha",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))


# Fonte de especialista com autoria completa, datada no dia da aprovação.
FONTE_APROVACAO = FonteEvidencia(
    id_fonte="FONTE-APROVACAO", tipo="especialista_de_dominio",
    referencia="curadoria/handoffs/e4d/estado_inicial_e4d.md",
    descricao="arbitragem final", estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
    responsavel="Bruno", data="2026-08-10")

# Evidência do caso real: lista de corte de verdade, não parecer.
FONTE_CASO = FonteEvidencia(
    id_fonte="FONTE-CASO-01", tipo="lista_de_corte_real",
    referencia="curadoria/campo/lista_a.pdf", descricao="lista de corte real",
    estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
    responsavel="Bruno", data="2026-08-10")


def _aprovacao(escopo, resultado=ResultadoAprovacao.APROVADO,
               responsavel="Bruno", fonte_id="FONTE-APROVACAO",
               data="2026-08-10"):
    return AprovacaoEspecialista(
        resultado=resultado, responsavel=responsavel, data=data,
        fonte_id=fonte_id, escopo=escopo)


def _validacao_aprovada(resultado=ResultadoAprovacao.APROVADO):
    return ValidacaoCasoReal(
        resultado=resultado, responsavel="Bruno", data="2026-08-10",
        fontes_ids=("FONTE-CASO-01",))


def _corte_confirmado(perfil="SU-001", comprimento="1000", quantidade=1):
    return CorteReal(perfil=perfil, comprimento_mm=Decimal(comprimento),
                     quantidade=quantidade,
                     estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                     fontes_ids=("FONTE-CASO-01",))


def _vidro_confirmado(largura="500", altura="900"):
    return VidroReal(folha="1", largura_mm=Decimal(largura),
                     altura_mm=Decimal(altura), espessura_mm=Decimal("6"),
                     estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                     fontes_ids=("FONTE-CASO-01",))


def _caso_validado(ident, largura, altura, validacao=None, **kw):
    base = dict(
        identificador=ident, largura_total_mm=Decimal(largura),
        altura_total_mm=Decimal(altura),
        estado_dimensoes=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes_ids_dimensoes=("FONTE-CASO-01",),
        cortes=(_corte_confirmado(),), vidros=(_vidro_confirmado(),),
        fontes=(FONTE_CASO,), estado_recebimento=ESTADO_CASO_RECEBIDO,
        validacao=validacao if validacao is not None else _validacao_aprovada())
    base.update(kw)
    return CasoRealFabricacao(**base)


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
    assert len(receita.componentes) == 8
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
    assert receita.componente("SU-102").perfil.id_geometria == "GEO-SU-102"


# ===========================================================================
# Estados de conhecimento
# ===========================================================================

def test_aceita_componente_confirmado():
    c = _componente_confirmado()
    assert c.confirmado and c.pendencias() == ()


def test_aceita_componente_pendente_em_receita_preliminar(receita, biblioteca):
    assert receita.preliminar
    assert all(not c.confirmado for c in receita.componentes)
    r = validar.validar_prontidao_para_visualizacao(receita, biblioteca)
    assert r.ok, r.descrever()
    assert len(r.avisos) == 8, "cada pendência tem de aparecer como aviso"


def test_bloqueia_calculo_com_componente_pendente(receita, biblioteca):
    r = validar.validar_prontidao_para_calculo(receita, biblioteca)
    assert not r.ok
    assert any("componente não confirmado" in f["regra"] for f in r.falhas)


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
    for c in receita.componentes:
        assert c.quantidade is None
        assert c.quantidade != 0
        assert not c.confirmado
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
    assert not r.ok and any("autoria" in f["regra"] for f in r.falhas)

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
    d["perfis"]["SU-999"] = {"funcao": "MARCO_SUPERIOR"}
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    assert any("fora do microlote" in f["regra"] for f in r.falhas)


def test_rejeita_campo_inventado_no_perfil(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-001"] = {"funcao": "MARCO_SUPERIOR", "peso_kg_m": 1.2}
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
    assert caso.estado_validacao == ESTADO_CASO_AGUARDANDO


def test_extrai_pendencias(ficha_em_branco):
    pend = fontes.extrair_pendencias(ficha_em_branco)
    escopos = {p["escopo"] for p in pend}
    assert "caso_real" in escopos and "vista" in escopos
    for p in PERFIS:
        assert f"perfis.{p}" in escopos, p
    assert len(pend) >= 3 + 5 + 4 * len(PERFIS)


def test_extrai_confirmacoes(ficha_em_branco):
    assert fontes.extrair_campos_preenchidos(ficha_em_branco) == ()
    d = copy.deepcopy(ficha_em_branco)
    d["vista"]["lado_de_referencia"] = "interno"
    d["perfis"]["SU-001"] = {"funcao": "MARCO_SUPERIOR", "quantidade": 1,
                             "orientacao": "horizontal", "observacoes": None,
                             "fonte": "especialista_de_dominio"}
    dec = fontes.extrair_campos_preenchidos(d)
    campos = {(x["escopo"], x["campo"]) for x in dec}
    assert ("vista", "lado_de_referencia") in campos
    assert ("perfis.SU-001", "funcao") in campos
    assert ("perfis.SU-001", "quantidade") in campos
    pend = fontes.extrair_pendencias(d)
    assert ("perfis.SU-001", "funcao") not in {(p["escopo"], p["campo"]) for p in pend}


def test_ficha_preenchida_vira_caso_real(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["caso_real"] = {"identificador": "CASO_B_MEDIO",
                      "largura_total_mm": 1500, "altura_total_mm": "1200,5"}
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.identificador == "CASO_B_MEDIO"
    assert caso.largura_total_mm == Decimal("1500")
    assert caso.altura_total_mm == Decimal("1200.5")
    assert caso.estado_validacao == ESTADO_CASO_PARCIAL, \
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
    assert len(g["avisos"]) == 8, "as pendências têm de continuar visíveis"


def test_gate_visual_fecha_se_receita_deixar_de_ser_preliminar(receita, biblioteca):
    from dataclasses import replace
    r2 = replace(receita, estado="CONFIRMADA")
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


_TRES_CASOS = (_caso_validado("CASO_A_PEQUENO", "800", "600"),
               _caso_validado("CASO_B_MEDIO", "1500", "1200"),
               _caso_validado("CASO_C_GRANDE", "2400", "2100"))


def _receita_completa(regra=None):
    """Receita com tudo confirmado — o ponto de partida dos testes de gate."""
    regra = regra or RegraDimensional(
        identificador="R", descricao="d", alvo="largura_folha",
        expressao="PLACEHOLDER_DE_TESTE", variaveis=("largura_total_mm",),
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))
    return ReceitaTipologia(
        codigo="TESTE", nome="t", sistema="Suprema", quantidade_folhas=2,
        componentes=tuple(_componente_confirmado(p) for p in PERFIS),
        regras_corte=(regra,), regras_vidro=(),
        regras_acessorios=(_regra_acessorio_confirmada(),),
        fontes=(FONTE_APROVACAO,), estado="CONFIRMADA")


def test_producao_exige_casos_reais_validados_e_aprovacao(biblioteca):
    """Mesmo com tudo confirmado, sem janela real fabricada não há produção."""
    from dataclasses import replace
    regra = RegraDimensional(
        identificador="R", descricao="d", alvo="largura_folha",
        expressao="PLACEHOLDER_DE_TESTE", variaveis=("largura_total_mm",),
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))
    completa = _receita_completa(regra)
    assert validar.validar_prontidao_para_calculo(completa, biblioteca).ok
    r = validar.validar_prontidao_para_producao(completa, biblioteca)
    assert not r.ok
    assert any("canônicos ausentes" in f["regra"] for f in r.falhas)
    assert any("aprovação do especialista" in f["regra"] for f in r.falhas)

    com_casos = replace(completa, casos_reais=_TRES_CASOS,
                        aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                    _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    assert validar.validar_prontidao_para_producao(com_casos, biblioteca).ok


def test_relatorio_lista_todas_as_pendencias(receita, biblioteca):
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    assert len(rel["componentes"]["pendentes"]) == 8
    assert len(rel["acessorios"]["pendentes"]) == len(receita.regras_acessorios)
    assert len(rel["regras"]["pendentes"]) == 9
    assert rel["componentes"]["confirmados"] == []
    assert rel["regras"]["confirmadas"] == []
    assert len(rel["perguntas_abertas"]) >= 10
    assert rel["casos_reais"] == {"recebidos": [], "validados": []}


def test_relatorio_markdown_e_legivel(receita, biblioteca):
    md = prontidao.relatorio_em_markdown(
        prontidao.gerar_relatorio_prontidao(receita, biblioteca))
    assert "BLOQUEADO" in md and "Perguntas abertas" in md
    assert "Checklist da visita" in md
    for p in PERFIS:
        assert f"`{p}`" in md, p


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
        receita.componentes[0].quantidade = 4


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


def test_nenhum_papel_funcional_foi_atribuido(receita):
    for c in receita.componentes:
        assert c.papel is PapelComponente.NAO_CONFIRMADO, c.identificador
        assert c.quantidade is None and c.orientacao is None
        assert c.folha is None and c.posicao is None


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
    d["perfis"]["SU-001"] = {"funcao": "MARCO_SUPERIORR"}
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
    d["perfis"]["SU-001"] = {"funcao": "MARCO_SUPERIOR", "quantidade": 1,
                             "orientacao": "horizontal",
                             "observacoes": "trilho duplo",
                             "estado": "CONFIRMADO_CASO_REAL",
                             "fontes_ids": ["FONTE-LISTA-A"]}
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
    assert su001.funcao is PapelComponente.MARCO_SUPERIOR
    assert su001.quantidade == 1 and su001.orientacao == "horizontal"
    assert caso.cortes[0].comprimento_mm == Decimal("760")
    assert caso.vidros[0].espessura_mm == Decimal("6")
    assert caso.baguetes[0].lado_de_encaixe == "interno"
    assert caso.acessorios[0].quantidade == 4
    assert caso.folgas[0].valor_mm == Decimal("3")
    assert caso.sobreposicoes[0].valor_mm == Decimal("25")
    assert caso.croquis and caso.fontes and caso.duvidas
    assert caso.croquis[0].descricao == "rabisco do serralheiro"
    assert caso.fontes[0].id_fonte == "FONTE-LISTA-A"
    assert caso.estado_validacao == ESTADO_CASO_RECEBIDO
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
    assert caso.estado_validacao == ESTADO_CASO_PARCIAL
    assert "folgas" in caso.secoes_preenchidas


def test_ficha_apenas_com_foto_e_recebido_parcial(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["fontes"] = [{"id_fonte": "FONTE-FOTO-A", "tipo": "foto",
                    "referencia": "curadoria/campo/frente.jpg",
                    "descricao": "vista interna", "estado": "CONFIRMADO_CASO_REAL",
                    "responsavel": "Bruno", "data": "2026-08-10"}]
    caso = fontes.converter_ficha_em_caso_real(d, "x")
    assert caso.estado_validacao == ESTADO_CASO_PARCIAL
    assert caso.fontes and caso.fontes[0].tipo == "foto"


def test_preenchido_nao_e_confirmado(ficha_em_branco):
    """Sem fonte declarada, um campo preenchido é rascunho — não decisão."""
    d = copy.deepcopy(ficha_em_branco)
    d["perfis"]["SU-001"] = {"funcao": "MARCO_SUPERIOR", "quantidade": 2,
                             "orientacao": "horizontal"}
    assert len(fontes.extrair_campos_preenchidos(d)) >= 3
    assert fontes.extrair_decisoes_confirmadas(d) == ()

    d["perfis"]["SU-001"]["estado"] = "CONFIRMADO_ESPECIALISTA"
    d["perfis"]["SU-001"]["fontes_ids"] = ["FONTE-ARB-01"]
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
    d["perfis"]["SU-001"] = {"funcao": "MARCO_SUPERIOR",
                             "estado": "CONFIRMADO_ESPECIALISTA",
                             "fontes_ids": ["FONTE-SEM-AUTOR"]}
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
    assert any("autoria" in f["regra"] for f in r.falhas)


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
    assert any("sem lista de corte" in f["regra"] for f in r.falhas)


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
    assert caso.estado_validacao == ESTADO_CASO_AGUARDANDO


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
    d["perfis"]["SU-001"] = {"funcao": "MARCO_SUPERIOR",
                             "estado": "CONFIRMADO_ESPECIALISTA",
                             "fontes_ids": ["FONTE-ESP-SEM-AUTOR"]}
    assert fontes.extrair_decisoes_confirmadas(d) == (), \
        "a fonte citada não tem autoria — a outra não pode salvá-la"

    d["perfis"]["SU-001"]["fontes_ids"] = ["FONTE-ESP-COM-AUTOR"]
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
    assert all(not c.validado for c in sem_validacao)
    assert all(c.estado_validacao == ESTADO_CASO_RECEBIDO
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
    assert caso.estado_validacao == ESTADO_CASO_VALIDADO
    assert caso.validado
    from dataclasses import replace
    receita = replace(_receita_completa(), casos_reais=_TRES_CASOS,
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert r.ok, r.descrever()


def test_validacao_reprovada_nao_torna_o_caso_validado():
    caso = _caso_validado("CASO_A_PEQUENO", "800", "600",
                          validacao=_validacao_aprovada(
                              ResultadoAprovacao.REPROVADO))
    assert not caso.validado
    assert caso.estado_validacao == ESTADO_CASO_RECEBIDO


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
    assert any("fonte inexistente" in f["regra"] for f in r.falhas)


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
    assert caso.estado_validacao == ESTADO_CASO_AGUARDANDO
    assert caso.secoes_preenchidas == ()


def test_modelo_yaml_nao_cria_valor_tecnico(ficha_em_branco):
    """Nenhum número, papel, quantidade ou fórmula nasce do modelo."""
    caso = fontes.converter_ficha_em_caso_real(ficha_em_branco, "modelo")
    assert caso.largura_total_mm is None and caso.altura_total_mm is None
    assert caso.estado_dimensoes is None and caso.fontes_ids_dimensoes == ()
    assert caso.vista.vazia
    assert all(p.vazio for p in caso.perfis)
    assert all(p.funcao is None and p.quantidade is None for p in caso.perfis)
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
    assert vazio.validado, "a validação estruturada está aprovada"
    assert not validar.validar_integridade_caso_real(vazio, PERFIS).ok

    receita = replace(_receita_completa(),
                      casos_reais=(vazio,) + _TRES_CASOS[1:],
                      aprovacoes=(_aprovacao(ESCOPO_APROVACAO_RECEITA),
                                  _aprovacao(ESCOPO_APROVACAO_FORMULAS)))
    r = validar.validar_prontidao_para_producao(receita, biblioteca)
    assert not r.ok
    assert any("campos mínimos" in f["regra"] for f in r.falhas)


def test_validacao_com_fonte_duplicada_reprova():
    with pytest.raises(ReceitaErro, match="fonte repetida"):
        ValidacaoCasoReal(resultado=ResultadoAprovacao.APROVADO,
                          responsavel="Bruno", data="2026-08-10",
                          fontes_ids=("FONTE-CASO-01", "FONTE-CASO-01"))


def test_responsavel_da_validacao_divergente_da_fonte_reprova():
    caso = _caso_com(validacao=ValidacaoCasoReal(
        resultado=ResultadoAprovacao.APROVADO, responsavel="Anderson",
        data="2026-08-10", fontes_ids=("FONTE-CASO-01",)))
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert not r.ok
    assert any("responsável da validação divergente" in f["regra"]
               for f in r.falhas)


def test_data_da_validacao_divergente_da_evidencia_reprova():
    caso = _caso_com(validacao=ValidacaoCasoReal(
        resultado=ResultadoAprovacao.APROVADO, responsavel="Bruno",
        data="2026-09-01", fontes_ids=("FONTE-CASO-01",)))
    r = validar.validar_integridade_caso_real(caso, PERFIS)
    assert not r.ok
    assert any("data da validação divergente" in f["regra"] for f in r.falhas)


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
    assert rel["componentes"]["confirmados"] == []
    assert rel["regras"]["confirmadas"] == []
    assert rel["acessorios"]["confirmados"] == []
