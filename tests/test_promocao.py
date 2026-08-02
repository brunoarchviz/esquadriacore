"""Sprint E.4C — promoção dos candidatos curados para a biblioteca oficial.

Cobre carregamento, validação, conflitos, simulação, atomicidade, rollback,
idempotência e manifesto. Os testes de transação exercitam o caminho de erro
de verdade (falha injetada), não apenas o caminho feliz.
"""
import copy
import json
from pathlib import Path

import pytest

from curadoria.promocao import auditoria, carregar, construir, transacao
from curadoria.promocao.carregar import (CAMINHO_ASSOCIACOES, CAMINHO_CONFIG,
                                         CAMINHO_GEOMETRIAS, PromocaoErro,
                                         calcular_hash_canonico, hash_arquivo)
from curadoria.promocao.modelos import PERFIS_E4B, CandidatoPromocao
from curadoria.promocao.validar import (validar_candidato_completo,
                                        validar_candidato_fechado,
                                        validar_contorno_externo,
                                        validar_dimensoes_aprovadas,
                                        validar_fabricante_derivado,
                                        validar_hashes_curadoria,
                                        validar_nivel_contorno,
                                        validar_su102_para_promocao,
                                        validar_topologia_aprovada,
                                        validar_vazios_internos)

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def config():
    return carregar.carregar_config_e4b(CAMINHO_CONFIG)


@pytest.fixture(scope="module")
def candidatos(config):
    return carregar.montar_candidatos(config, "E4B")


@pytest.fixture(scope="module")
def oficiais():
    return (carregar.carregar_geometrias_oficiais(CAMINHO_GEOMETRIAS),
            carregar.carregar_associacoes_oficiais(CAMINHO_ASSOCIACOES))


@pytest.fixture(scope="module")
def oficiais_antes(oficiais):
    """Baseline PRÉ-promoção, derivada da biblioteca viva removendo os oito
    registros do E.4B.

    Sem isto, os testes de simulação e transação passariam ou falhariam
    conforme a promoção já tivesse rodado — dependência de ordem que
    esconderia regressão. Aqui eles provam o comportamento sempre."""
    geo, assoc = oficiais
    novas = {f"GEO-{p}" for p in PERFIS_E4B}
    perfis = {carregar.perfil_id_oficial(p) for p in PERFIS_E4B}
    g = dict(geo, geometrias=[x for x in geo["geometrias"] if x["id"] not in novas])
    a = dict(assoc, associacoes=[x for x in assoc["associacoes"]
                                 if x["perfil_id"] not in perfis])
    return g, a


def _plano(cands, geo, assoc):
    return construir.construir_plano_promocao(cands, geo, assoc, "E4B")


def _troca(c: CandidatoPromocao, **kw) -> CandidatoPromocao:
    from dataclasses import replace
    return replace(c, **kw)


# ===========================================================================
# Carregamento
# ===========================================================================

def test_carrega_config_valido(config):
    assert "perfis" in config and "microlote_janela" in config


def test_rejeita_config_inexistente(tmp_path):
    with pytest.raises(PromocaoErro, match="ausente"):
        carregar.carregar_config_e4b(tmp_path / "nao_existe.json")


def test_rejeita_json_invalido(tmp_path):
    p = tmp_path / "ruim.json"
    p.write_text("{ isto nao e json", encoding="utf-8")
    with pytest.raises(PromocaoErro, match="JSON inválido"):
        carregar.carregar_config_e4b(p)


def test_localiza_os_oito_candidatos(candidatos):
    assert len(candidatos) == 8
    assert tuple(c.codigo_perfil for c in candidatos) == PERFIS_E4B


def test_rejeita_candidato_sem_artefato(tmp_path, config):
    (tmp_path / "SU-001").mkdir()
    with pytest.raises(PromocaoErro, match="nenhum contorno comercial"):
        carregar.montar_candidato("SU-001", config, tmp_path)


def test_reconhece_os_dois_layouts_de_artefato():
    """SU-040/041 são do lote 1 e usam prefixos numéricos; os demais não."""
    assert carregar.localizar_artefatos_candidato("SU-041")["layout"] == "legado"
    assert carregar.localizar_artefatos_candidato("SU-102")["layout"] == "atual"


def test_hash_canonico_e_determinista():
    a = {"b": 1, "a": [1.0, 2.0]}
    b = {"a": [1.0, 2.0], "b": 1}
    assert calcular_hash_canonico(a) == calcular_hash_canonico(b)
    assert calcular_hash_canonico(a) != calcular_hash_canonico({"a": [1.0, 3.0], "b": 1})


# ===========================================================================
# Validação
# ===========================================================================

def test_aceita_os_oito_candidatos_fechados(candidatos, config):
    for c in candidatos:
        r = validar_candidato_completo(c, config)
        assert r.ok, f"{c.codigo_perfil}:\n{r.descrever()}"


