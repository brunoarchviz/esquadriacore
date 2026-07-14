"""
EsquadriaCore — contrato/consumo
=================================
Carregador/adaptador genérico da biblioteca homologada (ADR-009).

Lê `dados/geometrias.json` e `dados/perfil_geometria.json` (fonte de verdade,
somente leitura) e devolve DTOs imutáveis com uma convenção de consumo
ESTÁVEL. A normalização (orientação dos anéis, resolução de nível, remoção do
fechamento explícito, unificação de legado) acontece SOMENTE no DTO de saída —
os pontos gravados no JSON não são reordenados nem modificados.

Convenção de saída (ver docs/adendos/adendo_contrato_consumo.md):
- sistema cartesiano 2D, unidade milímetros;
- eixo_x positivo para a direita, eixo_y positivo para cima;
- referencial local do perfil (`referencial = "local_do_perfil"`): cada
  geometria tem seu próprio referencial; NÃO há referencial canônico
  compartilhado nesta versão. `referencial` NÃO é uma coordenada/ponto de
  origem — é a declaração de que o sistema é próprio de cada perfil. O
  bounding-box é exposto como referência calculada;
- contorno externo em sentido anti-horário (CCW), vazios em horário (CW);
  inverter a ordem dos pontos NÃO altera forma, coordenadas, escala ou posição
  — altera apenas o sentido de percurso do anel;
- fechamento implícito: se o anel de origem repetir o primeiro ponto no final,
  essa repetição é removida (normalização de representação, não de geometria);
  nenhum outro ponto é removido.

Este módulo NÃO implementa geometria de engenharia: a validação estrutural é
delegada a `domain.validar_contornos` (ADR-008). Sem dependências externas.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Optional

from domain.entidades import GeometriaPadrao, validar_contornos


CONTRATO_CONSUMO_VERSAO = "1.0"

CAMINHO_GEOMETRIAS = "dados/geometrias.json"
CAMINHO_ASSOCIACOES = "dados/perfil_geometria.json"

# Enumeração fechada dos níveis reconhecidos (plano de curadoria, Sprint E.2).
# Chave AUSENTE no JSON equivale ao primeiro nível. Um valor PRESENTE porém
# fora desta tupla é erro explícito — nunca tratado silenciosamente como válido.
NIVEIS_RECONHECIDOS = (
    "0_bruto_aproximado",
    "1_envelope_funcional",
    "2_renderizavel_comercial",
    "3_vetorial_validado",
    "4_alta_fidelidade",
)
NIVEL_PADRAO = "0_bruto_aproximado"

# Somente estes níveis, formalmente conhecidos, determinam renderizavel=True.
# Não se usa ordenação lexical nem "nível atual ou superior".
NIVEIS_RENDERIZAVEIS = frozenset({
    "2_renderizavel_comercial",
    "3_vetorial_validado",
    "4_alta_fidelidade",
})

# Valores controlados de fonte_contorno.
FONTE_NOVO = "contorno_externo_vazios_internos"
FONTE_LEGADO = "contorno_mm_legado"

# Derivação de fabricante a partir do prefixo do perfil_id. O campo NÃO existe
# em dados/perfil_geometria.json (ver ADR-009): é exposto como conveniência
# derivada (`fabricante_derivado`), nunca como dado armazenado. Prefixo
# desconhecido -> None. Não substitui um eventual fabricante do domínio nem
# estabelece intercambiabilidade entre perfis/fabricantes (ADR-004).
_FABRICANTE_POR_PREFIXO = {
    "ALCOA": "Alcoa",
    "HYDRO": "Hydro",
    "VITRALSUL": "Vitral Sul",
    "TAMBORE": "Tamboré",
    "CENTENARIO": "Centenário",
    "ASA": "ASA",
}


class ContratoInvalido(Exception):
    """Um registro da biblioteca viola o contrato mínimo de consumo (ADR-009).

    Distinto de domain.ContornoInvalido (que é sobre a geometria em si);
    aqui a falha é de contrato: nível desconhecido, id vazio, associação
    pendurada, etc."""


# ---------------------------------------------------------------------------
# Anéis: abertura (fechamento implícito) + normalização de orientação
# ---------------------------------------------------------------------------

def _abrir_anel(anel) -> tuple:
    """Converte para tupla de tuplas e remove APENAS a repetição de fechamento
    (último ponto == primeiro). Nenhum outro ponto é removido."""
    t = [(float(x), float(y)) for x, y in anel]
    if len(t) >= 2 and t[0] == t[-1]:
        t = t[:-1]
    return tuple(t)


def _area_com_sinal(anel) -> float:
    """Shoelace com sinal: > 0 anti-horário (CCW), < 0 horário (CW)."""
    s = 0.0
    n = len(anel)
    for i in range(n):
        x1, y1 = anel[i]
        x2, y2 = anel[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _orientar(anel_aberto, ccw: bool) -> tuple:
    """Devolve o anel (já aberto) no sentido pedido. Inverter a ordem não altera
    a forma — apenas o sentido de percurso."""
    horario = _area_com_sinal(anel_aberto) < 0
    precisa_inverter = (ccw and horario) or (not ccw and not horario)
    return tuple(reversed(anel_aberto)) if precisa_inverter else anel_aberto


# ---------------------------------------------------------------------------
# DTOs imutáveis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoundingBoxDTO:
    """Caixa envolvente calculada, em mm. Só existe quando há contorno —
    geometrias sem coordenadas têm bounding_box=None (nunca zeros artificiais)."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def largura(self) -> float:
        return round(self.max_x - self.min_x, 4)

    @property
    def altura(self) -> float:
        return round(self.max_y - self.min_y, 4)

    def para_dict(self) -> dict:
        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "max_x": self.max_x,
            "max_y": self.max_y,
            "largura": self.largura,
            "altura": self.altura,
        }


