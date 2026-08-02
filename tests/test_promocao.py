"""Sprint E.4C — promoção dos candidatos curados para a biblioteca oficial.

Cobre carregamento, validação, conflitos, simulação, atomicidade, rollback,
idempotência e manifesto. Os testes de transação exercitam o caminho de erro
de verdade (falha injetada), não apenas o caminho feliz.
"""
import copy
import json
from pathlib import Path

import pytest

from curadoria.promocao import (auditoria, carregar, construir, evento,
                                finalizacao, integridade, journal, transacao)
from curadoria.promocao.config_promovido import (ConfigInesperado,
                                                 construir_config_promovido_e4b)
from curadoria.promocao.transacao import InterrupcaoSimulada
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

REL_CONFIG = "curadoria/aquisicao/configs/e4b_suprema.json"
REL_MANIFESTO = "curadoria/promocoes/e4c/manifesto_promocao_e4b.json"


class ArvoreIsolada:
    """Árvore de trabalho no estado PRÉ-promoção, materializada do git.

    Não é derivada do estado promovido removendo campos: é o conteúdo exato do
    commit anterior à gravação. Derivar esconderia justamente o que a auditoria
    encontrou — um config que a transação nunca escreveu."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.geometrias = raiz / "dados/geometrias.json"
        self.associacoes = raiz / "dados/perfil_geometria.json"
        self.config = raiz / REL_CONFIG
        self.manifesto = raiz / REL_MANIFESTO

    @property
    def dir_dados(self):
        return self.geometrias.parent

    def carregar(self):
        return (carregar.carregar_config_e4b(self.config),
                carregar.carregar_geometrias_oficiais(self.geometrias),
                carregar.carregar_associacoes_oficiais(self.associacoes))

    def verificador(self, cands):
        def verificar():
            cfg, geo, assoc = self.carregar()
            man = json.loads(self.manifesto.read_text(encoding="utf-8"))
            return integridade.verificar_integridade_promocao_e4b(
                cfg, geo, assoc, man, cands)
        return verificar


@pytest.fixture
def arvore(tmp_path):
    import subprocess
    raiz = tmp_path / "arvore"
    arv = ArvoreIsolada(raiz)
    for rel in ("dados/geometrias.json", "dados/perfil_geometria.json", REL_CONFIG):
        alvo = raiz / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(["git", "show", f"{evento.COMMIT_PRE_PROMOCAO}:{rel}"],
                             cwd=RAIZ, capture_output=True)
        assert out.returncode == 0, out.stderr.decode()[:400]
        alvo.write_bytes(out.stdout)
    # o estado inicial tem de ser mesmo o do evento — senão o teste integral
    # provaria outra coisa
    assert hash_arquivo(arv.geometrias) == evento.HASH_ANTES[evento.REL_GEOMETRIAS]
    assert hash_arquivo(arv.associacoes) == evento.HASH_ANTES[evento.REL_ASSOCIACOES]
    assert not arv.manifesto.exists()
    return arv


@pytest.fixture
def copias(arvore):
    return arvore.geometrias, arvore.associacoes


def _sim_para(copias, candidatos):
    g, a = copias
    geo = carregar.carregar_geometrias_oficiais(g)
    assoc = carregar.carregar_associacoes_oficiais(a)
    plano = _plano(candidatos, geo, assoc)
    return plano, transacao.simular_promocao(plano, geo, assoc)


def _documentos(arvore, candidatos):
    cfg, geo, assoc = arvore.carregar()
    plano = _plano(candidatos, geo, assoc)
    sim = transacao.simular_promocao(plano, geo, assoc)
    docs = finalizacao.planejar_documentos(
        sim, cfg, candidatos, arvore.geometrias, arvore.associacoes,
        arvore.config)
    return plano, sim, docs


def _aplicar(arvore, candidatos, **kw):
    """Transação completa dos QUATRO artefatos sobre a árvore isolada."""
    plano, sim, docs = _documentos(arvore, candidatos)
    finalizar = kw.pop("finalizar", None)
    if finalizar is None:
        def finalizar(j):
            return finalizacao.retomar_finalizacao(
                j, arvore.raiz, docs, arvore.verificador(candidatos),
                interrupcao=InterrupcaoSimulada,
                falha_injetada=kw.get("falha_injetada", ""),
                interromper_em=kw.get("interromper_em", ""))
    return transacao.aplicar_promocao_transacional(
        plano, arvore.geometrias, arvore.associacoes, sim, docs,
        caminho_config=arvore.config, caminho_manifesto=arvore.manifesto,
        finalizar=finalizar, raiz=arvore.raiz, **kw)


def test_grava_os_dois_arquivos_em_sucesso(arvore, candidatos):
    g, a = arvore.geometrias, arvore.associacoes
    _, sim, _ = _documentos(arvore, candidatos)
    estado, h0, h1 = _aplicar(arvore, candidatos)
    assert estado.aplicado and not estado.rollback_executado
    assert h1 != h0
    assert len(json.loads(g.read_text())["geometrias"]) == sim.geometrias_depois
    assert len(json.loads(a.read_text())["associacoes"]) == sim.associacoes_depois


@pytest.mark.parametrize("ponto", ["apos_primeiro_temporario",
                                   "entre_os_dois_replaces",
                                   "na_validacao_pos_gravacao"])
def test_falha_em_qualquer_ponto_restaura_os_dois_arquivos(arvore, candidatos, ponto):
    g, a = arvore.geometrias, arvore.associacoes
    h0 = (hash_arquivo(g), hash_arquivo(a))
    estado, _, _ = _aplicar(arvore, candidatos, falha_injetada=ponto)
    assert not estado.aplicado
    assert (hash_arquivo(g), hash_arquivo(a)) == h0, "rollback não restaurou tudo"
    json.loads(g.read_text())          # não pode ficar JSON parcial
    json.loads(a.read_text())


def test_temporarios_nao_permanecem_apos_sucesso(arvore, candidatos):
    _aplicar(arvore, candidatos)
    restos = [p.name for p in arvore.dir_dados.iterdir() if p.suffix == ".tmp"]
    assert restos == []


def test_promocao_repetida_e_idempotente(arvore, candidatos):
    g, a = arvore.geometrias, arvore.associacoes
    _aplicar(arvore, candidatos)
    h1 = (hash_arquivo(g), hash_arquivo(a))
    plano2, sim2 = _sim_para((g, a), candidatos)
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
    """Os hashes descrevem o EVENTO. Uma reconstrução não os iguala — se
    igualasse, o manifesto estaria descrevendo a si mesmo em vez da promoção."""
    assert manifesto["hash_antes"] and manifesto["hash_depois"]
    assert manifesto["hash_antes"] != manifesto["hash_depois"]
    assert manifesto["reconstruido_apos_gravacao"] is False


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

def _dir(copias):
    return copias[0].parent


def test_sucesso_normal_nao_deixa_journal_nem_backup(arvore, candidatos):
    estado, _, _ = _aplicar(arvore, candidatos)
    assert estado.aplicado
    assert journal.pendente(arvore.dir_dados) is None
    restos = [p.name for p in arvore.dir_dados.iterdir() if p.name.startswith(".")]
    assert restos == [], f"sobras: {restos}"
    assert not journal.caminho_backup(arvore.config).exists()
    assert not journal.caminho_backup(arvore.manifesto).exists()


@pytest.mark.parametrize("ponto,estado_esperado", [
    ("apos_journal", journal.PREPARADA),
    ("apos_primeiro_replace", journal.GEOMETRIAS_SUBSTITUIDAS),
    ("apos_ambos_replaces", journal.AMBOS_SUBSTITUIDOS),
])
def test_interrupcao_abrupta_deixa_journal_recuperavel(arvore, candidatos,
                                                       ponto, estado_esperado):
    """Simula SIGKILL: sai sem rollback, como um processo morto faria."""
    g, a = arvore.geometrias, arvore.associacoes
    h0 = (hash_arquivo(g), hash_arquivo(a))
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em=ponto)
    pend = journal.pendente(arvore.dir_dados)
    assert pend is not None and pend["estado"] == estado_esperado

    # nova "execução" encontra o journal e recupera
    rel = journal.recuperar(arvore.dir_dados, arvore.raiz)
    assert rel["ok"] and rel["acao"] == "restaurado"
    assert (hash_arquivo(g), hash_arquivo(a)) == h0, "não voltou ao original"
    assert journal.pendente(arvore.dir_dados) is None
    json.loads(g.read_text()); json.loads(a.read_text())


def test_interrupcao_apos_primeiro_replace_deixa_destinos_dessincronizados(
        arvore, candidatos):
    """Prova que a janela existe de verdade — é o que o journal cobre."""
    g, a = arvore.geometrias, arvore.associacoes
    h0g = hash_arquivo(g)
    _, sim, _ = _documentos(arvore, candidatos)
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_primeiro_replace")
    assert hash_arquivo(g) != h0g, "geometrias deveria ter sido substituída"
    assert len(json.loads(a.read_text())["associacoes"]) == sim.associacoes_antes
    journal.recuperar(arvore.dir_dados, arvore.raiz)


def test_promover_recusa_enquanto_houver_journal_pendente(arvore, candidatos):
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_journal")
    with pytest.raises(RuntimeError, match="não concluída"):
        _aplicar(arvore, candidatos)
    journal.recuperar(arvore.dir_dados, arvore.raiz)


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


@pytest.mark.parametrize("faltando", ["geometrias", "associacoes"])
def test_preflight_bloqueia_sem_restaurar_nada_quando_falta_backup(
        arvore, candidatos, faltando):
    """Prova de NÃO-restauração parcial.

    Restaurar um arquivo e só então descobrir que o backup do outro sumiu
    deixaria o estado pior do que estava. O preflight roda antes de qualquer
    mutação; se reprova, zero destinos são tocados."""
    g, a = arvore.geometrias, arvore.associacoes
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_ambos_replaces")

    # ambos os destinos estão NOVOS neste ponto
    novos = (hash_arquivo(g), hash_arquivo(a))
    alvo = g if faltando == "geometrias" else a
    outro = a if faltando == "geometrias" else g
    journal.caminho_backup(alvo).unlink()
    bak_outro = journal.caminho_backup(outro)

    with pytest.raises(journal.RecuperacaoBloqueada, match="backup ausente"):
        journal.recuperar(arvore.dir_dados, arvore.raiz)

    # nada foi restaurado — nem o arquivo cujo backup ainda existe
    assert (hash_arquivo(g), hash_arquivo(a)) == novos, \
        "houve restauração parcial"
    assert journal.caminho_journal(arvore.dir_dados).exists(), "journal sumiu"
    assert bak_outro.exists(), "backup existente foi removido"
    assert journal.caminho_backup(arvore.config).exists(), \
        "backup do config foi removido apesar do preflight reprovar"


def test_preflight_bloqueia_backup_com_hash_divergente(arvore, candidatos):
    g, a = arvore.geometrias, arvore.associacoes
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_ambos_replaces")
    novos = (hash_arquivo(g), hash_arquivo(a))
    journal.caminho_backup(g).write_text('{"geometrias": []}', encoding="utf-8")
    with pytest.raises(journal.RecuperacaoBloqueada, match="hash divergente"):
        journal.recuperar(arvore.dir_dados, arvore.raiz)
    assert (hash_arquivo(g), hash_arquivo(a)) == novos


def test_recuperar_sem_journal_e_no_op(tmp_path):
    rel = journal.recuperar(tmp_path, tmp_path)
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


# ===========================================================================
# Journal CONCLUIDA abandonado e finalização retomável
# ===========================================================================

def test_journal_concluida_abandonado_nao_e_ignorado(arvore, candidatos):
    """Morte entre CONCLUIDA e a limpeza deixaria backups órfãos no disco.
    `pendente()` não pode fingir que está tudo bem."""
    g = arvore.geometrias
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_concluida")
    pend = journal.pendente(arvore.dir_dados)
    assert pend is not None and pend["estado"] == journal.CONCLUIDA
    # a limpeza passa pelo fluxo de retomada, que revalida antes de apagar —
    # chamar `journal.limpar()` direto provaria só que unlink funciona
    rel = _recuperar(arvore, candidatos)
    assert rel.estado_encontrado == journal.CONCLUIDA
    assert rel.concluida and not rel.limpeza_pendente
    assert "verificação unificada aprovada" in rel.passos
    assert journal.pendente(arvore.dir_dados) is None
    assert not journal.caminho_backup(g).exists()


def test_interrupcao_apos_dados_validos_mantem_dados_novos(arvore, candidatos):
    """A partir de DADOS_VALIDOS a estratégia é retomar, não desfazer: os dados
    já foram validados e desfazê-los perderia trabalho verificado."""
    g = arvore.geometrias
    _, sim, _ = _documentos(arvore, candidatos)
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_dados_validos")
    pend = journal.pendente(arvore.dir_dados)
    assert pend["estado"] == journal.DADOS_VALIDOS
    assert pend["estado"] in journal.ESTADOS_FINALIZAVEIS
    assert pend["estado"] not in journal.ESTADOS_ROLLBACK
    assert len(json.loads(g.read_text())["geometrias"]) == sim.geometrias_depois
    journal.limpar(arvore.dir_dados, arvore.raiz)


def test_journal_carrega_recibo_suficiente_para_o_manifesto(arvore, candidatos):
    """hash_antes, quantidade_antes e ids_criados NÃO podem ser inferidos
    depois da gravação — por isso viajam no journal."""
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_dados_validos")
    rec = journal.pendente(arvore.dir_dados)["evento_promocao"]
    assert rec["quantidade_antes"] == {"geometrias": 46, "associacoes": 245}
    assert rec["quantidade_depois"] == {"geometrias": 54, "associacoes": 253}
    assert len(rec["ids_criados"]) == 8
    assert len(rec["associacoes_criadas"]) == 8
    assert rec["commit_pre_promocao"] == evento.COMMIT_PRE_PROMOCAO
    assert rec["hash_antes"] != rec["hash_esperado_depois"]
    journal.limpar(arvore.dir_dados, arvore.raiz)


def test_journal_registra_config_e_manifesto(arvore, candidatos):
    """A finalização auditável tem de estar sob o mesmo journal."""
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_journal")
    arq = journal.pendente(arvore.dir_dados)["arquivos"]
    assert set(arq) == {"geometrias", "associacoes", "config", "manifesto"}
    assert arq["config"]["existia_antes"] is True
    assert arq["manifesto"]["existia_antes"] is False
    assert arq["manifesto"]["backup"] is None
    journal.recuperar(arvore.dir_dados, arvore.raiz)


def test_journal_tem_hash_final_dos_quatro_papeis(arvore, candidatos):
    """Sem hash final para config e manifesto, o journal conheceria os quatro
    caminhos sem conseguir confirmar o conteúdo final de nenhum dos dois."""
    _, _, docs = _documentos(arvore, candidatos)
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_journal")
    arq = journal.pendente(arvore.dir_dados)["arquivos"]
    for papel in journal.PAPEIS:
        h = arq[papel]["hash_esperado_depois"]
        assert h and len(h) == 64, papel
        assert h == docs.hashes[papel], papel
    journal.recuperar(arvore.dir_dados, arvore.raiz)


def test_journal_sem_hash_final_de_config_e_recusado(arvore, candidatos):
    _, _, docs = _documentos(arvore, candidatos)
    parciais = dict(docs.hashes)
    parciais["config"] = None
    with pytest.raises(ValueError, match="hash final esperado"):
        journal.preparar(
            {"geometrias": arvore.geometrias, "associacoes": arvore.associacoes,
             "config": arvore.config, "manifesto": arvore.manifesto},
            parciais, evento.recibo_evento(), arvore.raiz)


def test_rollback_remove_manifesto_que_nao_existia(arvore, candidatos):
    """Sem backup para restaurar: rollback = remover o arquivo criado."""
    man = arvore.manifesto
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_primeiro_replace")
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text('{"parcial": true}', encoding="utf-8")   # criado no meio
    rel = journal.recuperar(arvore.dir_dados, arvore.raiz)
    assert "manifesto" in rel["removidos"]
    assert not man.exists()


# ===========================================================================
# O manifesto rastreado real não pode ser alterado pelos testes
# ===========================================================================

def test_manifesto_rastreado_descreve_o_evento_e_nao_o_disco_atual(manifesto):
    assert manifesto["quantidade_antes"] == {"geometrias": 46, "associacoes": 245}
    assert manifesto["quantidade_depois"] == {"geometrias": 54, "associacoes": 253}
    assert manifesto["quantidade_antes"] != manifesto["quantidade_depois"], \
        "54 -> 54 não é promoção"
    assert list(manifesto["ids_criados"]) == [f"GEO-{p}" for p in PERFIS_E4B]
    assert list(manifesto["associacoes_criadas"]) == [f"ALCOA-{p}" for p in PERFIS_E4B]
    assert manifesto["ids_reutilizados"] == []
    assert manifesto["associacoes_reutilizadas"] == []


def test_commit_pre_promocao_e_o_do_evento_nao_o_head(manifesto):
    """HEAD muda a cada commit novo; o evento não."""
    import subprocess
    assert manifesto["commit_pre_promocao"] == \
        "53fcfaca7ba89ccc1c7a0fc8c52a7e6efc18dc76"
    assert manifesto["commit_pre_promocao"] != "2d918acb44745ce91b5fac56d58fc48c4d55957f"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ,
                          capture_output=True, text=True).stdout.strip()
    assert manifesto["commit_pre_promocao"] != head, \
        "commit_pre_promocao virou o HEAD atual — descreve a execução, não o evento"


def test_manifesto_registra_capacidade_de_reconstrucao_separadamente(manifesto):
    c = manifesto["capacidade_reconstrucao_manifesto"]
    assert c["testada"] is True and c["resultado"] == "APROVADA"
    assert manifesto["reconstruido_apos_gravacao"] is False


def test_suite_de_recuperacao_nao_altera_o_manifesto_rastreado():
    """Roda os cenários de crash e confere que o manifesto do repositório
    continua byte a byte igual. Nenhum teste pode apagá-lo."""
    antes = hash_arquivo(auditoria.CAMINHO_MANIFESTO)
    import subprocess
    subprocess.run(
        [".venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_promocao.py", "-k",
         "journal or recuperar or preflight or interrupcao or crash"],
        cwd=RAIZ, capture_output=True, text=True, timeout=300)
    assert hash_arquivo(auditoria.CAMINHO_MANIFESTO) == antes, \
        "a suíte de recuperação alterou o manifesto rastreado"


# ---- mutações dos invariantes canônicos -----------------------------------

@pytest.mark.parametrize("campo,valor", [
    ("quantidade_antes", {"geometrias": 54, "associacoes": 253}),
    ("quantidade_depois", {"geometrias": 46, "associacoes": 245}),
    ("ids_criados", []),
    ("associacoes_criadas", []),
    ("ids_reutilizados", ["GEO-SU-001"]),
    ("associacoes_reutilizadas", ["ALCOA-SU-001"]),
    ("reconstruido_apos_gravacao", True),
    ("commit_pre_promocao", "2d918acb44745ce91b5fac56d58fc48c4d55957f"),
])
def test_mutacao_de_invariante_canonico_e_detectada(quatro_camadas, campo, valor):
    cfg, geo, assoc, man, cands = quatro_camadas
    m2 = copy.deepcopy(man)
    m2[campo] = valor
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, m2)
    assert not r.ok, f"{campo}={valor!r} passou sem ser detectado"


def test_hash_antes_igual_a_depois_e_detectado(quatro_camadas):
    """O sintoma exato do manifesto que descreve a si mesmo."""
    cfg, geo, assoc, man, cands = quatro_camadas
    m2 = copy.deepcopy(man)
    m2["hash_antes"] = copy.deepcopy(m2["hash_depois"])
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, m2)
    assert not r.ok and any("hash_antes" in f["regra"] for f in r.falhas)


# ===========================================================================
# Transformação do config: o que a promoção realmente escreve
# ===========================================================================

@pytest.fixture
def config_pre(arvore):
    """Config no estado PRÉ-promoção, vindo do git — não derivado do promovido."""
    cfg = carregar.carregar_config_e4b(arvore.config)
    assert cfg["microlote_janela"]["promocao_oficial_realizada"] is False
    for p in PERFIS_E4B:
        po = cfg["perfis"][p].get("promocao_oficial")
        assert not (isinstance(po, dict) and po.get("status") == "PROMOVIDO"), p
    return cfg


def test_config_pre_promocao_reprova_a_verificacao_unificada(
        config_pre, oficiais, candidatos, manifesto_real):
    """Sem esta prova, o teste integral não significaria nada: se o config
    pré-promoção já passasse, a ausência de gravação ficaria invisível."""
    geo, assoc = oficiais
    r = integridade.verificar_integridade_promocao_e4b(
        config_pre, geo, assoc, manifesto_real, candidatos)
    assert not r.ok
    assert any("promocao_oficial_realizada" in f["regra"] for f in r.falhas)


def test_transformacao_promove_os_oito_perfis(config_pre, candidatos):
    novo = construir_config_promovido_e4b(config_pre, candidatos)
    ml = novo["microlote_janela"]
    assert ml["promocao_oficial_realizada"] is True
    assert ml["lote_promocao"] == "E4C"
    assert ml["pendencia_restante"] is None
    assert ml["fechados_na_curadoria"] == 8
    assert ml["aguardando_evidencia_externa"] == 0
    for p in PERFIS_E4B:
        po = novo["perfis"][p]["promocao_oficial"]
        assert po["status"] == "PROMOVIDO"
        assert po["id_geometria"] == f"GEO-{p}"
        assert po["perfil_id_oficial"] == carregar.perfil_id_oficial(p)
        assert po["lote"] == "E4C"


def test_transformacao_nao_altera_o_config_recebido(config_pre, candidatos):
    antes = calcular_hash_canonico(config_pre)
    construir_config_promovido_e4b(config_pre, candidatos)
    assert calcular_hash_canonico(config_pre) == antes


def test_transformacao_e_idempotente(config_pre, candidatos):
    um = construir_config_promovido_e4b(config_pre, candidatos)
    dois = construir_config_promovido_e4b(um, candidatos)
    assert calcular_hash_canonico(um) == calcular_hash_canonico(dois)


def test_transformacao_reproduz_o_config_publicado(config_pre, candidatos):
    """A prova mais forte: partindo do estado pré-promoção, a função gera
    exatamente o arquivo que está publicado — byte a byte."""
    gerado = json.dumps(construir_config_promovido_e4b(config_pre, candidatos),
                        ensure_ascii=False, indent=2) + "\n"
    assert gerado == CAMINHO_CONFIG.read_text(encoding="utf-8")


def test_transformacao_preserva_o_historico_datado(config_pre, candidatos):
    novo = construir_config_promovido_e4b(config_pre, candidatos)
    h = novo["perfis"]["SU-053"]["historico_pre_promocao"]
    assert h["estado"] == "APROVADO_APENAS_NA_CURADORIA"
    assert "HISTORICO" in h["observacao"]
    for p in ("SU-001", "SU-002", "SU-003"):
        hv = novo["perfis"][p]["aprovacao_visual"]["historico_pre_promocao"]
        assert hv["data"] == "2026-07-28"


def test_transformacao_apaga_a_contradicao_de_estado_atual(config_pre, candidatos):
    novo = construir_config_promovido_e4b(config_pre, candidatos)
    assert integridade.verificar_integridade_promocao_e4b(
        novo, *oficiais_do_repo(), manifesto_do_repo(), ()).ok


def oficiais_do_repo():
    return (carregar.carregar_geometrias_oficiais(CAMINHO_GEOMETRIAS),
            carregar.carregar_associacoes_oficiais(CAMINHO_ASSOCIACOES))


def manifesto_do_repo():
    return json.loads(auditoria.CAMINHO_MANIFESTO.read_text(encoding="utf-8"))


def test_transformacao_preserva_a_arbitragem_do_su102(config_pre, candidatos):
    novo = construir_config_promovido_e4b(config_pre, candidatos)
    p = novo["perfis"]["SU-102"]
    assert p["gate_aspecto_fisico_bruto"]["dimensoes_mm"] == [16.9, 15.0]
    assert p["gate_aspecto_fisico_bruto"]["resultado"] == "REPROVADO"
    assert p["gate_aspecto_nominal"]["resultado"] == "APROVADO"
    po = p["promocao_oficial"]
    assert po["dimensao_nominal_mm"] == [17.0, 15.0]
    assert po["origem_dimensional"] == "MEDICAO_FISICA_COM_NOMINALIZACAO_POR_DOMINIO"
    assert po["identidade_tms102"] == "CONFIRMADA"
    assert po["geo_tms102_criado"] is False


def test_transformacao_recusa_nota_desconhecida(config_pre, candidatos):
    """Não sobrescreve texto que ninguém revisou."""
    c2 = copy.deepcopy(config_pre)
    c2["microlote_janela"]["_nota_contagem"] = "outra coisa qualquer"
    with pytest.raises(ConfigInesperado, match="texto inesperado"):
        construir_config_promovido_e4b(c2, candidatos)


# ===========================================================================
# Teste integral: 46/245 e config NÃO promovido -> 54/253 e config promovido
# ===========================================================================

def test_promocao_integral_a_partir_do_estado_pre_promocao(arvore, candidatos):
    """O estado vivo da branch já está promovido e esconderia a ausência de
    gravação do config. Aqui a transação parte do estado real do evento."""
    cfg0 = carregar.carregar_config_e4b(arvore.config)
    geo0 = carregar.carregar_geometrias_oficiais(arvore.geometrias)
    assoc0 = carregar.carregar_associacoes_oficiais(arvore.associacoes)
    assert len(geo0["geometrias"]) == 46
    assert len(assoc0["associacoes"]) == 245
    assert cfg0["microlote_janela"]["promocao_oficial_realizada"] is False
    assert not arvore.manifesto.exists()

    estado, _, _ = _aplicar(arvore, candidatos)
    assert estado.aplicado and not estado.rollback_executado

    cfg, geo, assoc = arvore.carregar()
    assert len(geo["geometrias"]) == 54
    assert len(assoc["associacoes"]) == 253
    assert cfg["microlote_janela"]["promocao_oficial_realizada"] is True
    for p in PERFIS_E4B:
        assert cfg["perfis"][p]["promocao_oficial"]["status"] == "PROMOVIDO"

    man = json.loads(arvore.manifesto.read_text(encoding="utf-8"))
    assert man["quantidade_antes"] == {"geometrias": 46, "associacoes": 245}
    assert man["quantidade_depois"] == {"geometrias": 54, "associacoes": 253}
    assert man["reconstruido_apos_gravacao"] is False

    unif = integridade.verificar_integridade_promocao_e4b(
        cfg, geo, assoc, man, candidatos)
    assert unif.ok, unif.descrever()

    assert journal.pendente(arvore.dir_dados) is None
    assert not journal.caminho_backup(arvore.config).exists()
    assert not journal.caminho_backup(arvore.geometrias).exists()


def test_promocao_integral_reproduz_os_hashes_do_evento(arvore, candidatos):
    """A árvore isolada sai byte a byte igual ao que foi publicado."""
    _aplicar(arvore, candidatos)
    assert hash_arquivo(arvore.geometrias) == \
        evento.HASH_DEPOIS[evento.REL_GEOMETRIAS]
    assert hash_arquivo(arvore.associacoes) == \
        evento.HASH_DEPOIS[evento.REL_ASSOCIACOES]
    assert arvore.config.read_text(encoding="utf-8") == \
        CAMINHO_CONFIG.read_text(encoding="utf-8")


def test_segunda_execucao_integral_nao_muda_nada(arvore, candidatos):
    _aplicar(arvore, candidatos)
    quatro = (arvore.geometrias, arvore.associacoes, arvore.config,
              arvore.manifesto)
    h1 = tuple(hash_arquivo(p) for p in quatro)
    cfg, geo, assoc = arvore.carregar()
    plano2 = _plano(candidatos, geo, assoc)
    sim2 = transacao.simular_promocao(plano2, geo, assoc)
    assert sim2.ids_criados == () and sim2.associacoes_criadas == ()
    docs2 = finalizacao.planejar_documentos(
        sim2, cfg, candidatos, arvore.geometrias, arvore.associacoes,
        arvore.config)
    assert docs2.config == arvore.config.read_text(encoding="utf-8")
    assert tuple(hash_arquivo(p) for p in quatro) == h1


# ===========================================================================
# Falhas DURANTE a finalização auditável
# ===========================================================================

PONTOS_DE_FALHA_NA_FINALIZACAO = [
    "depois_de_gravar_manifesto",
    "depois_de_gravar_config",
    "durante_verificacao_unificada",
    "depois_de_validacao_unificada",
]


@pytest.mark.parametrize("ponto", PONTOS_DE_FALHA_NA_FINALIZACAO)
def test_falha_na_finalizacao_restaura_os_quatro_artefatos(arvore, candidatos, ponto):
    """Exceção depois do journal não pode restaurar só `dados/`.

    Era exatamente esse o buraco: o manifesto novo ficava no disco, o config
    ficava no estado que estivesse, e o journal — a única autoridade capaz de
    desfazer os quatro — era apagado em seguida."""
    h0 = {p: hash_arquivo(p) for p in (arvore.geometrias, arvore.associacoes,
                                       arvore.config)}
    assert not arvore.manifesto.exists()

    estado, _, _ = _aplicar(arvore, candidatos, falha_injetada=ponto)
    assert not estado.aplicado and estado.rollback_executado

    for caminho, h in h0.items():
        assert hash_arquivo(caminho) == h, f"{caminho.name} não voltou ao original"
    assert not arvore.manifesto.exists(), \
        "manifesto que não existia antes continuou no disco"
    cfg = carregar.carregar_config_e4b(arvore.config)
    assert cfg["microlote_janela"]["promocao_oficial_realizada"] is False
    assert journal.pendente(arvore.dir_dados) is None
    assert not journal.caminho_backup(arvore.config).exists()
    assert not journal.caminho_backup(arvore.geometrias).exists()


def test_manifesto_inexistente_e_removido_quando_a_verificacao_falha(arvore, candidatos):
    """O caso obrigatório: manifesto não existia, é gravado, a verificação
    unificada falha depois. Ele tem de sumir e todo o resto voltar."""
    h0 = {p: hash_arquivo(p) for p in (arvore.geometrias, arvore.associacoes,
                                       arvore.config)}
    plano, sim, docs = _documentos(arvore, candidatos)

    def verificador_que_reprova():
        from curadoria.promocao.modelos import ResultadoValidacao
        assert arvore.manifesto.exists(), "o manifesto deveria ter sido gravado"
        return ResultadoValidacao.reprovado(
            "-", "reprovação forçada", "x", "y", "teste")

    def finalizar(j):
        finalizacao.retomar_finalizacao(j, arvore.raiz, docs,
                                        verificador_que_reprova)

    estado, _, _ = transacao.aplicar_promocao_transacional(
        plano, arvore.geometrias, arvore.associacoes, sim, docs,
        caminho_config=arvore.config, caminho_manifesto=arvore.manifesto,
        finalizar=finalizar, raiz=arvore.raiz)
    assert not estado.aplicado and estado.rollback_executado
    assert not arvore.manifesto.exists()
    for caminho, h in h0.items():
        assert hash_arquivo(caminho) == h


def test_rollback_falho_preserva_journal_e_backups(arvore, candidatos):
    """Se o rollback não puder ser confirmado, nada é limpo."""
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_ambos_replaces")
    journal.caminho_backup(arvore.config).unlink()
    with pytest.raises(journal.RecuperacaoBloqueada):
        journal.recuperar(arvore.dir_dados, arvore.raiz)
    assert journal.caminho_journal(arvore.dir_dados).exists()
    assert journal.caminho_backup(arvore.geometrias).exists()


# ===========================================================================
# Crash em TODOS os marcos + recuperação orientada por estado
# ===========================================================================

MARCOS_DE_CRASH = [
    ("apos_journal", journal.PREPARADA),
    ("apos_primeiro_replace", journal.GEOMETRIAS_SUBSTITUIDAS),
    ("apos_ambos_replaces", journal.AMBOS_SUBSTITUIDOS),
    ("apos_dados_validos", journal.DADOS_VALIDOS),
    ("depois_de_gravar_manifesto", journal.MANIFESTO_GRAVADO),
    ("depois_de_gravar_config", journal.CONFIG_FINALIZADO),
    ("depois_de_validacao_unificada", journal.VALIDACAO_UNIFICADA),
    ("apos_concluida", journal.CONCLUIDA),
]


def _recuperar(arvore, candidatos):
    """Nova execução: reconstrói os documentos e retoma pelo journal."""
    d = journal.ler(journal.caminho_journal(arvore.dir_dados), arvore.raiz)
    if d["estado"] in journal.ESTADOS_ROLLBACK:
        return journal.recuperar(arvore.dir_dados, arvore.raiz)
    cfg, geo, assoc = arvore.carregar()
    if len(geo["geometrias"]) > 46:          # dados já promovidos
        ids = {c.id_geometria for c in candidatos}
        perfis = {carregar.perfil_id_oficial(c.codigo_perfil) for c in candidatos}
        geo = dict(geo, geometrias=[x for x in geo["geometrias"]
                                    if x["id"] not in ids])
        assoc = dict(assoc, associacoes=[x for x in assoc["associacoes"]
                                         if x["perfil_id"] not in perfis])
    sim = transacao.simular_promocao(_plano(candidatos, geo, assoc), geo, assoc)
    docs = finalizacao.planejar_documentos(
        sim, cfg, candidatos, arvore.geometrias, arvore.associacoes, arvore.config)
    return finalizacao.retomar_finalizacao(
        journal.caminho_journal(arvore.dir_dados), arvore.raiz, docs,
        arvore.verificador(candidatos))


@pytest.mark.parametrize("ponto,estado", MARCOS_DE_CRASH)
def test_crash_em_cada_marco_e_recuperado(arvore, candidatos, ponto, estado):
    """Encerramento abrupto: sai sem `except`, como um processo morto."""
    h0 = {p: hash_arquivo(p) for p in (arvore.geometrias, arvore.associacoes,
                                       arvore.config)}
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em=ponto)
    pend = journal.pendente(arvore.dir_dados)
    assert pend is not None and pend["estado"] == estado

    _recuperar(arvore, candidatos)

    if estado in journal.ESTADOS_ROLLBACK:
        for caminho, h in h0.items():
            assert hash_arquivo(caminho) == h, f"{caminho.name}: rollback incompleto"
        assert not arvore.manifesto.exists()
    else:
        cfg, geo, assoc = arvore.carregar()
        assert len(geo["geometrias"]) == 54
        assert len(assoc["associacoes"]) == 253
        assert cfg["microlote_janela"]["promocao_oficial_realizada"] is True
        man = json.loads(arvore.manifesto.read_text(encoding="utf-8"))
        assert man["quantidade_antes"] == {"geometrias": 46, "associacoes": 245}
        assert integridade.verificar_integridade_promocao_e4b(
            cfg, geo, assoc, man, candidatos).ok

    assert journal.pendente(arvore.dir_dados) is None
    for alvo in (arvore.geometrias, arvore.associacoes, arvore.config,
                 arvore.manifesto):
        assert not journal.caminho_backup(alvo).exists(), alvo.name


def test_crash_apos_dados_validos_grava_o_config_na_retomada(arvore, candidatos):
    """O bug original em uma linha: `CONFIG_FINALIZADO` era só um rótulo."""
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_dados_validos")
    assert carregar.carregar_config_e4b(
        arvore.config)["microlote_janela"]["promocao_oficial_realizada"] is False
    rel = _recuperar(arvore, candidatos)
    assert "config gravado" in rel.passos
    assert carregar.carregar_config_e4b(
        arvore.config)["microlote_janela"]["promocao_oficial_realizada"] is True


def test_retomada_passa_pelos_marcos_na_ordem(arvore, candidatos):
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_dados_validos")
    rel = _recuperar(arvore, candidatos)
    assert rel.estado_encontrado == journal.DADOS_VALIDOS
    assert rel.passos == ("manifesto gravado", "config gravado",
                          "verificação unificada aprovada", "CONCLUIDA",
                          "journal e backups removidos")


def test_retomada_de_manifesto_gravado_nao_regrava_o_manifesto(arvore, candidatos):
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="depois_de_gravar_manifesto")
    rel = _recuperar(arvore, candidatos)
    assert "manifesto gravado" not in rel.passos
    assert "config gravado" in rel.passos


def test_concluida_nao_e_limpo_sem_conferir(arvore, candidatos):
    """`CONCLUIDA` abandonado: os quatro hashes e a verificação unificada são
    conferidos ANTES da limpeza. Limpar às cegas confiaria num rótulo."""
    config_pre_texto = arvore.config.read_text(encoding="utf-8")
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_concluida")
    # o rótulo diz CONCLUIDA, mas o config no disco voltou a ser o anterior
    arvore.config.write_text(config_pre_texto, encoding="utf-8")
    with pytest.raises(finalizacao.FinalizacaoBloqueada, match="config"):
        _recuperar(arvore, candidatos)
    assert journal.caminho_journal(arvore.dir_dados).exists(), \
        "journal foi limpo apesar da divergência"
    assert journal.caminho_backup(arvore.config).exists()


def test_retomada_bloqueia_se_o_recibo_do_journal_divergir(arvore, candidatos):
    """Um journal cujo recibo não descreve esta promoção terminaria outra."""
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_dados_validos")
    j = journal.caminho_journal(arvore.dir_dados)
    d = json.loads(j.read_text(encoding="utf-8"))
    d["evento_promocao"]["quantidade_antes"] = {"geometrias": 54, "associacoes": 253}
    j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    h_config = hash_arquivo(arvore.config)
    with pytest.raises(finalizacao.FinalizacaoBloqueada, match="recibo"):
        _recuperar(arvore, candidatos)
    assert hash_arquivo(arvore.config) == h_config, "config foi tocado"
    assert not arvore.manifesto.exists()
    assert j.exists()


def test_retomada_bloqueia_se_o_documento_reconstruido_divergir(arvore, candidatos):
    """A retomada não grava um config diferente do que o journal prometeu."""
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_dados_validos")
    _, _, docs = _documentos(arvore, candidatos)
    from dataclasses import replace as _replace
    adulterado = _replace(docs, config=docs.config + " ")
    with pytest.raises(finalizacao.FinalizacaoBloqueada, match="divergem"):
        finalizacao.retomar_finalizacao(
            journal.caminho_journal(arvore.dir_dados), arvore.raiz, adulterado,
            arvore.verificador(candidatos))
    assert not arvore.manifesto.exists()
    assert journal.caminho_journal(arvore.dir_dados).exists()


# ===========================================================================
# Estrutura do journal
# ===========================================================================

def _journal_valido(arvore, candidatos):
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_journal")
    j = journal.caminho_journal(arvore.dir_dados)
    return j, json.loads(j.read_text(encoding="utf-8"))


@pytest.mark.parametrize("mutacao", [
    "papel_a_menos", "papel_a_mais", "destino_absoluto", "destino_com_pai",
    "hash_curto", "sem_hash_final_do_config", "recibo_incompleto",
])
def test_journal_invalido_e_recusado(arvore, candidatos, mutacao):
    j, d = _journal_valido(arvore, candidatos)
    if mutacao == "papel_a_menos":
        d["arquivos"].pop("config")
    elif mutacao == "papel_a_mais":
        d["arquivos"]["extra"] = dict(d["arquivos"]["config"])
    elif mutacao == "destino_absoluto":
        d["arquivos"]["config"]["destino"] = "/etc/passwd"
    elif mutacao == "destino_com_pai":
        d["arquivos"]["config"]["destino"] = "../../fora.json"
    elif mutacao == "hash_curto":
        d["arquivos"]["geometrias"]["hash_esperado_depois"] = "abc"
    elif mutacao == "sem_hash_final_do_config":
        d["arquivos"]["config"]["hash_esperado_depois"] = None
    elif mutacao == "recibo_incompleto":
        d["evento_promocao"].pop("commit_pre_promocao")
    j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(journal.JournalCorrompido):
        journal.ler(j, arvore.raiz)
    assert j.exists(), "journal inválido não pode ser apagado silenciosamente"


def test_journal_recusa_alteracao_externa_durante_a_transacao(arvore, candidatos):
    """Conteúdo que não é nem o anterior nem o esperado = edição de fora."""
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_ambos_replaces")
    arvore.config.write_text('{"perfis": {}, "editado_por_fora": true}\n',
                             encoding="utf-8")
    with pytest.raises(journal.RecuperacaoBloqueada, match="alteração externa"):
        journal.recuperar(arvore.dir_dados, arvore.raiz)
    assert journal.caminho_journal(arvore.dir_dados).exists()


def test_limpeza_remove_backups_dos_tres_diretorios(arvore, candidatos):
    """Os backups não vivem todos em `dados/`."""
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_journal")
    assert journal.caminho_backup(arvore.config).exists()
    assert journal.caminho_backup(arvore.geometrias).exists()
    journal.recuperar(arvore.dir_dados, arvore.raiz)
    for alvo in (arvore.geometrias, arvore.associacoes, arvore.config):
        assert not journal.caminho_backup(alvo).exists(), alvo.name


# ===========================================================================
# Evento histórico × permanência atual — a biblioteca pode crescer
# ===========================================================================

def _promovida(arvore, candidatos):
    """Árvore isolada já promovida, pronta para receber lotes futuros."""
    _aplicar(arvore, candidatos)
    return arvore.carregar()


def _geometria_futura(gid="GEO-FUTURO-001"):
    return {
        "id": gid,
        "contorno_externo": [[0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0]],
        "vazios_internos": [],
        "nivel_contorno": "2_renderizavel_comercial",
        "bounding_box": {"largura": 10.0, "altura": 5.0},
    }


def test_evento_historico_nao_olha_para_o_disco(manifesto_real):
    """Os fatos do E.4C são imutáveis e independem do arquivo de hoje."""
    r = integridade.verificar_evento_historico_e4c(manifesto_real)
    assert r.ok, r.descrever()


def test_biblioteca_pode_crescer_sem_reprovar_o_e4b(arvore, candidatos):
    """Uma promoção futura legítima acrescenta registros. Isso não é corrupção
    do E.4B, e o verificador não pode chamar de corrupção."""
    cfg, geo, assoc = _promovida(arvore, candidatos)
    geo["geometrias"].append(_geometria_futura())
    assoc["associacoes"].append({"perfil_id": "FABRICANTE-FUTURO-001",
                                 "geometria_padrao_id": "GEO-FUTURO-001"})
    assert len(geo["geometrias"]) == 55
    assert len(assoc["associacoes"]) == 254

    man = json.loads(arvore.manifesto.read_text(encoding="utf-8"))
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, man,
                                                       candidatos)
    assert r.ok, r.descrever()
    # e o manifesto continua descrevendo 46 -> 54, sem tocar em nada
    assert man["quantidade_depois"] == {"geometrias": 54, "associacoes": 253}


def test_hash_global_diferente_do_historico_nao_reprova(arvore, candidatos):
    """Depois de um lote novo o arquivo tem outro hash. O fato histórico
    continua verdadeiro."""
    cfg, geo, assoc = _promovida(arvore, candidatos)
    assert hash_arquivo(arvore.geometrias) == \
        evento.HASH_DEPOIS[evento.REL_GEOMETRIAS]
    geo["geometrias"].append(_geometria_futura())
    arvore.geometrias.write_text(
        json.dumps(geo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    assert hash_arquivo(arvore.geometrias) != \
        evento.HASH_DEPOIS[evento.REL_GEOMETRIAS]

    cfg, geo, assoc = arvore.carregar()
    man = json.loads(arvore.manifesto.read_text(encoding="utf-8"))
    assert integridade.verificar_integridade_promocao_e4b(
        cfg, geo, assoc, man, candidatos).ok


@pytest.mark.parametrize("mutacao", [
    "contorno_alterado", "geo_removido", "associacao_apontando_errado",
    "dimensao_alterada", "config_despromovido", "geo_tms102_criado",
])
def test_mutacao_de_registro_do_e4b_reprova(arvore, candidatos, mutacao):
    cfg, geo, assoc = _promovida(arvore, candidatos)
    if mutacao == "contorno_alterado":
        for g in geo["geometrias"]:
            if g["id"] == "GEO-SU-001":
                g["contorno_externo"][0] = [g["contorno_externo"][0][0] + 1.0,
                                            g["contorno_externo"][0][1]]
    elif mutacao == "geo_removido":
        geo["geometrias"] = [g for g in geo["geometrias"] if g["id"] != "GEO-SU-041"]
    elif mutacao == "associacao_apontando_errado":
        for a in assoc["associacoes"]:
            if a["perfil_id"] == "ALCOA-SU-053":
                a["geometria_padrao_id"] = "GEO-SU-005"
    elif mutacao == "dimensao_alterada":
        for g in geo["geometrias"]:
            if g["id"] == "GEO-SU-102":
                g["contorno_externo"] = [[0.0, 0.0], [40.0, 0.0], [40.0, 40.0]]
    elif mutacao == "config_despromovido":
        cfg["perfis"]["SU-002"]["promocao_oficial"]["status"] = "ainda_nao_autorizada"
    elif mutacao == "geo_tms102_criado":
        geo["geometrias"].append(_geometria_futura("GEO-TMS-102"))

    man = json.loads(arvore.manifesto.read_text(encoding="utf-8"))
    r = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, man,
                                                       candidatos)
    assert not r.ok, f"{mutacao} passou sem ser detectada"
    # e a permanência atual sozinha já pega — não depende do manifesto
    assert not integridade.verificar_permanencia_atual_e4b(
        cfg, geo, assoc, candidatos).ok


def test_mutacao_do_fato_historico_reprova(arvore, candidatos):
    """`46 → 54` virando outra coisa continua sendo reprovado."""
    cfg, geo, assoc = _promovida(arvore, candidatos)
    man = json.loads(arvore.manifesto.read_text(encoding="utf-8"))
    man["quantidade_antes"] = {"geometrias": 54, "associacoes": 253}
    assert not integridade.verificar_evento_historico_e4c(man).ok
    assert not integridade.verificar_integridade_promocao_e4b(
        cfg, geo, assoc, man, candidatos).ok
    # mas a permanência atual continua aprovada: são perguntas diferentes
    assert integridade.verificar_permanencia_atual_e4b(
        cfg, geo, assoc, candidatos).ok


def test_journal_continua_exigindo_os_quatro_hashes_finais(arvore, candidatos):
    """A flexibilização é da auditoria durável, NÃO da transação ativa."""
    _, _, docs = _documentos(arvore, candidatos)
    with pytest.raises(InterrupcaoSimulada):
        _aplicar(arvore, candidatos, interromper_em="apos_journal")
    arq = journal.pendente(arvore.dir_dados)["arquivos"]
    for papel in journal.PAPEIS:
        assert arq[papel]["hash_esperado_depois"] == docs.hashes[papel], papel
    journal.recuperar(arvore.dir_dados, arvore.raiz)


# ===========================================================================
# Reconstrução do manifesto: comando explícito, nunca silenciosa
# ===========================================================================

from curadoria.promocao import cli as cli_mod   # noqa: E402


@pytest.fixture
def cli_na_arvore(arvore, monkeypatch):
    """Aponta a CLI para a árvore isolada, sem tocar no repositório."""
    monkeypatch.setattr(cli_mod, "RAIZ", arvore.raiz)
    monkeypatch.setattr(cli_mod, "CAMINHO_CONFIG", arvore.config)
    monkeypatch.setattr(cli_mod, "CAMINHO_GEOMETRIAS", arvore.geometrias)
    monkeypatch.setattr(cli_mod, "CAMINHO_ASSOCIACOES", arvore.associacoes)
    monkeypatch.setattr(cli_mod, "DIR_DADOS", arvore.dir_dados)
    monkeypatch.setattr(auditoria, "CAMINHO_MANIFESTO", arvore.manifesto)
    return lambda *argv: cli_mod.main(list(argv))


def _promover_e_apagar_manifesto(arvore, candidatos):
    _aplicar(arvore, candidatos)
    arvore.manifesto.unlink()
    assert not arvore.manifesto.exists()


def test_promover_nao_reconstroi_manifesto_em_silencio(arvore, candidatos,
                                                       cli_na_arvore):
    """Decidir sucesso só porque os oito GEOs existem é fraco demais."""
    _promover_e_apagar_manifesto(arvore, candidatos)
    codigo = cli_na_arvore("promover", "--apply", "--permitir-arvore-suja",
                           "--lote", "E4B")
    assert codigo == 2
    assert not arvore.manifesto.exists(), "promover recriou em silêncio"


def test_reconstruir_manifesto_exige_apply(arvore, candidatos, cli_na_arvore):
    _promover_e_apagar_manifesto(arvore, candidatos)
    assert cli_na_arvore("reconstruir-manifesto", "--lote", "E4B") == 2
    assert not arvore.manifesto.exists()


def test_reconstruir_manifesto_recusa_sobrescrever(arvore, candidatos,
                                                   cli_na_arvore):
    """Sobrescrever manifesto existente seria apagar o registro do evento."""
    _aplicar(arvore, candidatos)
    h = hash_arquivo(arvore.manifesto)
    assert cli_na_arvore("reconstruir-manifesto", "--lote", "E4B", "--apply") == 2
    assert hash_arquivo(arvore.manifesto) == h


def test_reconstruir_manifesto_caso_integro(arvore, candidatos, cli_na_arvore):
    _promover_e_apagar_manifesto(arvore, candidatos)
    h_outros = {p: hash_arquivo(p) for p in (arvore.geometrias,
                                             arvore.associacoes, arvore.config)}
    assert cli_na_arvore("reconstruir-manifesto", "--lote", "E4B", "--apply") == 0
    man = json.loads(arvore.manifesto.read_text(encoding="utf-8"))
    assert man["quantidade_antes"] == {"geometrias": 46, "associacoes": 245}
    assert man["quantidade_depois"] == {"geometrias": 54, "associacoes": 253}
    assert man["reconstruido_apos_gravacao"] is False
    cfg, geo, assoc = arvore.carregar()
    assert integridade.verificar_integridade_promocao_e4b(
        cfg, geo, assoc, man, candidatos).ok
    for p, h in h_outros.items():
        assert hash_arquivo(p) == h, f"{p.name} foi modificado"


@pytest.mark.parametrize("incoerencia", [
    "config_nao_promovido", "associacao_errada", "geo_ausente",
    "contorno_alterado", "geo_tms102_criado",
])
def test_reconstruir_manifesto_bloqueia_estado_incoerente(
        arvore, candidatos, cli_na_arvore, incoerencia):
    """Reconstruir auditoria sobre `dados/` que não sustenta a promoção seria
    fabricar evidência."""
    _promover_e_apagar_manifesto(arvore, candidatos)

    if incoerencia == "config_nao_promovido":
        cfg = json.loads(arvore.config.read_text(encoding="utf-8"))
        cfg["microlote_janela"]["promocao_oficial_realizada"] = False
        arvore.config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2)
                                 + "\n", encoding="utf-8")
    else:
        geo = json.loads(arvore.geometrias.read_text(encoding="utf-8"))
        assoc = json.loads(arvore.associacoes.read_text(encoding="utf-8"))
        if incoerencia == "associacao_errada":
            for a in assoc["associacoes"]:
                if a["perfil_id"] == "ALCOA-SU-039":
                    a["geometria_padrao_id"] = "GEO-SU-005"
        elif incoerencia == "geo_ausente":
            geo["geometrias"] = [g for g in geo["geometrias"]
                                 if g["id"] != "GEO-SU-003"]
        elif incoerencia == "contorno_alterado":
            for g in geo["geometrias"]:
                if g["id"] == "GEO-SU-053":
                    g["contorno_externo"][2] = [999.0, 999.0]
        elif incoerencia == "geo_tms102_criado":
            geo["geometrias"].append(_geometria_futura("GEO-TMS-102"))
        arvore.geometrias.write_text(
            json.dumps(geo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        arvore.associacoes.write_text(
            json.dumps(assoc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    h = {p: hash_arquivo(p) for p in (arvore.geometrias, arvore.associacoes,
                                      arvore.config)}
    assert cli_na_arvore("reconstruir-manifesto", "--lote", "E4B", "--apply") == 1
    assert not arvore.manifesto.exists(), "manifesto criado sobre estado incoerente"
    for p, hp in h.items():
        assert hash_arquivo(p) == hp, f"{p.name} foi modificado"


def test_reconstruir_manifesto_remove_o_arquivo_se_a_verificacao_final_reprovar(
        arvore, candidatos, cli_na_arvore, monkeypatch):
    """Última rede: gravou, releu, reprovou -> some."""
    _promover_e_apagar_manifesto(arvore, candidatos)
    from curadoria.promocao.modelos import ResultadoValidacao
    monkeypatch.setattr(
        cli_mod.integridade, "verificar_integridade_promocao_e4b",
        lambda *a, **k: ResultadoValidacao.reprovado(
            "-", "reprovação forçada", "x", "y", "teste"))
    assert cli_na_arvore("reconstruir-manifesto", "--lote", "E4B", "--apply") == 1
    assert not arvore.manifesto.exists()


# ===========================================================================
# CONCLUIDA é o ponto de commit: falha de limpeza não desfaz promoção
# ===========================================================================

def _quebrar_limpeza(monkeypatch, arvore, alvo: str):
    """Falha só na faxina, depois de CONCLUIDA."""
    if alvo == "fsync_do_diretorio":
        real_sync, real_limpar = journal.sincronizar_diretorio, journal.limpar
        na_faxina = []

        def sync(p):
            if na_faxina:
                raise OSError("fsync do diretório falhou")
            return real_sync(p)

        def limpar(*a, **kw):
            na_faxina.append(True)
            return real_limpar(*a, **kw)
        monkeypatch.setattr(journal, "sincronizar_diretorio", sync)
        monkeypatch.setattr(journal, "limpar", limpar)
        return
    real = Path.unlink

    def unlink(self, *a, **kw):
        nome = self.name
        if alvo == "primeiro_backup" and nome.endswith(".bak"):
            raise OSError(f"falha ao apagar backup {nome}")
        if alvo == "arquivo_journal" and nome.startswith(".promocao_"):
            raise OSError(f"falha ao apagar journal {nome}")
        return real(self, *a, **kw)
    monkeypatch.setattr(Path, "unlink", unlink)


@pytest.mark.parametrize("alvo", ["primeiro_backup", "arquivo_journal",
                                  "fsync_do_diretorio"])
def test_falha_na_limpeza_nao_desfaz_promocao_concluida(arvore, candidatos,
                                                        monkeypatch, alvo):
    """Depois de CONCLUIDA os quatro artefatos estão gravados, conferidos por
    hash e aprovados. Trocar isso por rollback, por causa de um backup que
    ninguém consome, seria perder trabalho correto."""
    with monkeypatch.context() as m:
        _quebrar_limpeza(m, arvore, alvo)
        estado, _, _ = _aplicar(arvore, candidatos)

    assert estado.aplicado, "promoção concluída foi desfeita por falha de faxina"
    assert not estado.rollback_executado
    assert estado.limpeza_pendente

    # os quatro estão no estado FINAL, nenhum voltou
    cfg, geo, assoc = arvore.carregar()
    assert len(geo["geometrias"]) == 54 and len(assoc["associacoes"]) == 253
    assert cfg["microlote_janela"]["promocao_oficial_realizada"] is True
    assert hash_arquivo(arvore.geometrias) == \
        evento.HASH_DEPOIS[evento.REL_GEOMETRIAS]
    man = json.loads(arvore.manifesto.read_text(encoding="utf-8"))
    assert man["quantidade_antes"] == {"geometrias": 46, "associacoes": 245}

    # e a recuperação seguinte apenas termina a faxina — nunca reverte.
    # (no caso do fsync final o journal já saiu do disco: sobrou só a barreira
    # de durabilidade, e não há nada pendente para retomar)
    if journal.pendente(arvore.dir_dados) is not None:
        rel = _recuperar(arvore, candidatos)
        assert rel.concluida and not rel.limpeza_pendente
    assert journal.pendente(arvore.dir_dados) is None
    for alvo_arq in (arvore.geometrias, arvore.associacoes, arvore.config,
                     arvore.manifesto):
        assert not journal.caminho_backup(alvo_arq).exists()
    assert len(json.loads(arvore.geometrias.read_text())["geometrias"]) == 54


def test_recuperar_apos_limpeza_pendente_revalida_antes_de_terminar(
        arvore, candidatos, monkeypatch):
    """A retomada da faxina não é cega: confere os quatro hashes e a
    verificação unificada antes de apagar o que sobrou."""
    with monkeypatch.context() as m:
        _quebrar_limpeza(m, arvore, "arquivo_journal")
        _aplicar(arvore, candidatos)
    assert journal.pendente(arvore.dir_dados)["estado"] == journal.CONCLUIDA

    arvore.manifesto.write_text('{"adulterado": true}\n', encoding="utf-8")
    with pytest.raises(finalizacao.FinalizacaoBloqueada, match="manifesto"):
        _recuperar(arvore, candidatos)
    assert journal.caminho_journal(arvore.dir_dados).exists(), \
        "faxina terminou sem revalidar"
    # e os dados NÃO foram revertidos
    assert len(json.loads(arvore.geometrias.read_text())["geometrias"]) == 54