def test_rejeita_perfil_fora_do_microlote(candidatos, config):
    c = _troca(candidatos[0], codigo_perfil="SU-999")
    assert not validar_candidato_fechado(c, config).ok


def test_rejeita_perfil_ainda_pendente(candidatos, config):
    cfg = copy.deepcopy(config)
    cfg["microlote_janela"]["pendencia_restante"] = {"perfil": "SU-102"}
    r = validar_candidato_fechado(candidatos[0], cfg)
    assert not r.ok and "pendência" in r.falhas[0]["regra"]


def test_rejeita_dimensao_divergente(candidatos, config):
    c = _troca(candidatos[0], dimensao_nominal_mm=(99.0, 1.0))
    r = validar_dimensoes_aprovadas(c, config)
    assert not r.ok and r.falhas[0]["encontrado"] == (99.0, 1.0)


def test_rejeita_topologia_divergente(candidatos, config):
    c = _troca(candidatos[0], quantidade_vazios=7)
    r = validar_topologia_aprovada(c, config)
    assert not r.ok and r.falhas[0]["encontrado"] == 7


def test_rejeita_hash_malformado(candidatos):
    c = _troca(candidatos[0], hash_contorno="curto")
    assert not validar_hashes_curadoria(c).ok


def test_rejeita_nivel_de_contorno_incompativel(candidatos):
    c = _troca(candidatos[0], nivel_contorno="0_bruto_aproximado")
    assert not validar_nivel_contorno(c).ok


def test_rejeita_fabricante_desconhecido_pelo_contrato(candidatos):
    c = _troca(candidatos[0], fabricante="FABRICANTE_INVENTADO")
    assert not validar_fabricante_derivado(c).ok


def test_rejeita_contorno_vazio(candidatos):
    c = _troca(candidatos[0], contorno_externo=())
    assert not validar_contorno_externo(c).ok


def test_rejeita_ponto_nao_finito(candidatos):
    c = _troca(candidatos[0],
               contorno_externo=((0.0, 0.0), (1.0, 0.0), (float("inf"), 1.0)))
    assert not validar_contorno_externo(c).ok


def test_rejeita_vazio_degenerado(candidatos):
    c = _troca(candidatos[0], vazios_internos=(((0.0, 0.0), (1.0, 1.0)),))
    assert not validar_vazios_internos(c).ok


def test_falha_nomeia_perfil_regra_encontrado_esperado_e_origem(candidatos, config):
    c = _troca(candidatos[0], quantidade_vazios=99)
    f = validar_topologia_aprovada(c, config).falhas[0]
    assert set(f) == {"perfil", "regra", "encontrado", "esperado", "arquivo_origem"}
    assert f["perfil"] == candidatos[0].codigo_perfil
    assert f["arquivo_origem"].startswith("curadoria/contornos/")


# ===========================================================================
# SU-102
# ===========================================================================

def _su102(candidatos):
    return next(c for c in candidatos if c.codigo_perfil == "SU-102")


def test_su102_preserva_leitura_fisica(config):
    dec = config["perfis"]["SU-102"]["decisao_dimensional"]
    assert dec["leitura_fisica_mm"] == [16.9, 15.0]


def test_su102_usa_dimensao_nominal_oficial(candidatos):
    assert _su102(candidatos).dimensao_nominal_mm == (17.0, 15.0)


def test_su102_preserva_reprovacao_do_gate_fisico(config):
    assert config["perfis"]["SU-102"]["gate_aspecto_fisico_bruto"]["resultado"] == "REPROVADO"


def test_su102_preserva_aprovacao_do_gate_nominal(config):
    assert config["perfis"]["SU-102"]["gate_aspecto_nominal"]["resultado"] == "APROVADO"


def test_su102_preserva_arbitragem_de_dominio(candidatos, config):
    c = _su102(candidatos)
    assert validar_su102_para_promocao(c, config).ok
    assert c.decisao_curadoria == "APROVADO_POR_ARBITRAGEM_DE_DOMINIO_COM_NOMINALIZACAO"


def test_su102_nominalizacao_e_anisotropica(config):
    n = config["perfis"]["SU-102"]["normalizacao_dimensional"]
    assert n["anisotropica"] is True
    assert n["fator_x"] != n["fator_y"]


def test_su102_e_tms102_compartilham_identidade(config):
    ident = config["perfis"]["SU-102"]["identidade_de_perfil"]
    assert ident["confirmada"] is True
    assert sorted(ident["codigos_equivalentes"]) == ["SU-102", "TMS-102"]


def test_tms102_nao_e_declarado_como_medido_separadamente(config):
    ap = config["perfis"]["SU-102"]["candidato_compartilhamento"]["aplicacao_dimensional"]
    assert ap["tms102_medido_separadamente"] is False