@dataclass(frozen=True)
class GeometriaConsumivel:
    """Representação imutável de GeometriaPadrao na fronteira de consumo.

    Coordenadas em tuplas de tuplas (imutáveis de fato). `vazios_internos` é
    SEMPRE uma tupla (nunca None); tupla vazia é válida. O contrato expõe uma
    única forma geométrica (contorno_externo + vazios_internos); a origem do
    contorno é indicada por `fonte_contorno`."""
    codigo: str
    familia_mercado: Optional[str]
    descricao: Optional[str]
    unidade: str
    referencial: str
    eixo_x: str
    eixo_y: str
    nivel_contorno: str
    renderizavel: bool
    contorno_externo: Optional[tuple]      # CCW, ou None quando ainda não há
    vazios_internos: tuple                 # cada anel em CW; sempre tupla
    fonte_contorno: Optional[str]          # FONTE_NOVO / FONTE_LEGADO / None
    bounding_box: Optional[BoundingBoxDTO]
    status_contorno: Optional[str]
    metodo_contorno: Optional[str]
    evidencia_contorno: Optional[str]
    versao_schema: str = CONTRATO_CONSUMO_VERSAO

    @property
    def largura_mm(self) -> Optional[float]:
        return None if self.bounding_box is None else self.bounding_box.largura

    @property
    def altura_mm(self) -> Optional[float]:
        return None if self.bounding_box is None else self.bounding_box.altura

    def para_dict(self) -> dict:
        """Serialização de fronteira: tuplas viram arrays (listas)."""
        def anel(a):
            return [[x, y] for x, y in a] if a is not None else None
        return {
            "codigo": self.codigo,
            "familia_mercado": self.familia_mercado,
            "descricao": self.descricao,
            "unidade": self.unidade,
            "referencial": self.referencial,
            "eixo_x": self.eixo_x,
            "eixo_y": self.eixo_y,
            "nivel_contorno": self.nivel_contorno,
            "renderizavel": self.renderizavel,
            "contorno_externo": anel(self.contorno_externo),
            "vazios_internos": [anel(v) for v in self.vazios_internos],
            "fonte_contorno": self.fonte_contorno,
            "bounding_box": (self.bounding_box.para_dict()
                             if self.bounding_box is not None else None),
            "status_contorno": self.status_contorno,
            "metodo_contorno": self.metodo_contorno,
            "evidencia_contorno": self.evidencia_contorno,
            "versao_schema": self.versao_schema,
        }


