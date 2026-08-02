"""Modelos tipados da promoção. Imutáveis — nenhuma etapa muta candidato."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Perfis do microlote E.4B, na ordem canônica do config.
PERFIS_E4B = ("SU-001", "SU-002", "SU-003", "SU-039",
              "SU-040", "SU-041", "SU-053", "SU-102")

LOTES = {"E4B": PERFIS_E4B}

# Estados de curadoria que autorizam promoção. `CANDIDATO_PREVIAMENTE_APROVADO`
# é o SU-040, aprovado antes do pipeline atual e revalidado por regressão.
ESTADOS_PROMOVIVEIS = frozenset({
    "CANDIDATO_GEOMETRICO_APROVADO",
    "CANDIDATO_PREVIAMENTE_APROVADO",
})

NIVEL_PROMOCAO = "2_renderizavel_comercial"


@dataclass(frozen=True)
class CandidatoPromocao:
    codigo_perfil: str
    id_geometria: str
    dimensao_nominal_mm: tuple[float, float]
    contorno_externo: tuple[tuple[float, float], ...]
    vazios_internos: tuple[tuple[tuple[float, float], ...], ...]
    quantidade_componentes: int
    quantidade_vazios: int
    nivel_contorno: str
    fabricante: str
    fonte: str
    procedencia: dict
    hash_contorno: str
    hash_metricas: str
    hash_operacoes: str
    decisao_curadoria: str
    estado_curadoria: str
    arquivo_origem: str


@dataclass(frozen=True)
class GeometriaOficialProposta:
    id: str
    registro: dict          # exatamente o que vai para dados/geometrias.json
    codigo_perfil: str


@dataclass(frozen=True)
class AssociacaoPerfilGeometriaProposta:
    perfil_id: str
    geometria_padrao_id: str
    registro: dict
    codigo_perfil: str
    motivo: str = "promocao_e4c"


@dataclass(frozen=True)
class ResultadoValidacao:
    """`ok=False` sempre carrega ao menos uma falha descrita por completo."""
    ok: bool
    falhas: tuple[dict, ...] = ()
    avisos: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.ok

    @staticmethod
    def aprovado(avisos: tuple[str, ...] = ()) -> "ResultadoValidacao":
        return ResultadoValidacao(True, (), avisos)

    @staticmethod
    def reprovado(perfil: str, regra: str, encontrado, esperado,
                  arquivo: str) -> "ResultadoValidacao":
        return ResultadoValidacao(False, ({
            "perfil": perfil, "regra": regra,
            "encontrado": encontrado, "esperado": esperado,
            "arquivo_origem": arquivo,
        },))

    def somar(self, outro: "ResultadoValidacao") -> "ResultadoValidacao":
        return ResultadoValidacao(self.ok and outro.ok,
                                  self.falhas + outro.falhas,
                                  self.avisos + outro.avisos)

    def descrever(self) -> str:
        if self.ok:
            return "aprovado" + (f" ({len(self.avisos)} avisos)" if self.avisos else "")
        return "\n".join(
            f"  {f['perfil']}: {f['regra']}\n"
            f"      encontrado: {f['encontrado']!r}\n"
            f"      esperado  : {f['esperado']!r}\n"
            f"      origem    : {f['arquivo_origem']}"
            for f in self.falhas)


@dataclass(frozen=True)
class ConflitoPromocao:
    tipo: str
    perfil: str
    identificador: str
    detalhe: str
    bloqueante: bool = True


@dataclass(frozen=True)
class PlanoPromocao:
    lote: str
    geometrias_novas: tuple[GeometriaOficialProposta, ...]
    geometrias_reutilizadas: tuple[str, ...]
    associacoes_novas: tuple[AssociacaoPerfilGeometriaProposta, ...]
    associacoes_reutilizadas: tuple[str, ...]
    conflitos: tuple[ConflitoPromocao, ...]
    candidatos: tuple[CandidatoPromocao, ...]

    @property
    def bloqueios(self) -> tuple[ConflitoPromocao, ...]:
        return tuple(c for c in self.conflitos if c.bloqueante)

    @property
    def vazio(self) -> bool:
        return not self.geometrias_novas and not self.associacoes_novas


@dataclass(frozen=True)
class ResultadoSimulacao:
    plano: PlanoPromocao
    geometrias_antes: int
    geometrias_depois: int
    associacoes_antes: int
    associacoes_depois: int
    ids_criados: tuple[str, ...]
    ids_reutilizados: tuple[str, ...]
    associacoes_criadas: tuple[str, ...]
    associacoes_reutilizadas: tuple[str, ...]
    registros_antigos_alterados: tuple[str, ...]
    avisos: tuple[str, ...]
    validacao: ResultadoValidacao
    geometrias_depois_doc: dict = field(default_factory=dict, repr=False)
    associacoes_depois_doc: dict = field(default_factory=dict, repr=False)

    @property
    def aprovada(self) -> bool:
        return (self.validacao.ok
                and not self.plano.bloqueios
                and not self.registros_antigos_alterados)


@dataclass(frozen=True)
class EstadoTransacao:
    backups: dict
    aplicado: bool
    rollback_executado: bool
    detalhe: str = ""


@dataclass(frozen=True)
class ResultadoPromocao:
    ok: bool
    simulacao: ResultadoSimulacao
    hash_antes: dict
    hash_depois: dict
    transacao: EstadoTransacao
    manifesto: dict
    erro: str = ""


@dataclass(frozen=True)
class ManifestoPromocao:
    conteudo: dict
    caminho: Path