def test_validador_su102_pega_gate_fisico_alterado(candidatos, config):
    cfg = copy.deepcopy(config)
    cfg["perfis"]["SU-102"]["gate_aspecto_fisico_bruto"]["resultado"] = "APROVADO"
    r = validar_su102_para_promocao(_su102(candidatos), cfg)
    assert not r.ok and "gate físico" in r.falhas[0]["regra"]


def test_validador_su102_pega_identidade_revogada(candidatos, config):
    cfg = copy.deepcopy(config)
    cfg["perfis"]["SU-102"]["identidade_de_perfil"]["confirmada"] = False
    assert not validar_su102_para_promocao(_su102(candidatos), cfg).ok


def test_nao_cria_geometria_duplicada_para_tms102(candidatos, oficiais):
    plano = _plano(candidatos, *oficiais)
    ids = {p.id for p in plano.geometrias_novas} | set(plano.geometrias_reutilizadas)
    assert "GEO-TMS-102" not in ids
    assert "GEO-SU-102" in ids


def test_alias_exige_identidade_confirmada():
    assert construir.construir_associacao_alias_identico("TMS-102", "GEO-SU-102", False) is None
    a = construir.construir_associacao_alias_identico("TMS-102", "GEO-SU-102", True)
    assert a.geometria_padrao_id == "GEO-SU-102"


# ===========================================================================
# IDs e associações
# ===========================================================================

def test_gera_os_oito_ids_esperados(candidatos):
    assert [c.id_geometria for c in candidatos] == [f"GEO-{p}" for p in PERFIS_E4B]


def test_detecta_colisao_de_id_divergente(candidatos, oficiais):
    geo, _ = oficiais
    g2 = copy.deepcopy(geo)
    g2["geometrias"].append({"id": "GEO-SU-001", "descricao": "outra coisa",
                             "status": "homologada", "versao": "9",
                             "familia_mercado": "X", "curado_por": "?",
                             "data_curadoria": "2000-01-01", "_nota": ""})
    prop = construir.construir_geometria_oficial(candidatos[0])
    conf = construir.detectar_colisao_id_geometria(prop, g2)
    assert conf is not None and conf.bloqueante


def test_aceita_id_existente_identico(candidatos, oficiais):
    geo, _ = oficiais
    prop = construir.construir_geometria_oficial(candidatos[0])
    g2 = copy.deepcopy(geo)
    g2["geometrias"].append(prop.registro)
    conf = construir.detectar_colisao_id_geometria(prop, g2)
    assert conf is not None and not conf.bloqueante


def test_detecta_perfil_associado_a_outra_geometria(candidatos, oficiais_antes):
    _, assoc = oficiais_antes
    a2 = copy.deepcopy(assoc)
    a2["associacoes"].append({"perfil_id": "ALCOA-SU-001",
                              "geometria_padrao_id": "GEO-OUTRA",
                              "responsavel_homologacao": "x",
                              "metodo_validacao": "x", "data": "2000-01-01",
                              "nivel_de_confianca": "alto", "observacoes": None})
    props = [construir.construir_associacao_perfil_geometria(candidatos[0])]
    conflitos = construir.detectar_reutilizacao_incompativel(props, a2)
    assert conflitos and conflitos[0].bloqueante


def test_detecta_ids_duplicados_no_plano(candidatos):
    p = construir.construir_geometria_oficial(candidatos[0])
    assert construir.detectar_ids_duplicados([p, p])


def test_detecta_perfis_duplicados_no_plano(candidatos):
    a = construir.construir_associacao_perfil_geometria(candidatos[0])
    assert construir.detectar_perfis_duplicados([a, a])


# ===========================================================================
# Simulação
# ===========================================================================

def test_simulacao_promove_exatamente_oito(candidatos, oficiais_antes):
    geo, assoc = oficiais_antes
    sim = transacao.simular_promocao(_plano(candidatos, geo, assoc), geo, assoc)
    assert len(sim.ids_criados) == 8
    assert sim.geometrias_depois == sim.geometrias_antes + 8
    assert sim.associacoes_depois == sim.associacoes_antes + 8
    assert sim.aprovada


def test_simulacao_preserva_todos_os_registros_anteriores(candidatos, oficiais_antes):
    geo, assoc = oficiais_antes
    sim = transacao.simular_promocao(_plano(candidatos, geo, assoc), geo, assoc)
    assert sim.registros_antigos_alterados == ()


def test_simulacao_nao_escreve_no_disco(candidatos, oficiais):
    antes = (hash_arquivo(CAMINHO_GEOMETRIAS), hash_arquivo(CAMINHO_ASSOCIACOES))
    geo, assoc = oficiais
    transacao.simular_promocao(_plano(candidatos, geo, assoc), geo, assoc)
    assert (hash_arquivo(CAMINHO_GEOMETRIAS), hash_arquivo(CAMINHO_ASSOCIACOES)) == antes