@dataclass(frozen=True)
class AssociacaoConsumivel:
    """Representação imutável de PerfilGeometria (ADR-005) na fronteira.

    Preserva os sete campos armazenados em perfil_geometria.json e acrescenta
    os campos de contrato `versao_schema` e `fabricante_derivado`. NÃO carrega
    pontos de geometria (só referencia por id). `fabricante_derivado` é
    INFERIDO do prefixo de perfil_id (não é dado armazenado; ver ADR-009): não
    substitui um eventual fabricante do domínio nem estabelece
    intercambiabilidade (ADR-004)."""
    perfil_id: str
    geometria_padrao_id: str
    responsavel_homologacao: str
    metodo_validacao: str
    data: str
    nivel_de_confianca: str
    observacoes: Optional[str]
    fabricante_derivado: Optional[str]     # inferido do prefixo, não armazenado
    versao_schema: str = CONTRATO_CONSUMO_VERSAO

    def para_dict(self) -> dict:
        return {
            "perfil_id": self.perfil_id,
            "geometria_padrao_id": self.geometria_padrao_id,
            "responsavel_homologacao": self.responsavel_homologacao,
            "metodo_validacao": self.metodo_validacao,
            "data": self.data,
            "nivel_de_confianca": self.nivel_de_confianca,
            "observacoes": self.observacoes,
            "fabricante_derivado": self.fabricante_derivado,
            "versao_schema": self.versao_schema,
        }


@dataclass(frozen=True)
class BibliotecaConsumivel:
    """Recorte imutável de toda a biblioteca na fronteira de consumo. As
    coleções são tuplas e o índice interno é um MappingProxyType (somente
    leitura) — a imutabilidade do ADR-009 vale também para a biblioteca."""
    geometrias: tuple
    associacoes: tuple

    _por_codigo: MappingProxyType = field(compare=False, repr=False, default=None)

    def __post_init__(self):
        indice = {g.codigo: g for g in self.geometrias}
        if len(indice) != len(self.geometrias):
            raise ContratoInvalido("códigos de geometria duplicados")
        object.__setattr__(self, "_por_codigo", MappingProxyType(indice))

    def geometria(self, codigo: str) -> GeometriaConsumivel:
        try:
            return self._por_codigo[codigo]
        except KeyError:
            raise ContratoInvalido(f"geometria inexistente: {codigo}")

    def renderizaveis(self) -> tuple:
        return tuple(g for g in self.geometrias if g.renderizavel)


# ---------------------------------------------------------------------------
# Resolução de nível (enumeração explícita)
# ---------------------------------------------------------------------------

def _resolver_nivel(registro: dict) -> str:
    if "nivel_contorno" not in registro:
        return NIVEL_PADRAO                    # ausência ≡ bruto (não é erro)
    nivel = registro["nivel_contorno"]
    if nivel not in NIVEIS_RECONHECIDOS:
        raise ContratoInvalido(
            f"{registro.get('id', '?')}: nivel_contorno desconhecido "
            f"'{nivel}' — não reconhecido pela enumeração do contrato "
            f"({', '.join(NIVEIS_RECONHECIDOS)})")
    return nivel


