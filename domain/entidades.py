"""
EsquadriaCore — domain
======================
Entidades do Modelo de Domínio (Volume 3 da documentação v1.0).

Regras respeitadas (ver Volume 3 e ADRs):
- Perfil nunca embute geometria — referencia via PerfilGeometria (ADR-005).
- Cena Técnica referencia Componentes por id, nunca copia dado físico (ADR-001).
- Vista carrega só apresentação, nunca dado físico (ADR-002).
- FamíliaMercado é vocabulário de mercado, nunca implica intercambiabilidade (ADR-004).

Consolidado no Sprint 3.5 a partir dos protótipos das Fases 0-4.
Zero funcionalidade nova em relação aos protótipos.
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Conhecimento / vocabulário de mercado
# ---------------------------------------------------------------------------

@dataclass
class AliasFabricante:
    fabricante: str
    prefixo_codigo: str
    nome_local: Optional[str] = None


@dataclass
class FamiliaMercado:
    """Vocabulário de mercado (ADR-004). Persistente. Nunca conhece geometria."""
    id: str
    nome_canonico: str
    bitola_mm: Optional[float] = None
    origem_historica: Optional[str] = None
    descricao: Optional[str] = None
    aliases_conhecidos: list[AliasFabricante] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Geometria homologada (ativo de engenharia)
# ---------------------------------------------------------------------------

@dataclass
class GeometriaPadrao:
    """Ativo de engenharia compartilhado (ADR-005). Persistente, versionado.
    Nunca conhece fabricante, peso ou preço."""
    id: str
    contorno_mm: list[tuple[float, float]]
    status: str  # "bruto_aproximado" | "homologado"
    versao: str
    descricao: Optional[str] = None
    svg_bruto_ref: Optional[str] = None
    curado_por: Optional[str] = None
    data_curadoria: Optional[str] = None
    # formato novo (ADR-008, rascunho): perfil de alumínio é OCO — silhueta
    # externa + câmaras vazadas. Opcional: geometrias antigas seguem válidas
    # com contorno_mm (polígono preenchido simples).
    contorno_externo: Optional[list] = None   # lista de (x,y) da silhueta externa
    vazios_internos: Optional[list] = None    # lista de listas de (x,y) — câmaras ocas
    nivel_contorno: str = "0_bruto_aproximado"  # escala de fidelidade (plano de curadoria, Sprint E.2)


@dataclass
class PerfilGeometria:
    """Entidade de ASSOCIAÇÃO AUDITÁVEL (ADR-005) — não é cache, não é otimização,
    não é tabela descartável. Registro de quem homologou o compartilhamento."""
    perfil_id: str
    geometria_padrao_id: str
    responsavel_homologacao: str
    metodo_validacao: str
    data: str
    nivel_de_confianca: str  # "alto" | "medio" | "baixo" (conjunto fechado, Volume 9)
    observacoes: Optional[str] = None


# ---------------------------------------------------------------------------
# Qualidade de extração (Value Object, sem identidade — Volume 9)
# ---------------------------------------------------------------------------

@dataclass
class QualidadePerfil:
    """Value Object embutido no Perfil. Sem id próprio, sem ciclo de vida próprio."""
    codigo_valido: bool = False
    peso_valido: bool = False
    vetor_encontrado: bool = False
    descricao_encontrada: bool = False
    escala_identificada: bool = False

    @property
    def indice(self) -> int:
        return sum([self.codigo_valido, self.peso_valido, self.vetor_encontrado,
                    self.descricao_encontrada, self.escala_identificada])

    @property
    def prioridade_revisao(self) -> str:
        # nome escolhido para não colidir com o status do fluxo de vida (Volume 9)
        return "revisar_primeiro" if self.indice <= 2 else "normal"


# ---------------------------------------------------------------------------
# Perfil (implementação de um fabricante)
# ---------------------------------------------------------------------------

@dataclass
class Perfil:
    """Implementação de um fabricante. Persistente.
    NUNCA embute geometria (referencia via PerfilGeometria).
    peso_suspeito=True quando o dado de origem é inválido (caso Euroshow) —
    nunca descartar o registro (Volume 9)."""
    id: str
    fabricante: str
    codigo_fabricante: str
    peso_kg_m: Optional[float] = None
    peso_suspeito: bool = False
    acabamento: Optional[str] = None
    liga: Optional[str] = None
    familia_mercado_id: Optional[str] = None
    categoria: Optional[str] = None       # preenchido na Curadoria
    orientacao: Optional[str] = None      # "vertical" | "horizontal" | "ambos"
    fonte: Optional[str] = None           # proveniência (catálogo, página)
    qualidade: QualidadePerfil = field(default_factory=QualidadePerfil)
    # fluxo de vida (Volume 3): extraido -> normalizado -> curado -> homologado
    #                            -> disponivel -> obsoleto
    estado_ciclo_vida: str = "extraido"


# ---------------------------------------------------------------------------
# Composição
# ---------------------------------------------------------------------------

@dataclass
class Componente:
    """Abstração comum sobre Perfil/Ferragem/Vidro dentro de um Tipo."""
    instancia_id: str
    perfil_id: str
    orientacao: str                        # "vertical" | "horizontal" | "ambos"
    funcao_na_composicao: Optional[str] = None


@dataclass
class Tipo:
    """Composição de Componentes segundo uma Regra.
    'Regra' hoje é texto/parâmetro — não é entidade (observação registrada no
    Volume 3, aguardando evidência de múltiplos Tipos reais)."""
    id: str
    nome: str
    regra: str
    largura_mm: float
    altura_mm: float
    componentes: list[Componente] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Representação (transitórias — Volume 3)
# ---------------------------------------------------------------------------

@dataclass
class InstanciaCena:
    """Uma peça posicionada na Cena. REFERENCIA o perfil por id — nunca copia
    dado físico (ADR-001, o invariante mais importante do domínio)."""
    instancia_id: str
    perfil_id: str
    posicao_mm: tuple[float, float]
    rotacao_graus: float
    comprimento_mm: float


@dataclass
class CenaTecnica:
    """Transitória: gerada a partir de um Tipo, descartável e regerável."""
    id: str
    tipo_id: str
    instancias: list[InstanciaCena] = field(default_factory=list)


@dataclass
class Vista:
    """Transitória. SÓ apresentação (ADR-002): ângulo, projeção, estilo.
    Nunca dado físico — se precisar, pergunta à Cena/Componente."""
    id: str
    cena_id: str
    tipo_projecao: str                     # "frontal" | "isometrica" | "explodida" | "corte"
    angulo_elevacao_graus: float = 35.264
    angulo_azimute_graus: float = 45.0
    escala: float = 1.0
    estilo: str = "comercial_realista"
    cor_aluminio: str = "#c9cdd1"
    cor_vidro: str = "#bfe3f0"
    opacidade_vidro: float = 0.35


# ---------------------------------------------------------------------------
# Erros do domínio (Volume 9 — Modelo de Erros)
# ---------------------------------------------------------------------------

class ErroDominio(Exception):
    """Base dos erros do domínio."""


class GeometryNotFound(ErroDominio):
    """PerfilGeometria aponta para GeometriaPadrao inexistente."""


class InvalidProfile(ErroDominio):
    """Perfil falha nas validações estruturais (Volume 9)."""


class InvalidFamily(ErroDominio):
    """FamíliaMercado referenciada não existe."""


class MissingComponent(ErroDominio):
    """Cena Técnica referencia Componente/Perfil inexistente (torna o ADR-001
    verificável em runtime)."""


class ProviderFailure(ErroDominio):
    """Provider não conseguiu extrair dado da fonte."""


class RendererFailure(ErroDominio):
    """Renderer não conseguiu produzir imagem a partir da Vista."""


class PipelineFailure(ErroDominio):
    """CATEGORIA RESIDUAL: exclusivamente para falhas de orquestração não
    enquadradas nas categorias anteriores. Não usar como atalho genérico."""


class ContornoInvalido(ErroDominio):
    """Contorno da GeometriaPadrao falha nas validações do ADR-008."""


# ---------------------------------------------------------------------------
# Validações de contorno (ADR-008 / Volume 9 via adendo) — domínio puro,
# sem dependências externas. Fechamento é implícito (último ponto != primeiro).
# ---------------------------------------------------------------------------

def _area_poligono(pontos) -> float:
    s = 0.0
    n = len(pontos)
    for i in range(n):
        x1, y1 = pontos[i]
        x2, y2 = pontos[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _ponto_no_poligono(pt, poligono) -> bool:
    """Ray casting clássico."""
    x, y = pt
    dentro = False
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cruz = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cruz:
                dentro = not dentro
    return dentro


def _segmentos_se_cruzam(p1, p2, p3, p4) -> bool:
    """Interseção própria (cruzamento real, não toque em vértice)."""
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4)


def _autointersecta(poligono) -> bool:
    n = len(poligono)
    for i in range(n):
        a1, a2 = poligono[i], poligono[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue  # arestas adjacentes compartilham vértice
            b1, b2 = poligono[j], poligono[(j + 1) % n]
            if _segmentos_se_cruzam(a1, a2, b1, b2):
                return True
    return False


def _validar_anel(pontos, nome: str):
    if len(pontos) < 3:
        raise ContornoInvalido(f"{nome} tem menos de 3 pontos")
    if tuple(pontos[0]) == tuple(pontos[-1]):
        raise ContornoInvalido(
            f"{nome}: fechamento deve ser implícito (último ponto repete o primeiro)")
    if _area_poligono(pontos) <= 0:
        raise ContornoInvalido(f"{nome} tem área nula")
    if _autointersecta(pontos):
        raise ContornoInvalido(f"{nome} se auto-intersecta")


def validar_contornos(geo: "GeometriaPadrao") -> None:
    """Validações do ADR-008. Falha explícita (ContornoInvalido), nunca silenciosa.

    Regra 1: pelo menos um formato (contorno_mm legado OU contorno_externo).
    Regras 2-4: anéis válidos, vazios contidos no externo e sem cruzamento
    entre si. Quando os dois formatos coexistem, o novo é preferencial."""
    tem_legado = bool(geo.contorno_mm)
    tem_novo = bool(geo.contorno_externo)
    if not tem_legado and not tem_novo:
        raise ContornoInvalido(
            f"{geo.id}: nenhum formato de contorno presente "
            f"(contorno_mm legado ou contorno_externo)")
    if not tem_novo:
        return  # formato legado puro: sem validações adicionais (compatibilidade)

    _validar_anel(geo.contorno_externo, f"{geo.id}.contorno_externo")
    vazios = geo.vazios_internos or []
    for k, vazio in enumerate(vazios):
        nome = f"{geo.id}.vazios_internos[{k}]"
        _validar_anel(vazio, nome)
        if not all(_ponto_no_poligono(p, geo.contorno_externo) for p in vazio):
            raise ContornoInvalido(f"{nome} não está contido no contorno_externo")
    for k in range(len(vazios)):
        for m in range(k + 1, len(vazios)):
            cruza_aresta = any(
                _segmentos_se_cruzam(vazios[k][i], vazios[k][(i + 1) % len(vazios[k])],
                                     vazios[m][j], vazios[m][(j + 1) % len(vazios[m])])
                for i in range(len(vazios[k])) for j in range(len(vazios[m])))
            contem_vertice = (
                any(_ponto_no_poligono(p, vazios[m]) for p in vazios[k])
                or any(_ponto_no_poligono(p, vazios[k]) for p in vazios[m]))
            if cruza_aresta or contem_vertice:
                raise ContornoInvalido(
                    f"{geo.id}: vazios_internos[{k}] e [{m}] se cruzam")