def test_segunda_simulacao_produz_diff_vazio(candidatos, oficiais_antes):
    geo, assoc = oficiais_antes
    sim = transacao.simular_promocao(_plano(candidatos, geo, assoc), geo, assoc)
    idem = transacao.verificar_idempotencia_simulada(sim, candidatos, _plano)
    assert idem.ok, idem.descrever()


def test_simulacao_bloqueia_se_registro_antigo_mudar(candidatos, oficiais):
    """Prova que o gate morde: adultera um registro antigo no resultado."""
    geo, assoc = oficiais
    g2 = copy.deepcopy(geo)
    g2["geometrias"][0] = dict(g2["geometrias"][0], descricao="ADULTERADO")
    alterados = transacao.verificar_preservacao_registros_existentes(
        geo, g2, "geometrias", "id", set())
    assert alterados == (geo["geometrias"][0]["id"],)


def test_ordem_dos_candidatos_nao_altera_o_resultado(candidatos, oficiais_antes):
    geo, assoc = oficiais_antes
    a = _plano(candidatos, geo, assoc)
    b = _plano(tuple(reversed(candidatos)), geo, assoc)
    assert ({p.id for p in a.geometrias_novas} == {p.id for p in b.geometrias_novas})
    assert (calcular_hash_canonico(sorted(p.registro["id"] for p in a.geometrias_novas))
            == calcular_hash_canonico(sorted(p.registro["id"] for p in b.geometrias_novas)))


# ===========================================================================
# Transação: escrita atômica e rollback
# ===========================================================================

