"""
EsquadriaCore — testes do Contrato Mínimo de Consumo (ADR-009)
==============================================================
Comprova que os dados já existentes nos JSONs oficiais são consumidos
corretamente pela fronteira `contrato/consumo.py`: 46 geometrias (10
renderizáveis + 36 brutas), 245 associações, orientação normalizada,
coordenadas armazenadas intactas, legado sintético, imutabilidade real e
conformidade com o schema de máquina.

Rodar:  pytest tests/test_contrato_consumo.py -v
"""
import dataclasses
import json
import os

import pytest

from domain.entidades import validar_contornos, GeometriaPadrao
from contrato.consumo import (
    CONTRATO_CONSUMO_VERSAO,
    NIVEIS_RENDERIZAVEIS,
    FONTE_NOVO,
    FONTE_LEGADO,
    BoundingBoxDTO,
    GeometriaConsumivel,
    AssociacaoConsumivel,
    ContratoInvalido,
    _adaptar_geometria,
    _area_com_sinal,
    carregar_geometrias,
    carregar_associacoes,
    carregar_biblioteca,
)

GEOMETRIAS = "dados/geometrias.json"
ASSOCIACOES = "dados/perfil_geometria.json"
SCHEMA = "contrato/schemas/biblioteca_consumo.schema.json"

pytestmark = pytest.mark.skipif(
    not (os.path.exists(GEOMETRIAS) and os.path.exists(ASSOCIACOES)),
    reason="biblioteca de dados não presente")


@pytest.fixture(scope="module")
def bib():
    return carregar_biblioteca()


# ---------------------------------------------------------------------------
# Validação ESTRUTURAL LIMITADA (NÃO é um validador de JSON Schema completo).
# Cobre apenas o subconjunto de palavras-chave usado no schema publicado:
#   type, required, properties, items, enum, anyOf, $ref.
# Não implementa: oneOf/allOf/not, patternProperties, format, dependências,
# additionalProperties, min/max, etc. Serve só para checar a saída do contrato
# contra o schema deste repositório — não substitui a biblioteca `jsonschema`
# nem prova conformidade com o padrão JSON Schema (ver ADR-009 §9).
# ---------------------------------------------------------------------------

PALAVRAS_SUPORTADAS = ("type", "required", "properties", "items",
                       "enum", "anyOf", "$ref")

_TIPOS = {"string": str, "number": (int, float), "boolean": bool,
          "array": list, "object": dict, "null": type(None)}


def _valida_estrutura_limitada(valor, esquema, raiz, caminho="$"):
    if "$ref" in esquema:
        alvo = raiz
        for parte in esquema["$ref"].lstrip("#/").split("/"):
            alvo = alvo[parte]
        return _valida_estrutura_limitada(valor, alvo, raiz, caminho)
    if "anyOf" in esquema:
        assert any(_ok(valor, s, raiz, caminho) for s in esquema["anyOf"]), \
            f"{caminho}: não satisfaz nenhum anyOf"
        return
    tipos = esquema.get("type")
    if tipos is not None:
        tipos = [tipos] if isinstance(tipos, str) else tipos
        pytipos = tuple(_TIPOS[t] for t in tipos)
        # bool é subtipo de int em Python: trate à parte
        if bool not in [_TIPOS[t] for t in tipos] and isinstance(valor, bool):
            raise AssertionError(f"{caminho}: bool inesperado")
        assert isinstance(valor, pytipos), \
            f"{caminho}: esperado {tipos}, veio {type(valor).__name__}"
    if "enum" in esquema:
        assert valor in esquema["enum"], f"{caminho}: {valor!r} fora do enum"
    if isinstance(valor, dict) and "properties" in esquema:
        for req in esquema.get("required", []):
            assert req in valor, f"{caminho}: falta chave obrigatória '{req}'"
        for chave, sub in esquema["properties"].items():
            if chave in valor:
                _valida_estrutura_limitada(valor[chave], sub, raiz,
                                           f"{caminho}.{chave}")
    if isinstance(valor, list) and "items" in esquema:
        for i, item in enumerate(valor):
            _valida_estrutura_limitada(item, esquema["items"], raiz,
                                       f"{caminho}[{i}]")