def _bounding_box(anel) -> BoundingBoxDTO:
    xs = [p[0] for p in anel]
    ys = [p[1] for p in anel]
    return BoundingBoxDTO(min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# Adaptação de um registro de geometria
# ---------------------------------------------------------------------------

def _adaptar_geometria(registro: dict) -> GeometriaConsumivel:
    codigo = registro.get("id") or ""
    if not codigo:
        raise ContratoInvalido("geometria sem id")

    nivel = _resolver_nivel(registro)
    renderizavel = nivel in NIVEIS_RENDERIZAVEIS

    externo_bruto = registro.get("contorno_externo")
    legado_bruto = registro.get("contorno_mm")

    contorno_externo = None
    vazios = ()
    fonte = None
    bbox = None

    if externo_bruto:
        # abre os anéis (remove fechamento explícito) e valida a geometria
        # ORIGINAL via domínio antes de normalizar a orientação
        ext_aberto = _abrir_anel(externo_bruto)
        vazios_abertos = tuple(_abrir_anel(v)
                               for v in (registro.get("vazios_internos") or []))
        validar_contornos(GeometriaPadrao(
            id=codigo, contorno_mm=[], status="homologada", versao="0",
            contorno_externo=[tuple(p) for p in ext_aberto],
            vazios_internos=[[tuple(p) for p in v] for v in vazios_abertos]))
        contorno_externo = _orientar(ext_aberto, ccw=True)
        vazios = tuple(_orientar(v, ccw=False) for v in vazios_abertos)
        fonte = FONTE_NOVO
        bbox = _bounding_box(contorno_externo)
    elif legado_bruto:
        leg_aberto = _abrir_anel(legado_bruto)
        validar_contornos(GeometriaPadrao(
            id=codigo, contorno_mm=[tuple(p) for p in leg_aberto],
            status="homologada", versao="0"))
        contorno_externo = _orientar(leg_aberto, ccw=True)
        vazios = ()
        fonte = FONTE_LEGADO
        bbox = _bounding_box(contorno_externo)

    if renderizavel and contorno_externo is None:
        raise ContratoInvalido(
            f"{codigo}: nivel {nivel} exige contorno, mas nenhum foi encontrado")

    return GeometriaConsumivel(
        codigo=codigo,
        familia_mercado=registro.get("familia_mercado"),
        descricao=registro.get("descricao"),
        unidade="mm",
        referencial="local_do_perfil",
        eixo_x="positivo_para_direita",
        eixo_y="positivo_para_cima",
        nivel_contorno=nivel,
        renderizavel=renderizavel,
        contorno_externo=contorno_externo,
        vazios_internos=vazios,
        fonte_contorno=fonte,
        bounding_box=bbox,
        status_contorno=registro.get("status_contorno"),
        metodo_contorno=registro.get("metodo_contorno"),
        evidencia_contorno=registro.get("evidencia_contorno"),
    )


# Campos obrigatórios da associação (inspeção: presentes nas 245). Não são
# mascarados: ausência/valor vazio falha explicitamente, distinguindo dos casos
# de string vazia silenciosa. `observacoes` é obrigatório como CHAVE, mas seu
# valor pode ser None.
_ASSOC_OBRIGATORIOS = (
    "perfil_id", "geometria_padrao_id", "responsavel_homologacao",
    "metodo_validacao", "data", "nivel_de_confianca",
)


def _adaptar_associacao(registro: dict) -> AssociacaoConsumivel:
    ident = registro.get("perfil_id") or registro.get("geometria_padrao_id") or "?"
    for campo in _ASSOC_OBRIGATORIOS:
        if campo not in registro:
            raise ContratoInvalido(
                f"associação {ident}: campo obrigatório ausente '{campo}'")
        valor = registro[campo]
        if not isinstance(valor, str) or not valor.strip():
            raise ContratoInvalido(
                f"associação {ident}: campo obrigatório '{campo}' vazio ou "
                f"inválido ({valor!r})")
    if "observacoes" not in registro:
        raise ContratoInvalido(
            f"associação {ident}: chave obrigatória 'observacoes' ausente "
            f"(valor pode ser None, mas a chave deve existir)")
    prefixo = registro["perfil_id"].split("-", 1)[0].upper()
    return AssociacaoConsumivel(
        perfil_id=registro["perfil_id"],
        geometria_padrao_id=registro["geometria_padrao_id"],
        responsavel_homologacao=registro["responsavel_homologacao"],
        metodo_validacao=registro["metodo_validacao"],
        data=registro["data"],
        nivel_de_confianca=registro["nivel_de_confianca"],
        observacoes=registro["observacoes"],
        fabricante_derivado=_FABRICANTE_POR_PREFIXO.get(prefixo),  # None se desconhecido
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def carregar_geometrias(caminho: str = CAMINHO_GEOMETRIAS) -> tuple:
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    return tuple(_adaptar_geometria(g) for g in dados["geometrias"])


def carregar_associacoes(caminho: str = CAMINHO_ASSOCIACOES) -> tuple:
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    return tuple(_adaptar_associacao(a) for a in dados["associacoes"])


def carregar_biblioteca(
        caminho_geometrias: str = CAMINHO_GEOMETRIAS,
        caminho_associacoes: str = CAMINHO_ASSOCIACOES) -> BibliotecaConsumivel:
    """Carrega geometrias + associações e verifica a integridade referencial:
    toda associação deve apontar para uma geometria carregada (ADR-005)."""
    geometrias = carregar_geometrias(caminho_geometrias)
    associacoes = carregar_associacoes(caminho_associacoes)
    codigos = {g.codigo for g in geometrias}
    for a in associacoes:
        if a.geometria_padrao_id not in codigos:
            raise ContratoInvalido(
                f"associação {a.perfil_id} referencia geometria inexistente "
                f"'{a.geometria_padrao_id}'")
    return BibliotecaConsumivel(geometrias=geometrias, associacoes=associacoes)
