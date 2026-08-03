"""Modelos da receita de tipologia — E.4D.

O que esta camada é: um registro **auditável de conhecimento** sobre como uma
tipologia se monta. O que ela não é: um motor de cálculo. Nenhuma fórmula de
corte, vidro, folga ou sobreposição existe aqui, porque nenhuma foi confirmada.

A regra que governa tudo neste módulo: **valor desconhecido não vira número**.
`None` significa "não informado" e nunca é lido como zero; papel não confirmado
é `NAO_CONFIRMADO`; regra sem evidência fica `PENDENTE` com `expressao=None`.
Um `0` no lugar de um desconhecido produziria uma peça com medida errada sem
nenhum aviso — é o tipo de erro que só aparece na serralheria.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class EstadoConhecimento(str, Enum):
    """De onde vem o que se afirma. A ordem importa: só os quatro primeiros
    autorizam cálculo oficial."""
    CONFIRMADO_CATALOGO = "CONFIRMADO_CATALOGO"
    CONFIRMADO_ESPECIALISTA = "CONFIRMADO_ESPECIALISTA"
    CONFIRMADO_CASO_REAL = "CONFIRMADO_CASO_REAL"
    DERIVADO_DE_REGRA_APROVADA = "DERIVADO_DE_REGRA_APROVADA"
    HIPOTESE = "HIPOTESE"
    PENDENTE = "PENDENTE"


ESTADOS_CONFIRMADOS = frozenset({
    EstadoConhecimento.CONFIRMADO_CATALOGO,
    EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
    EstadoConhecimento.CONFIRMADO_CASO_REAL,
    EstadoConhecimento.DERIVADO_DE_REGRA_APROVADA,
})

# `HIPOTESE` é conhecimento honesto — uma leitura plausível ainda não
# arbitrada. Nunca autoriza cálculo, e por isso fica fora do conjunto acima.
ESTADOS_NAO_CALCULAVEIS = frozenset({EstadoConhecimento.HIPOTESE,
                                     EstadoConhecimento.PENDENTE})


class PapelComponente(str, Enum):
    """Papéis POSSÍVEIS numa correr de duas folhas.

    A existência do enum não afirma qual perfil exerce qual papel: isso é
    decisão de domínio e ainda não foi tomada."""
    MARCO_SUPERIOR = "MARCO_SUPERIOR"
    MARCO_INFERIOR = "MARCO_INFERIOR"
    MARCO_LATERAL_ESQUERDO = "MARCO_LATERAL_ESQUERDO"
    MARCO_LATERAL_DIREITO = "MARCO_LATERAL_DIREITO"
    TRAVESSA_SUPERIOR_FOLHA = "TRAVESSA_SUPERIOR_FOLHA"
    TRAVESSA_INFERIOR_FOLHA = "TRAVESSA_INFERIOR_FOLHA"
    MONTANTE_LATERAL_FOLHA = "MONTANTE_LATERAL_FOLHA"
    ENCONTRO_CENTRAL = "ENCONTRO_CENTRAL"
    MAO_DE_AMIGO = "MAO_DE_AMIGO"
    BAGUETE = "BAGUETE"
    NAO_CONFIRMADO = "NAO_CONFIRMADO"


TIPOS_DE_FONTE = frozenset({
    "catalogo", "medicao_fisica", "especialista_de_dominio",
    "lista_de_corte_real", "software_externo", "foto", "croqui",
    "tabela_de_fabricacao",
})

# Alvos que uma regra dimensional pode governar. Declarar o alvo não cria a
# fórmula: é só o vocabulário do que ainda falta responder.
ALVOS_DIMENSIONAIS = (
    "corte_marco_superior",
    "corte_marco_inferior",
    "corte_marco_lateral",
    "largura_folha",
    "altura_folha",
    "largura_vidro",
    "altura_vidro",
    "corte_baguete_horizontal",
    "corte_baguete_vertical",
)

ESTADO_RECEITA_PRELIMINAR = "PRELIMINAR_AGUARDANDO_DADOS_DE_CAMPO"


# ---------------------------------------------------------------------------
# Resultado de validação
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoValidacao:
    """`ok=False` sempre carrega ao menos uma falha descrita por completo.

    Mesmo formato usado em `curadoria/promocao/modelos.py`, redefinido aqui de
    propósito: a composição não deve depender das ferramentas de curadoria."""
    ok: bool
    falhas: tuple[dict, ...] = ()
    avisos: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.ok

    @staticmethod
    def aprovado(avisos: tuple[str, ...] = ()) -> "ResultadoValidacao":
        return ResultadoValidacao(True, (), avisos)

    @staticmethod
    def reprovado(alvo: str, regra: str, encontrado, esperado,
                  origem: str) -> "ResultadoValidacao":
        return ResultadoValidacao(False, ({
            "alvo": alvo, "regra": regra,
            "encontrado": encontrado, "esperado": esperado,
            "origem": origem,
        },))

    def somar(self, outro: "ResultadoValidacao") -> "ResultadoValidacao":
        return ResultadoValidacao(self.ok and outro.ok,
                                  self.falhas + outro.falhas,
                                  self.avisos + outro.avisos)

    def descrever(self) -> str:
        if self.ok:
            return "aprovado" + (f" ({len(self.avisos)} avisos)"
                                 if self.avisos else "")
        return "\n".join(
            f"  {f['alvo']}: {f['regra']}\n"
            f"      encontrado: {f['encontrado']!r}\n"
            f"      esperado  : {f['esperado']!r}\n"
            f"      origem    : {f['origem']}"
            for f in self.falhas)


class ReceitaErro(RuntimeError):
    """Falha de carregamento ou estrutura. Sempre nomeia a origem."""


# ---------------------------------------------------------------------------
# Evidência
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FonteEvidencia:
    """De onde veio a afirmação. Sem isto, `CONFIRMADO` seria só uma palavra."""
    tipo: str
    referencia: str
    descricao: str
    estado: EstadoConhecimento
    responsavel: str | None = None
    data: str | None = None

    def __post_init__(self):
        if self.tipo not in TIPOS_DE_FONTE:
            raise ReceitaErro(
                f"tipo de fonte desconhecido: {self.tipo!r} "
                f"(conhecidos: {sorted(TIPOS_DE_FONTE)})")
        if not self.referencia:
            raise ReceitaErro(f"fonte {self.tipo}: referência vazia")
        # Caminho absoluto amarraria a evidência à máquina de quem registrou.
        if self.referencia.startswith("/") or ":\\" in self.referencia:
            raise ReceitaErro(
                f"fonte {self.tipo}: referência absoluta não é permitida "
                f"({self.referencia!r}) — use caminho relativo à raiz do repo "
                f"ou identificador externo")

    def para_dict(self) -> dict:
        return {"tipo": self.tipo, "referencia": self.referencia,
                "descricao": self.descricao, "estado": self.estado.value,
                "responsavel": self.responsavel, "data": self.data}


# ---------------------------------------------------------------------------
# Referência à biblioteca oficial
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReferenciaPerfilOficial:
    """Ponteiro para a biblioteca oficial — nunca cópia de geometria (ADR-001).

    A receita não guarda contorno: ela cita `id_geometria`. Copiar pontos aqui
    criaria uma segunda verdade que envelheceria em silêncio."""
    codigo_perfil: str
    id_geometria: str
    perfil_id_oficial: str

    def para_dict(self) -> dict:
        return {"codigo_perfil": self.codigo_perfil,
                "id_geometria": self.id_geometria,
                "perfil_id_oficial": self.perfil_id_oficial}


# ---------------------------------------------------------------------------
# Componente da receita
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ComponenteReceita:
    """Um perfil oficial exercendo (ou ainda não) um papel na tipologia.

    `quantidade=None` e `orientacao=None` significam NÃO INFORMADO. Não são
    zero, não são vazio, e nenhum consumidor pode tratá-los como tal."""
    identificador: str
    perfil: ReferenciaPerfilOficial
    papel: PapelComponente = PapelComponente.NAO_CONFIRMADO
    quantidade: int | None = None
    orientacao: str | None = None
    folha: str | None = None
    posicao: str | None = None
    estado: EstadoConhecimento = EstadoConhecimento.PENDENTE
    fontes: tuple[FonteEvidencia, ...] = ()
    observacoes: tuple[str, ...] = ()

    def __post_init__(self):
        if self.quantidade is not None and self.quantidade <= 0:
            raise ReceitaErro(
                f"{self.identificador}: quantidade {self.quantidade!r} — "
                f"desconhecida é None, nunca 0")

    @property
    def confirmado(self) -> bool:
        """Confirmado de verdade: estado, papel, quantidade e orientação."""
        return (self.estado in ESTADOS_CONFIRMADOS
                and self.papel is not PapelComponente.NAO_CONFIRMADO
                and self.quantidade is not None
                and self.orientacao is not None)

    def pendencias(self) -> tuple[str, ...]:
        faltando = []
        if self.estado in ESTADOS_NAO_CALCULAVEIS:
            faltando.append(f"estado={self.estado.value}")
        if self.papel is PapelComponente.NAO_CONFIRMADO:
            faltando.append("papel não confirmado")
        if self.quantidade is None:
            faltando.append("quantidade não informada")
        if self.orientacao is None:
            faltando.append("orientação não informada")
        if not self.fontes and self.estado in ESTADOS_CONFIRMADOS:
            faltando.append("confirmado sem fonte")
        return tuple(faltando)

    def para_dict(self) -> dict:
        return {
            "identificador": self.identificador,
            "perfil": self.perfil.para_dict(),
            "papel": self.papel.value,
            "quantidade": self.quantidade,
            "orientacao": self.orientacao,
            "folha": self.folha,
            "posicao": self.posicao,
            "estado": self.estado.value,
            "fontes": [f.para_dict() for f in self.fontes],
            "observacoes": list(self.observacoes),
        }


# ---------------------------------------------------------------------------
# Regra dimensional
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegraDimensional:
    """O lugar reservado para uma fórmula que ainda NÃO existe.

    `expressao=None` com `estado=PENDENTE` é o estado correto de tudo o que
    depende de desconto de corte, folga, sobreposição ou medida de vidro."""
    identificador: str
    descricao: str
    alvo: str
    expressao: str | None = None
    variaveis: tuple[str, ...] = ()
    unidade: str = "mm"
    estado: EstadoConhecimento = EstadoConhecimento.PENDENTE
    fontes: tuple[FonteEvidencia, ...] = ()

    def __post_init__(self):
        if self.alvo not in ALVOS_DIMENSIONAIS:
            raise ReceitaErro(
                f"{self.identificador}: alvo desconhecido {self.alvo!r}")
        if self.estado in ESTADOS_CONFIRMADOS and not self.expressao:
            raise ReceitaErro(
                f"{self.identificador}: regra confirmada sem expressão")
        if self.estado in ESTADOS_CONFIRMADOS and not self.fontes:
            raise ReceitaErro(
                f"{self.identificador}: regra confirmada sem evidência")

    @property
    def calculavel(self) -> bool:
        return (self.estado in ESTADOS_CONFIRMADOS
                and bool(self.expressao) and bool(self.fontes))

    def para_dict(self) -> dict:
        return {"identificador": self.identificador,
                "descricao": self.descricao, "alvo": self.alvo,
                "expressao": self.expressao, "variaveis": list(self.variaveis),
                "unidade": self.unidade, "estado": self.estado.value,
                "fontes": [f.para_dict() for f in self.fontes]}


# ---------------------------------------------------------------------------
# Caso real de fabricação
# ---------------------------------------------------------------------------

ESTADO_CASO_AGUARDANDO = "AGUARDANDO_DADOS"
ESTADO_CASO_RECEBIDO = "RECEBIDO_NAO_VALIDADO"
ESTADO_CASO_VALIDADO = "VALIDADO"

IDENTIFICADORES_DE_CASO = ("CASO_A_PEQUENO", "CASO_B_MEDIO", "CASO_C_GRANDE")


@dataclass(frozen=True)
class CasoRealFabricacao:
    """Uma janela real, medida e fabricada — a única prova de que uma fórmula
    futura está certa.

    Medidas em `Decimal`: uma lista de corte é um documento de fabricação, e
    arredondamento binário de `float` não tem lugar nela."""
    identificador: str
    largura_total_mm: Decimal | None = None
    altura_total_mm: Decimal | None = None
    cortes: tuple = ()
    vidros: tuple = ()
    acessorios: tuple = ()
    croquis: tuple = ()
    fontes: tuple[FonteEvidencia, ...] = ()
    estado_validacao: str = ESTADO_CASO_AGUARDANDO

    def __post_init__(self):
        for campo in ("largura_total_mm", "altura_total_mm"):
            v = getattr(self, campo)
            if v is None:
                continue
            if not isinstance(v, Decimal):
                raise ReceitaErro(
                    f"{self.identificador}: {campo} tem de ser Decimal, "
                    f"recebido {type(v).__name__}")
            if v <= 0:
                raise ReceitaErro(
                    f"{self.identificador}: {campo}={v} — medida real é "
                    f"positiva; desconhecida é None")

    @property
    def tem_medidas(self) -> bool:
        return (self.largura_total_mm is not None
                and self.altura_total_mm is not None)

    def para_dict(self) -> dict:
        return {
            "identificador": self.identificador,
            "largura_total_mm": (str(self.largura_total_mm)
                                 if self.largura_total_mm is not None else None),
            "altura_total_mm": (str(self.altura_total_mm)
                                if self.altura_total_mm is not None else None),
            "cortes": len(self.cortes), "vidros": len(self.vidros),
            "acessorios": len(self.acessorios), "croquis": list(self.croquis),
            "estado_validacao": self.estado_validacao,
        }


# ---------------------------------------------------------------------------
# Receita da tipologia
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReceitaTipologia:
    """A tipologia inteira: componentes, regras e evidências.

    É um documento de conhecimento, não um programa. Enquanto o estado for
    `PRELIMINAR_AGUARDANDO_DADOS_DE_CAMPO`, ela não autoriza cálculo nem
    produção — só descreve o que já se sabe e o que falta perguntar."""
    codigo: str
    nome: str
    sistema: str
    quantidade_folhas: int
    componentes: tuple[ComponenteReceita, ...] = ()
    regras_corte: tuple[RegraDimensional, ...] = ()
    regras_vidro: tuple[RegraDimensional, ...] = ()
    regras_acessorios: tuple = ()
    casos_reais: tuple[CasoRealFabricacao, ...] = ()
    fontes: tuple[FonteEvidencia, ...] = ()
    estado: str = ESTADO_RECEITA_PRELIMINAR
    decisoes_do_especialista: tuple[str, ...] = ()
    perguntas_abertas: tuple[str, ...] = field(default=())

    @property
    def todas_as_regras(self) -> tuple[RegraDimensional, ...]:
        return tuple(self.regras_corte) + tuple(self.regras_vidro)

    @property
    def preliminar(self) -> bool:
        return self.estado == ESTADO_RECEITA_PRELIMINAR

    def componente(self, codigo_perfil: str) -> ComponenteReceita:
        for c in self.componentes:
            if c.perfil.codigo_perfil == codigo_perfil:
                return c
        raise ReceitaErro(f"{self.codigo}: sem componente para {codigo_perfil}")