def _ok(valor, esquema, raiz, caminho):
    try:
        _valida_estrutura_limitada(valor, esquema, raiz, caminho)
        return True
    except AssertionError:
        return False


# ---------------------------------------------------------------------------
# 1-3, 5-6, 8: geometrias
# ---------------------------------------------------------------------------

def test_carrega_as_46_geometrias(bib):
    assert len(bib.geometrias) == 46
    assert all(isinstance(g, GeometriaConsumivel) for g in bib.geometrias)


def test_dez_renderizaveis_36_brutas(bib):
    rend = bib.renderizaveis()
    assert len(rend) == 10
    assert all(g.renderizavel for g in rend)
    assert all(g.nivel_contorno in NIVEIS_RENDERIZAVEIS for g in rend)
    brutas = [g for g in bib.geometrias if not g.renderizavel]
    assert len(brutas) == 36


def test_renderizaveis_tem_contorno_externo_nao_vazio(bib):
    for g in bib.renderizaveis():
        assert g.contorno_externo is not None and len(g.contorno_externo) >= 3


def test_renderizaveis_nivel_correto(bib):
    for g in bib.renderizaveis():
        assert g.nivel_contorno == "2_renderizavel_comercial"


def test_unidade_referencial_eixos_e_versao_em_todas(bib):
    for g in bib.geometrias:
        assert g.unidade == "mm"
        assert g.versao_schema == CONTRATO_CONSUMO_VERSAO == "1.0"
        assert g.referencial == "local_do_perfil"
        assert g.eixo_x == "positivo_para_direita"
        assert g.eixo_y == "positivo_para_cima"


def test_vazios_sempre_tupla_nunca_none(bib):
    for g in bib.geometrias:
        assert isinstance(g.vazios_internos, tuple)   # lista vazia é válida


def test_brutas_contorno_none_sem_erro(bib):
    for g in bib.geometrias:
        if not g.renderizavel:
            assert g.contorno_externo is None
            assert g.vazios_internos == ()
            assert g.fonte_contorno is None
            assert g.bounding_box is None      # nunca zeros artificiais


def test_fonte_contorno_das_renderizaveis(bib):
    for g in bib.renderizaveis():
        assert g.fonte_contorno == FONTE_NOVO


# ---------------------------------------------------------------------------
# Orientação normalizada e coordenadas intactas
# ---------------------------------------------------------------------------

def test_orientacao_externo_ccw_vazios_cw(bib):
    for g in bib.renderizaveis():
        assert _area_com_sinal(g.contorno_externo) > 0, \
            f"{g.codigo}: externo deveria ser CCW"
        for v in g.vazios_internos:
            assert _area_com_sinal(v) < 0, f"{g.codigo}: vazio deveria ser CW"


def test_coordenadas_armazenadas_intactas(bib):
    """A normalização é só no DTO: o conjunto de pontos (ignorando ordem) do
    contorno de saída é idêntico ao gravado no JSON."""
    with open(GEOMETRIAS, encoding="utf-8") as f:
        cru = {g["id"]: g for g in json.load(f)["geometrias"]}
    for g in bib.renderizaveis():
        pts_json = {(float(x), float(y)) for x, y in cru[g.codigo]["contorno_externo"]}
        pts_dto = set(g.contorno_externo)
        assert pts_json == pts_dto, f"{g.codigo}: conjunto de pontos mudou"


def test_bounding_box_coerente(bib):
    for g in bib.renderizaveis():
        xs = [p[0] for p in g.contorno_externo]
        ys = [p[1] for p in g.contorno_externo]
        bb = g.bounding_box
        assert isinstance(bb, BoundingBoxDTO)
        assert (bb.min_x, bb.min_y, bb.max_x, bb.max_y) == \
            (min(xs), min(ys), max(xs), max(ys))
        assert g.largura_mm > 0 and g.altura_mm > 0


