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
                                EstadoConhecimento, FonteEvidencia,
                                PapelComponente, ReceitaErro, ReceitaTipologia,
                                RegraAcessorio, RegraDimensional, VidroReal)

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
           data="2026-08-03"):
    return FonteEvidencia(
        tipo="especialista_de_dominio",
        referencia="curadoria/handoffs/e4d/estado_inicial_e4d.md",
        descricao="decisão registrada em teste", estado=estado,
        responsavel=responsavel, data=data)


def _regra_acessorio_confirmada(item="roldanas"):
    return RegraAcessorio(
        identificador=f"TESTE:acessorio:{item}", item=item,
        quantidade_expressao="PLACEHOLDER_DE_TESTE", posicao="base da folha",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),))


def _aprovacao(escopo):
    return AprovacaoEspecialista(
        decisao="aprovado", responsavel="Bruno", data="2026-08-10",
        fonte=_fonte(), escopo=escopo)


def _caso_validado(ident, largura, altura):
    return CasoRealFabricacao(
        identificador=ident, largura_total_mm=Decimal(largura),
        altura_total_mm=Decimal(altura),
        cortes=(CorteReal(perfil="SU-001", comprimento_mm=Decimal("1000")),),
        vidros=(VidroReal(folha="1", largura_mm=Decimal("500"),
                          altura_mm=Decimal("900")),),
        fontes=(_fonte(estado=EstadoConhecimento.CONFIRMADO_CASO_REAL),),
        estado_validacao=ESTADO_CASO_VALIDADO)


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
        estado="CONFIRMADA")


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
    assert falha["esperado"] == "cortes", "a mensagem tem de sugerir o nome certo"


def test_campo_desconhecido_em_vista_reprova(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["vista"]["lado_de_referencias"] = "interno"
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    falha = next(f for f in r.falhas if "lado_de_referencias" in str(f["alvo"]))
    assert falha["esperado"] == "lado_de_referencia"


def test_campo_desconhecido_em_item_de_corte_reprova(ficha_em_branco):
    d = copy.deepcopy(ficha_em_branco)
    d["cortes"] = [{"perfil": "SU-001", "comprimento_mmm": 1000}]
    r = fontes.validar_estrutura_ficha(d, "x")
    assert not r.ok
    falha = next(f for f in r.falhas if "comprimento_mmm" in str(f["alvo"]))
    assert falha["esperado"] == "comprimento_mm"


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
                             "fonte": "lista_de_corte_real"}
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
    d["fontes"] = [{"tipo": "lista_de_corte_real",
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
    assert caso.estado_validacao == ESTADO_CASO_RECEBIDO
    # nada se perdeu no caminho
    for secao in ("vista", "perfis", "cortes", "vidros", "baguetes",
                  "acessorios", "folgas", "sobreposicoes", "croquis",
                  "fontes", "duvidas"):
        assert secao in caso.secoes_preenchidas, secao


def test_dado_fora_do_schema_vai_para_dados_adicionais():
    """Item de lista com campo extra reprova a estrutura; mas se a conversão
    for chamada com ele, o dado é preservado, nunca descartado."""
    item = {"perfil": "SU-001", "comprimento_mm": 700, "medido_com": "trena"}
    from composicao.fontes import CAMPOS_CORTE, _extras
    assert _extras(item, CAMPOS_CORTE) == (("medido_com", "trena"),)


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
    d["fontes"] = [{"tipo": "foto", "referencia": "curadoria/campo/frente.jpg",
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

    d["perfis"]["SU-001"]["fonte"] = "especialista_de_dominio"
    d["fontes"] = [{"tipo": "especialista_de_dominio",
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
                             "fonte": "especialista_de_dominio"}
    d["fontes"] = [{"tipo": "especialista_de_dominio",
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


@pytest.mark.parametrize("campo", ["decisao", "responsavel", "data", "escopo"])
def test_aprovacao_exige_todos_os_campos(campo):
    base = dict(decisao="ok", responsavel="Bruno", data="2026-08-10",
                fonte=_fonte(), escopo=ESCOPO_APROVACAO_RECEITA)
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
        FonteEvidencia(tipo="foto", referencia=referencia, descricao="",
                       estado=EstadoConhecimento.PENDENTE)


@pytest.mark.parametrize("referencia,forma", [
    ("https://exemplo.com/catalogo.pdf", "url"),
    ("PEDIDO-2026-0451", "identificador_externo"),
])
def test_identificador_externo_e_url_nao_sao_tratados_como_caminho(referencia,
                                                                   forma):
    """A regra de caminho relativo vale para arquivo; um DOI ou uma URL não são
    caminhos e não podem ser recusados por isso."""
    f = FonteEvidencia(tipo="software_externo", referencia=referencia,
                       descricao="", estado=EstadoConhecimento.PENDENTE,
                       forma_referencia=forma)
    assert f.referencia == referencia


def test_referencia_relativa_e_aceita():
    f = FonteEvidencia(tipo="foto", referencia="curadoria/campo/a/frente.jpg",
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