@pytest.fixture
def copias(tmp_path, oficiais_antes):
    """Cópias no estado PRÉ-promoção, para que a transação tenha o que gravar."""
    geo, assoc = oficiais_antes
    g = tmp_path / "geometrias.json"
    a = tmp_path / "perfil_geometria.json"
    g.write_text(json.dumps(geo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    a.write_text(json.dumps(assoc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return g, a


def _sim_para(copias, candidatos):
    g, a = copias
    geo = carregar.carregar_geometrias_oficiais(g)
    assoc = carregar.carregar_associacoes_oficiais(a)
    plano = _plano(candidatos, geo, assoc)
    return plano, transacao.simular_promocao(plano, geo, assoc)


def test_grava_os_dois_arquivos_em_sucesso(copias, candidatos):
    g, a = copias
    plano, sim = _sim_para(copias, candidatos)
    estado, h0, h1 = transacao.aplicar_promocao_transacional(plano, g, a, sim)
    assert estado.aplicado and not estado.rollback_executado
    assert h1 != h0
    assert len(json.loads(g.read_text())["geometrias"]) == sim.geometrias_depois
    assert len(json.loads(a.read_text())["associacoes"]) == sim.associacoes_depois


@pytest.mark.parametrize("ponto", ["apos_primeiro_temporario",
                                   "entre_os_dois_replaces",
                                   "na_validacao_pos_gravacao"])
def test_falha_em_qualquer_ponto_restaura_os_dois_arquivos(copias, candidatos, ponto):
    g, a = copias
    h0 = (hash_arquivo(g), hash_arquivo(a))
    plano, sim = _sim_para(copias, candidatos)
    estado, _, _ = transacao.aplicar_promocao_transacional(
        plano, g, a, sim, falha_injetada=ponto)
    assert not estado.aplicado and estado.rollback_executado
    assert (hash_arquivo(g), hash_arquivo(a)) == h0, "rollback não restaurou tudo"
    json.loads(g.read_text())          # não pode ficar JSON parcial
    json.loads(a.read_text())


def test_temporarios_nao_permanecem_apos_sucesso(copias, candidatos):
    g, a = copias
    plano, sim = _sim_para(copias, candidatos)
    transacao.aplicar_promocao_transacional(plano, g, a, sim)
    restos = [p.name for p in g.parent.iterdir() if p.suffix == ".tmp"]
    assert restos == []


def test_promocao_repetida_e_idempotente(copias, candidatos):
    g, a = copias
    plano, sim = _sim_para(copias, candidatos)
    transacao.aplicar_promocao_transacional(plano, g, a, sim)
    h1 = (hash_arquivo(g), hash_arquivo(a))
    plano2, sim2 = _sim_para(copias, candidatos)
    assert sim2.ids_criados == () and sim2.associacoes_criadas == ()
    assert (hash_arquivo(g), hash_arquivo(a)) == h1


def test_escrita_usa_o_mesmo_filesystem_do_destino(tmp_path):
    destino = tmp_path / "x.json"
    destino.write_text("{}", encoding="utf-8")
    tmp = transacao.escrever_json_temporario(destino, {"a": 1})
    assert tmp.parent == destino.parent, "temporário fora do dir do destino"
    tmp.unlink()


# ===========================================================================
# Manifesto
# ===========================================================================

@pytest.fixture(scope="module")
def manifesto():
    p = RAIZ / "curadoria/promocoes/e4c/manifesto_promocao_e4b.json"
    if not p.exists():
        pytest.skip("manifesto ainda não gerado")
    return json.loads(p.read_text(encoding="utf-8"))


def test_manifesto_tem_os_oito_perfis(manifesto):
    assert manifesto["perfis"] == list(PERFIS_E4B)
    assert len(manifesto["geometrias"]) == 8


def test_manifesto_tem_hashes_antes_e_depois(manifesto):
    assert manifesto["hash_antes"] and manifesto["hash_depois"]
    if manifesto.get("reconstruido_apos_gravacao"):
        # manifesto refeito sobre dados JÁ promovidos: nada foi escrito, logo
        # antes == depois é o registro honesto do que aconteceu
        assert manifesto["hash_antes"] == manifesto["hash_depois"]
    else:
        assert manifesto["hash_antes"] != manifesto["hash_depois"]


def test_manifesto_registra_decisao_especial_do_su102(manifesto):
    s = manifesto["su102"]
    assert s["leitura_fisica_mm"] == [16.9, 15.0]
    assert s["dimensao_nominal_mm"] == [17.0, 15.0]
    assert s["gate_aspecto_fisico_bruto"] == "REPROVADO"
    assert s["gate_aspecto_nominal"] == "APROVADO"
    assert s["decisao"] == "APROVADO_POR_ARBITRAGEM_DE_DOMINIO_COM_NOMINALIZACAO"


def test_manifesto_nao_afirma_medicao_separada_do_tms102(manifesto):
    assert manifesto["su102"]["tms102_medido_separadamente"] is False


def test_manifesto_nao_cria_geo_tms102(manifesto):
    assert manifesto["su102"]["geo_tms102_criado"] is False
    assert "GEO-TMS-102" not in manifesto["geometrias"]


def test_manifesto_nao_tem_caminho_absoluto(manifesto):
    texto = json.dumps(manifesto, ensure_ascii=False)
    assert "/home/" not in texto and "C:\\" not in texto


def test_manifesto_registra_gates_zerados(manifesto):
    g = manifesto["gates"]
    assert g["registros_antigos_alterados"] == 0
    assert g["bloqueios"] == 0
    assert g["associacoes_orfas"] == 0


# ===========================================================================
# Integração com o contrato de consumo (pós-promoção)
# ===========================================================================

@pytest.fixture(scope="module")
def biblioteca():
    from contrato.consumo import carregar_biblioteca
    return carregar_biblioteca(str(CAMINHO_GEOMETRIAS), str(CAMINHO_ASSOCIACOES))


@pytest.fixture(scope="module")
def promovidas(biblioteca):
    return {g.codigo: g for g in biblioteca.geometrias
            if g.codigo in {f"GEO-{p}" for p in PERFIS_E4B}}


def test_contrato_carrega_as_oito_novas_geometrias(promovidas):
    assert len(promovidas) == 8


def test_contrato_carrega_geometria_su102(promovidas):
    g = promovidas["GEO-SU-102"]
    assert g.renderizavel and g.contorno_externo
    assert g.bounding_box is not None


def test_contrato_preserva_bounding_box_como_objeto(promovidas):
    from contrato.consumo import BoundingBoxDTO
    for g in promovidas.values():
        assert isinstance(g.bounding_box, BoundingBoxDTO), g.codigo


def test_contrato_preserva_biblioteca_imutavel(biblioteca):
    assert isinstance(biblioteca.geometrias, tuple)
    assert isinstance(biblioteca.associacoes, tuple)
    with pytest.raises((AttributeError, TypeError)):
        biblioteca.geometrias[0].codigo = "X"


def test_associacoes_apontam_para_geometrias_existentes(biblioteca):
    ids = {g.codigo for g in biblioteca.geometrias}
    for a in biblioteca.associacoes:
        assert a.geometria_padrao_id in ids, a.perfil_id


def test_nenhuma_associacao_fica_orfa(biblioteca):
    ids = {g.codigo for g in biblioteca.geometrias}
    assert [a.perfil_id for a in biblioteca.associacoes
            if a.geometria_padrao_id not in ids] == []


def test_geometrias_antigas_permanecem_iguais(biblioteca):
    """As 46 anteriores continuam carregando; a promoção só acrescentou."""
    novas = {f"GEO-{p}" for p in PERFIS_E4B}
    antigas = [g for g in biblioteca.geometrias if g.codigo not in novas]
    assert len(antigas) == 46


def test_todos_os_ids_da_biblioteca_sao_unicos(biblioteca):
    ids = [g.codigo for g in biblioteca.geometrias]
    assert len(ids) == len(set(ids))


def test_nenhum_perfil_tem_duas_associacoes_incompativeis(biblioteca):
    import collections
    por_perfil = collections.defaultdict(set)
    for a in biblioteca.associacoes:
        por_perfil[a.perfil_id].add(a.geometria_padrao_id)
    conflitos = {p: g for p, g in por_perfil.items() if len(g) > 1}
    assert not conflitos, conflitos


# ===========================================================================
# Propriedades/invariantes dos oito perfis
# ===========================================================================

@pytest.mark.parametrize("perfil", PERFIS_E4B)
def test_geometria_promovida_tem_id_esperado(perfil, promovidas):
    assert f"GEO-{perfil}" in promovidas


@pytest.mark.parametrize("perfil", PERFIS_E4B)
def test_geometria_promovida_tem_dimensao_aprovada(perfil, promovidas, config):
    p = config["perfis"][perfil]
    bb = promovidas[f"GEO-{perfil}"].bounding_box
    assert bb.largura == pytest.approx(p["largura_mm"], abs=0.05), perfil
    assert bb.altura == pytest.approx(p["altura_mm"], abs=0.05), perfil
    assert bb.largura > 0 and bb.altura > 0


@pytest.mark.parametrize("perfil", PERFIS_E4B)
def test_geometria_promovida_preserva_contorno(perfil, promovidas, candidatos):
    """Ponto a ponto contra o artefato curado — sem novo arredondamento."""
    c = next(x for x in candidatos if x.codigo_perfil == perfil)
    g = promovidas[f"GEO-{perfil}"]
    r = construir.comparar_contornos_exatamente(c.contorno_externo, g.contorno_externo)
    assert r.ok, r.descrever()


@pytest.mark.parametrize("perfil", PERFIS_E4B)
def test_geometria_promovida_preserva_topologia(perfil, promovidas, config):
    esperado = config["perfis"][perfil]["vazios_esperados"]
    assert len(promovidas[f"GEO-{perfil}"].vazios_internos) == esperado


@pytest.mark.parametrize("perfil", PERFIS_E4B)
def test_geometria_promovida_tem_associacao(perfil, biblioteca):
    pid = carregar.perfil_id_oficial(perfil)
    achadas = [a for a in biblioteca.associacoes if a.perfil_id == pid]
    assert len(achadas) == 1, f"{pid}: {len(achadas)} associações"
    assert achadas[0].geometria_padrao_id == f"GEO-{perfil}"


@pytest.mark.parametrize("perfil", PERFIS_E4B)
def test_geometria_promovida_e_renderizavel(perfil, promovidas):
    g = promovidas[f"GEO-{perfil}"]
    assert g.nivel_contorno == "2_renderizavel_comercial"
    assert g.renderizavel is True


def test_serializacao_da_biblioteca_e_determinista():
    a = CAMINHO_GEOMETRIAS.read_bytes()
    b = CAMINHO_GEOMETRIAS.read_bytes()
    assert calcular_hash_canonico(json.loads(a)) == calcular_hash_canonico(json.loads(b))


def test_escrita_preserva_a_indentacao_do_arquivo_oficial(tmp_path):
    """A promoção é aditiva. Reescrever o arquivo inteiro só porque o
    serializador tem outro default produziria um diff de 24 mil linhas e
    esconderia qualquer alteração real de geometria."""
    destino = tmp_path / "oficial.json"
    destino.write_text(json.dumps({"a": [1, 2]}, indent=1) + "\n", encoding="utf-8")
    assert transacao.detectar_indentacao(destino) == 1
    tmp = transacao.escrever_json_temporario(destino, {"a": [1, 2], "b": 3})
    linhas = tmp.read_text(encoding="utf-8").splitlines()
    assert linhas[1].startswith(' "'), "indentação do original não foi preservada"
    tmp.unlink()


def test_dados_oficiais_mantem_indentacao_de_origem():
    """Os arquivos publicados continuam no formato em que sempre estiveram."""
    for caminho in (CAMINHO_GEOMETRIAS, CAMINHO_ASSOCIACOES):
        assert transacao.detectar_indentacao(caminho) == 1, caminho.name


# ===========================================================================
# Journal e recuperação após encerramento abrupto
# ===========================================================================

from curadoria.promocao import integridade, journal          # noqa: E402
from curadoria.promocao.transacao import InterrupcaoSimulada  # noqa: E402


def _dir(copias):
    return copias[0].parent


def test_sucesso_normal_nao_deixa_journal_nem_backup(copias, candidatos):
    g, a = copias
    plano, sim = _sim_para(copias, candidatos)
    estado, _, _ = transacao.aplicar_promocao_transacional(plano, g, a, sim)
    assert estado.aplicado
    assert journal.pendente(_dir(copias)) is None
    restos = [p.name for p in g.parent.iterdir() if p.name.startswith(".")]
    assert restos == [], f"sobras: {restos}"


@pytest.mark.parametrize("ponto,estado_esperado", [
    ("apos_journal", journal.PREPARADA),
    ("apos_primeiro_replace", journal.GEOMETRIAS_SUBSTITUIDAS),
    ("apos_ambos_replaces", journal.AMBOS_SUBSTITUIDOS),
])
def test_interrupcao_abrupta_deixa_journal_recuperavel(copias, candidatos,
                                                       ponto, estado_esperado):
    """Simula SIGKILL: sai sem rollback, como um processo morto faria."""
    g, a = copias
    h0 = (hash_arquivo(g), hash_arquivo(a))
    plano, sim = _sim_para(copias, candidatos)
    with pytest.raises(InterrupcaoSimulada):
        transacao.aplicar_promocao_transacional(plano, g, a, sim,
                                                interromper_em=ponto)
    pend = journal.pendente(_dir(copias))
    assert pend is not None and pend["estado"] == estado_esperado

    # nova "execução" encontra o journal e recupera
    rel = journal.recuperar(_dir(copias))
    assert rel["ok"] and rel["acao"] == "restaurado"
    assert (hash_arquivo(g), hash_arquivo(a)) == h0, "não voltou ao original"
    assert journal.pendente(_dir(copias)) is None
    json.loads(g.read_text()); json.loads(a.read_text())


def test_interrupcao_apos_primeiro_replace_deixa_destinos_dessincronizados(
        copias, candidatos):
    """Prova que a janela existe de verdade — é o que o journal cobre."""
    g, a = copias
    h0g = hash_arquivo(g)
    plano, sim = _sim_para(copias, candidatos)
    with pytest.raises(InterrupcaoSimulada):
        transacao.aplicar_promocao_transacional(
            plano, g, a, sim, interromper_em="apos_primeiro_replace")
    assert hash_arquivo(g) != h0g, "geometrias deveria ter sido substituída"
    assert len(json.loads(a.read_text())["associacoes"]) == sim.associacoes_antes
    journal.recuperar(_dir(copias))


def test_promover_recusa_enquanto_houver_journal_pendente(copias, candidatos):
    g, a = copias
    plano, sim = _sim_para(copias, candidatos)
    with pytest.raises(InterrupcaoSimulada):
        transacao.aplicar_promocao_transacional(plano, g, a, sim,
                                                interromper_em="apos_journal")
    with pytest.raises(RuntimeError, match="não concluída"):
        transacao.aplicar_promocao_transacional(plano, g, a, sim)
    journal.recuperar(_dir(copias))


def test_journal_corrompido_e_recusado_sem_apagar(copias):
    j = journal.caminho_journal(_dir(copias))
    j.write_text("{ nao e json", encoding="utf-8")
    with pytest.raises(journal.JournalCorrompido, match="ilegível"):
        journal.ler(j)
    assert j.exists(), "journal ilegível não pode ser apagado silenciosamente"
    j.unlink()


def test_journal_de_versao_desconhecida_e_recusado(copias):
    j = journal.caminho_journal(_dir(copias))
    j.write_text(json.dumps({"versao": 99, "estado": "PREPARADA"}), encoding="utf-8")
    with pytest.raises(journal.JournalCorrompido, match="estrutura desconhecida"):
        journal.ler(j)
    j.unlink()


def test_backup_ausente_impede_recuperacao_e_preserva_journal(copias, candidatos):
    g, a = copias
    plano, sim = _sim_para(copias, candidatos)
    with pytest.raises(InterrupcaoSimulada):
        transacao.aplicar_promocao_transacional(
            plano, g, a, sim, interromper_em="apos_primeiro_replace")
    journal.caminho_backup(g).unlink()          # backup some
    with pytest.raises(journal.JournalCorrompido, match="backup ausente"):
        journal.recuperar(_dir(copias))
    assert journal.caminho_journal(_dir(copias)).exists(), \
        "journal não pode sumir sem recuperação confirmada"


def test_recuperar_sem_journal_e_no_op(tmp_path):
    rel = journal.recuperar(tmp_path)
    assert rel["ok"] and rel["acao"] == "nada_a_recuperar"


# ===========================================================================
# Verificador unificado — cada mutação isolada tem de ser detectada
# ===========================================================================

@pytest.fixture(scope="module")
def manifesto_real():
    return json.loads(auditoria.CAMINHO_MANIFESTO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def quatro_camadas(config, oficiais, manifesto_real, candidatos):
    geo, assoc = oficiais
    return config, geo, assoc, manifesto_real, candidatos


def test_verificador_unificado_aprova_o_estado_real(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, man, cands)
    assert r.ok, r.descrever()


def test_mutacao_no_config_e_detectada(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    c2 = copy.deepcopy(cfg)
    c2["microlote_janela"]["promocao_oficial_realizada"] = False
    assert not integridade.verificar_integridade_promocao_e4b(c2, geo, assoc, man).ok


def test_mutacao_no_id_de_geo_do_config_e_detectada(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    c2 = copy.deepcopy(cfg)
    c2["perfis"]["SU-001"]["promocao_oficial"]["id_geometria"] = "GEO-OUTRO"
    r = integridade.verificar_integridade_promocao_e4b(c2, geo, assoc, man)
    assert not r.ok and any("id_geometria" in f["regra"] for f in r.falhas)


def test_mutacao_na_geometria_e_detectada(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    g2 = copy.deepcopy(geo)
    g2["geometrias"] = [x for x in g2["geometrias"] if x["id"] != "GEO-SU-039"]
    r = integridade.verificar_integridade_promocao_e4b(cfg, g2, assoc, man)
    assert not r.ok and any("ausente" in f["regra"] for f in r.falhas)


def test_mutacao_no_contorno_promovido_e_detectada(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    g2 = copy.deepcopy(geo)
    for x in g2["geometrias"]:
        if x["id"] == "GEO-SU-102":
            x["contorno_externo"] = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]
    r = integridade.verificar_integridade_promocao_e4b(cfg, g2, assoc, man, cands)
    assert not r.ok


def test_mutacao_na_associacao_e_detectada(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    a2 = copy.deepcopy(assoc)
    for x in a2["associacoes"]:
        if x["perfil_id"] == "ALCOA-SU-053":
            x["geometria_padrao_id"] = "GEO-SU-005"
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, a2, man)
    assert not r.ok and any("GEO errado" in f["regra"] for f in r.falhas)


def test_mutacao_no_hash_do_manifesto_e_detectada(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    m2 = copy.deepcopy(man)
    m2["hash_depois"]["dados/geometrias.json"] = "0" * 64
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, m2)
    assert not r.ok and any("hash_depois" in f["regra"] for f in r.falhas)


def test_mutacao_na_contagem_do_manifesto_e_detectada(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    m2 = copy.deepcopy(man)
    m2["quantidade_depois"]["geometrias"] = 999
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, m2)
    assert not r.ok and any("quantidade_depois" in f["regra"] for f in r.falhas)


def test_mutacao_no_texto_de_estado_atual_e_detectada(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    c2 = copy.deepcopy(cfg)
    c2["perfis"]["SU-001"]["promocao_oficial"]["_obs"] = \
        "nao existe geometria oficial em dados/"
    r = integridade.verificar_integridade_promocao_e4b(c2, geo, assoc, man)
    assert not r.ok and any("contradiz" in f["regra"] for f in r.falhas)


def test_nota_historica_datada_nao_e_confundida_com_estado_atual(quatro_camadas):
    """O fato de que ANTES da promoção não existia geometria é verdadeiro e
    tem de sobreviver — a varredura não pode ser cega."""
    cfg, geo, assoc, man, cands = quatro_camadas
    c2 = copy.deepcopy(cfg)
    c2["perfis"]["SU-001"]["historico_pre_promocao"] = {
        "observacao": "nao existia geometria oficial em dados/ nesta data"}
    assert integridade.verificar_integridade_promocao_e4b(c2, geo, assoc, man, cands).ok


def test_manifesto_com_commit_descritivo_e_detectado(quatro_camadas):
    cfg, geo, assoc, man, cands = quatro_camadas
    m2 = copy.deepcopy(man)
    m2["commit_curadoria_fonte"] = "E.4B — microlote fechado com 8 perfis"
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, m2)
    assert not r.ok and any("40 hex" in f["regra"] for f in r.falhas)


def test_manifesto_tem_commits_de_procedencia_validos(manifesto_real):
    import re
    for campo in ("commit_base_main", "commit_pre_promocao", "commit_curadoria_fonte"):
        v = manifesto_real[campo]
        assert re.fullmatch(r"[0-9a-f]{40}", v), f"{campo}={v!r}"
    assert manifesto_real["commit_base_main"] == \
        "e356ba2c34b3c04711d97cbf576f3737be974af3"
    assert manifesto_real["descricao_curadoria_fonte"]


def test_manifesto_descreve_o_mecanismo_sem_prometer_atomicidade_conjunta(manifesto_real):
    m = manifesto_real["mecanismo_transacional"]
    assert m["substituicao_atomica_por_arquivo"] is True
    assert m["commit_atomico_conjunto"] is False
    assert m["journal_persistente"] is True
    assert m["recuperacao_apos_encerramento_abrupto"] is True


def test_campo_de_pontos_tem_nome_honesto(candidatos):
    """`quantidade_componentes` recebia len(contorno) — era contagem de pontos."""
    c = candidatos[0]
    assert c.quantidade_pontos_contorno_externo == len(c.contorno_externo)
    assert not hasattr(c, "quantidade_componentes")