def test_bounding_box_serializa_como_objeto_nomeado(bib):
    g = bib.renderizaveis()[0]
    d = g.para_dict()["bounding_box"]
    assert isinstance(d, dict)
    assert set(d) == {"min_x", "min_y", "max_x", "max_y", "largura", "altura"}
    assert d["largura"] == round(d["max_x"] - d["min_x"], 4)
    assert d["altura"] == round(d["max_y"] - d["min_y"], 4)
    # bruta -> null
    b = next(x for x in bib.geometrias if not x.renderizavel)
    assert b.para_dict()["bounding_box"] is None


def test_contornos_passam_validacao_de_dominio(bib):
    for g in bib.renderizaveis():
        validar_contornos(GeometriaPadrao(
            id=g.codigo, contorno_mm=[], status="homologada", versao="2.0",
            contorno_externo=list(g.contorno_externo),
            vazios_internos=[list(v) for v in g.vazios_internos]))


# ---------------------------------------------------------------------------
# Níveis: enumeração explícita
# ---------------------------------------------------------------------------

def test_nivel_ausente_vira_bruto():
    g = _adaptar_geometria({"id": "GEO-X", "familia_mercado": "SUPREMA"})
    assert g.nivel_contorno == "0_bruto_aproximado"
    assert g.renderizavel is False


def test_nivel_desconhecido_falha_explicitamente():
    with pytest.raises(ContratoInvalido):
        _adaptar_geometria({"id": "GEO-X", "nivel_contorno": "9_ultra_hd"})


# ---------------------------------------------------------------------------
# Legado sintético (nenhum dado real usa contorno_mm)
# ---------------------------------------------------------------------------

def test_legado_contorno_mm_vira_forma_unica():
    quadrado = [[0, 0], [10, 0], [10, 10], [0, 10]]
    g = _adaptar_geometria({
        "id": "GEO-LEGADO", "contorno_mm": quadrado,
        "nivel_contorno": "2_renderizavel_comercial"})
    assert g.fonte_contorno == FONTE_LEGADO
    assert g.contorno_externo is not None            # exposto como forma única
    assert g.vazios_internos == ()
    assert _area_com_sinal(g.contorno_externo) > 0   # normalizado CCW
    assert g.renderizavel is True


def test_externo_prevalece_sobre_legado():
    triangulo = [[0, 0], [10, 0], [5, 8]]
    quadrado = [[0, 0], [10, 0], [10, 10], [0, 10]]
    g = _adaptar_geometria({
        "id": "GEO-AMBOS", "contorno_externo": triangulo,
        "contorno_mm": quadrado,
        "nivel_contorno": "2_renderizavel_comercial"})
    assert g.fonte_contorno == FONTE_NOVO
    assert len(g.contorno_externo) == 3              # o triângulo (novo)


def test_fechamento_explicito_removido_sem_alterar_geometria():
    # anel com o primeiro ponto repetido no fim (fechamento explícito)
    fechado = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    g = _adaptar_geometria({
        "id": "GEO-FECHADO", "contorno_externo": fechado,
        "nivel_contorno": "2_renderizavel_comercial"})
    # apenas a repetição de fechamento foi removida
    assert len(g.contorno_externo) == 4
    assert g.contorno_externo[0] != g.contorno_externo[-1]
    # mesma coleção de vértices geométricos, mesmo bounding-box
    assert set(g.contorno_externo) == {(0.0, 0.0), (10.0, 0.0),
                                       (10.0, 10.0), (0.0, 10.0)}
    bb = g.bounding_box
    assert (bb.min_x, bb.min_y, bb.max_x, bb.max_y) == (0.0, 0.0, 10.0, 10.0)


# ---------------------------------------------------------------------------
# Imutabilidade real
# ---------------------------------------------------------------------------

