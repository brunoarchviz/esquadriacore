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
from composicao.modelos import (ESTADO_CASO_RECEBIDO, ESTADO_CASO_VALIDADO,
                                ESTADO_RECEITA_PRELIMINAR, CasoRealFabricacao,
                                ComponenteReceita, EstadoConhecimento,
                                FonteEvidencia, PapelComponente, ReceitaErro,
                                ReceitaTipologia, RegraDimensional)

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


def _fonte(estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA, responsavel="Bruno"):
    return FonteEvidencia(
        tipo="especialista_de_dominio",
        referencia="curadoria/handoffs/e4d/estado_inicial_e4d.md",
        descricao="decisão registrada em teste", estado=estado,
        responsavel=responsavel, data="2026-08-03")


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
    for regra in receita.todas_as_regras:
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
    with pytest.raises(ReceitaErro, match="absoluta"):
        FonteEvidencia(tipo="foto", referencia="/home/bruno/foto.jpg",
                       descricao="", estado=EstadoConhecimento.PENDENTE)


def test_fonte_recusa_tipo_desconhecido():
    with pytest.raises(ReceitaErro, match="tipo de fonte desconhecido"):
        FonteEvidencia(tipo="chute", referencia="x", descricao="",
                       estado=EstadoConhecimento.PENDENTE)


# ===========================================================================
# Ficha de campo
# ===========================================================================

def test_carrega_ficha_estruturalmente_valida(ficha_em_branco):
    r = fontes.validar_estrutura_ficha(ficha_em_branco, "modelo")
    assert r.ok, r.descrever()
    assert ficha_em_branco["tipologia"]["codigo"] == "SUPREMA_CORRER_2F"


def test_rejeita_ficha_sem_tipologia():
    r = fontes.validar_estrutura_ficha({"caso_real": {}}, "x")
    assert not r.ok and "tipologia" in r.falhas[0]["regra"]


@pytest.mark.parametrize("campo", ["largura_total_mm", "altura_total_mm"])
@pytest.mark.parametrize("valor", [0, -1, "0", "abc"])
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
    assert any("campos desconhecidos" in f["regra"] for f in r.falhas)


def test_nao_inventa_campo_ausente(ficha_em_branco):
    """Campo em branco entra como None — não como 0, não como string vazia
    convertida em número."""
    caso = fontes.converter_ficha_em_caso_real(ficha_em_branco, "modelo")
    assert caso.largura_total_mm is None
    assert caso.altura_total_mm is None
    assert caso.cortes == () and caso.vidros == () and caso.acessorios == ()
    assert caso.estado_validacao != ESTADO_CASO_VALIDADO


def test_extrai_pendencias(ficha_em_branco):
    pend = fontes.extrair_pendencias(ficha_em_branco)
    escopos = {p["escopo"] for p in pend}
    assert "caso_real" in escopos and "vista" in escopos
    for p in PERFIS:
        assert f"perfis.{p}" in escopos, p
    assert len(pend) >= 3 + 5 + 4 * len(PERFIS)


def test_extrai_confirmacoes(ficha_em_branco):
    assert fontes.extrair_decisoes_confirmadas(ficha_em_branco) == ()
    d = copy.deepcopy(ficha_em_branco)
    d["vista"]["lado_de_referencia"] = "interno"
    d["perfis"]["SU-001"] = {"funcao": "MARCO_SUPERIOR", "quantidade": 1,
                             "orientacao": "horizontal", "observacoes": None,
                             "fonte": "especialista_de_dominio"}
    dec = fontes.extrair_decisoes_confirmadas(d)
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
    assert caso.estado_validacao == ESTADO_CASO_RECEBIDO, \
        "receber não é validar"


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


def test_producao_exige_casos_reais_validados_e_aprovacao(biblioteca):
    """Mesmo com tudo confirmado, sem janela real fabricada não há produção."""
    from dataclasses import replace
    regra = RegraDimensional(
        identificador="R", descricao="d", alvo="largura_folha",
        expressao="PLACEHOLDER_DE_TESTE", variaveis=("largura_total_mm",),
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))
    completa = ReceitaTipologia(
        codigo="TESTE", nome="t", sistema="Suprema", quantidade_folhas=2,
        componentes=tuple(_componente_confirmado(p) for p in PERFIS),
        regras_corte=(regra,), regras_vidro=(), estado="CONFIRMADA")
    assert validar.validar_prontidao_para_calculo(completa, biblioteca).ok
    r = validar.validar_prontidao_para_producao(completa, biblioteca)
    assert not r.ok
    assert any("casos reais" in f["regra"] for f in r.falhas)
    assert any("especialista" in f["regra"] for f in r.falhas)

    casos = tuple(CasoRealFabricacao(identificador=i,
                                     estado_validacao=ESTADO_CASO_VALIDADO)
                  for i in ("CASO_A_PEQUENO", "CASO_B_MEDIO", "CASO_C_GRANDE"))
    com_casos = replace(completa, casos_reais=casos,
                        decisoes_do_especialista=("aprovado em 2026-08-10",))
    assert validar.validar_prontidao_para_producao(com_casos, biblioteca).ok


def test_relatorio_lista_todas_as_pendencias(receita, biblioteca):
    rel = prontidao.gerar_relatorio_prontidao(receita, biblioteca)
    assert len(rel["componentes"]["pendentes"]) == 8
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
    for regra in receita.todas_as_regras:
        assert regra.expressao is None, regra.identificador
        assert regra.variaveis == ()
        assert regra.estado is EstadoConhecimento.PENDENTE
    assert receita.regras_acessorios == ()
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