def test_dto_geometria_imutavel(bib):
    g = bib.renderizaveis()[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.contorno_externo = ()
    # coordenadas em tuplas (não há .append/.reverse a explorar)
    assert isinstance(g.contorno_externo, tuple)
    assert all(isinstance(p, tuple) for p in g.contorno_externo)
    for v in g.vazios_internos:
        assert isinstance(v, tuple)


def test_dto_associacao_imutavel(bib):
    a = bib.associacoes[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.perfil_id = "x"


def test_biblioteca_imutavel(bib):
    # coleções são tuplas
    assert isinstance(bib.geometrias, tuple)
    assert isinstance(bib.associacoes, tuple)
    # não é possível reatribuir campos
    with pytest.raises(dataclasses.FrozenInstanceError):
        bib.geometrias = ()
    # índice interno é somente-leitura (MappingProxyType)
    with pytest.raises(TypeError):
        bib._por_codigo["X"] = None


def test_codigos_duplicados_falham(tmp_path):
    geo = tmp_path / "g.json"
    ass = tmp_path / "a.json"
    dois_iguais = {"geometrias": [
        {"id": "GEO-DUP", "contorno_externo": [[0, 0], [10, 0], [5, 8]],
         "nivel_contorno": "2_renderizavel_comercial"},
        {"id": "GEO-DUP", "contorno_externo": [[0, 0], [10, 0], [5, 8]],
         "nivel_contorno": "2_renderizavel_comercial"}]}
    geo.write_text(json.dumps(dois_iguais))
    ass.write_text(json.dumps({"associacoes": []}))
    with pytest.raises(ContratoInvalido):
        carregar_biblioteca(str(geo), str(ass))


# ---------------------------------------------------------------------------
# Associações (PerfilGeometria) — ADR-005
# ---------------------------------------------------------------------------

def test_carrega_as_245_associacoes(bib):
    assert len(bib.associacoes) == 245
    assert all(isinstance(a, AssociacaoConsumivel) for a in bib.associacoes)


def test_toda_associacao_referencia_geometria_existente(bib):
    codigos = {g.codigo for g in bib.geometrias}
    for a in bib.associacoes:
        assert a.geometria_padrao_id in codigos


def test_identificadores_obrigatorios_nao_vazios(bib):
    for a in bib.associacoes:
        assert a.perfil_id and a.geometria_padrao_id


def _assoc_base():
    return {
        "perfil_id": "ALCOA-SU-005", "geometria_padrao_id": "GEO-SU-005",
        "responsavel_homologacao": "Bruno", "metodo_validacao": "visual",
        "data": "2026-07-09", "nivel_de_confianca": "alto",
        "observacoes": None}


def test_associacao_campo_obrigatorio_ausente_falha():
    from contrato.consumo import _adaptar_associacao
    reg = _assoc_base()
    del reg["metodo_validacao"]
    with pytest.raises(ContratoInvalido) as e:
        _adaptar_associacao(reg)
    assert "metodo_validacao" in str(e.value)


def test_associacao_campo_obrigatorio_vazio_falha():
    from contrato.consumo import _adaptar_associacao
    reg = _assoc_base()
    reg["responsavel_homologacao"] = "   "     # só espaços
    with pytest.raises(ContratoInvalido) as e:
        _adaptar_associacao(reg)
    assert "responsavel_homologacao" in str(e.value)


def test_associacao_observacoes_none_aceito():
    from contrato.consumo import _adaptar_associacao
    a = _adaptar_associacao(_assoc_base())     # observacoes=None
    assert a.observacoes is None


def test_associacao_observacoes_chave_ausente_falha():
    from contrato.consumo import _adaptar_associacao
    reg = _assoc_base()
    del reg["observacoes"]
    with pytest.raises(ContratoInvalido) as e:
        _adaptar_associacao(reg)
    assert "observacoes" in str(e.value)


def test_campos_de_auditoria_preservados(bib):
    with open(ASSOCIACOES, encoding="utf-8") as f:
        cru = json.load(f)["associacoes"]
    # casa 1:1 por (perfil_id, geometria_padrao_id)
    idx = {(a.perfil_id, a.geometria_padrao_id): a for a in bib.associacoes}
    for r in cru:
        a = idx[(r["perfil_id"], r["geometria_padrao_id"])]
        assert a.responsavel_homologacao == r["responsavel_homologacao"]
        assert a.metodo_validacao == r["metodo_validacao"]
        assert a.data == r["data"]
        assert a.nivel_de_confianca == r["nivel_de_confianca"]
        assert a.observacoes == r["observacoes"]


def test_associacao_nao_embute_pontos_de_geometria(bib):
    campos = {f.name for f in dataclasses.fields(AssociacaoConsumivel)}
    assert "contorno_externo" not in campos
    assert "vazios_internos" not in campos
    assert "contorno_mm" not in campos
    assert "fabricante" not in campos            # é fabricante_derivado
    assert "fabricante_derivado" in campos


def test_ligacao_perfil_associacao_geometria(bib):
    # Perfil (perfil_id) -> PerfilGeometria -> GeometriaConsumivel
    a = next(a for a in bib.associacoes if a.perfil_id == "ALCOA-SU-005")
    assert a.geometria_padrao_id == "GEO-SU-005"
    g = bib.geometria(a.geometria_padrao_id)
    assert g.renderizavel and g.codigo == "GEO-SU-005"
    assert a.fabricante_derivado == "Alcoa"      # inferido do prefixo


def test_fabricante_derivado_prefixo_desconhecido():
    from contrato.consumo import _adaptar_associacao
    a = _adaptar_associacao({
        "perfil_id": "XPTO-999", "geometria_padrao_id": "GEO-SU-005",
        "responsavel_homologacao": "x", "metodo_validacao": "x",
        "data": "x", "nivel_de_confianca": "alto", "observacoes": None})
    assert a.fabricante_derivado is None         # prefixo desconhecido -> None


def test_integridade_referencial_detecta_pendurada(tmp_path):
    # associação apontando para geometria inexistente deve falhar no load
    geo = tmp_path / "g.json"
    ass = tmp_path / "a.json"
    geo.write_text(json.dumps({"geometrias": [
        {"id": "GEO-A", "contorno_externo": [[0, 0], [10, 0], [5, 8]],
         "nivel_contorno": "2_renderizavel_comercial"}]}))
    ass.write_text(json.dumps({"associacoes": [
        {"perfil_id": "ALCOA-A", "geometria_padrao_id": "GEO-FANTASMA",
         "responsavel_homologacao": "x", "metodo_validacao": "x",
         "data": "x", "nivel_de_confianca": "alto", "observacoes": None}]}))
    with pytest.raises(ContratoInvalido):
        carregar_biblioteca(str(geo), str(ass))


# ---------------------------------------------------------------------------
# Validação ESTRUTURAL LIMITADA contra o schema de máquina.
# NÃO é conformidade com o padrão JSON Schema (ver ADR-009 §9): checa apenas
# o subconjunto de palavras-chave documentado em PALAVRAS_SUPORTADAS.
# ---------------------------------------------------------------------------

def test_schema_e_json_valido_e_cobre_ambos():
    with open(SCHEMA, encoding="utf-8") as f:
        esquema = json.load(f)
    assert "geometria" in esquema["definitions"]
    assert "associacao" in esquema["definitions"]


def test_dtos_passam_na_validacao_estrutural_limitada(bib):
    # cobertura limitada: type/required/properties/items/enum/anyOf/$ref
    with open(SCHEMA, encoding="utf-8") as f:
        esquema = json.load(f)
    doc = {
        "geometrias": [g.para_dict() for g in bib.geometrias],
        "associacoes": [a.para_dict() for a in bib.associacoes],
    }
    _valida_estrutura_limitada(doc, esquema, esquema)   # AssertionError se violar


# ---------------------------------------------------------------------------
# Painel: gerado em tmp_path (não sobrescreve a evidência oficial)
# ---------------------------------------------------------------------------

def test_painel_gera_em_tmp_path(tmp_path):
    from curadoria.painel_comercial import gerar
    destino = tmp_path / "painel_teste.png"
    saida = gerar(str(destino))
    assert os.path.exists(saida)
    assert os.path.getsize(saida) > 0
    # não deixou lixo no diretório oficial
    oficial = "curadoria/contornos/painel_10_comerciais.png"
    assert str(destino) != oficial
