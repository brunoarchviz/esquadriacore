"""Modelos da receita de tipologia — E.4D.

O que esta camada é: um registro **auditável de conhecimento** sobre como uma
tipologia se monta. O que ela não é: um motor de cálculo. Nenhuma fórmula de
corte, vidro, folga ou sobreposição existe aqui, porque nenhuma foi confirmada.

A regra que governa tudo neste módulo: **valor desconhecido não vira informação**.
`None` significa "não informado" e nunca é lido como zero, como string vazia nem
como um default plausível; papel não confirmado é `NAO_CONFIRMADO`; regra sem
evidência fica `PENDENTE` com `expressao=None`. Um `0` — ou um
`CASO_A_PEQUENO` — no lugar de um desconhecido produziria um dado inventado com
aparência de resposta, e o erro só apareceria na serralheria.

Três palavras que **não** são sinônimas, e que o código mantém separadas:

```text
campo preenchido     alguém escreveu algo na ficha
decisão confirmada   estado confirmado + fonte + autoria quando é do especialista
regra aprovada       decisão confirmada + fórmula + conferida contra caso real
```
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class EstadoConhecimento(str, Enum):
    """De onde vem o que se afirma. Só os cinco primeiros autorizam cálculo."""
    CONFIRMADO_CATALOGO = "CONFIRMADO_CATALOGO"
    CONFIRMADO_BIBLIOTECA_OFICIAL = "CONFIRMADO_BIBLIOTECA_OFICIAL"
    CONFIRMADO_ESPECIALISTA = "CONFIRMADO_ESPECIALISTA"
    CONFIRMADO_CASO_REAL = "CONFIRMADO_CASO_REAL"
    DERIVADO_DE_REGRA_APROVADA = "DERIVADO_DE_REGRA_APROVADA"
    HIPOTESE = "HIPOTESE"
    PENDENTE = "PENDENTE"


ESTADOS_CONFIRMADOS = frozenset({
    EstadoConhecimento.CONFIRMADO_CATALOGO,
    EstadoConhecimento.CONFIRMADO_BIBLIOTECA_OFICIAL,
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


# `manifesto_promocao` e `biblioteca_oficial` descrevem o que o E.4C produziu.
# Chamá-lo de `catalogo` ou `tabela_de_fabricacao` criaria procedência
# enganosa: o manifesto prova que os perfis EXISTEM na biblioteca, não o que
# eles fazem numa janela.
TIPOS_DE_FONTE = frozenset({
    "catalogo", "medicao_fisica", "especialista_de_dominio",
    "lista_de_corte_real", "software_externo", "foto", "croqui",
    "tabela_de_fabricacao", "manifesto_promocao", "biblioteca_oficial",
})

# Como a `referencia` da fonte deve ser lida. A regra de caminho relativo vale
# só para arquivo: um DOI, um número de pedido ou uma URL não são caminhos.
FORMA_ARQUIVO = "arquivo"
FORMA_IDENTIFICADOR_EXTERNO = "identificador_externo"
FORMA_URL = "url"
FORMAS_DE_REFERENCIA = frozenset({FORMA_ARQUIVO, FORMA_IDENTIFICADOR_EXTERNO,
                                  FORMA_URL})

FORMATO_DATA = "AAAA-MM-DD"
_RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")

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

def _referencia_de_arquivo_insegura(referencia: str) -> str | None:
    """Motivo pelo qual o caminho é recusado, ou None se for aceitável.

    Recusa absoluto (Unix e Windows) e qualquer travessia por `..`. Um caminho
    absoluto amarra a evidência à máquina de quem registrou; um `..` aponta
    para fora do repositório, onde a evidência não sobrevive ao clone."""
    r = referencia.replace("\\", "/")
    if r.startswith("/"):
        return "caminho absoluto (Unix)"
    if re.match(r"^[A-Za-z]:[/\\]?", referencia):
        return "caminho absoluto (Windows)"
    if r.startswith("~"):
        return "caminho dependente do usuário"
    if ".." in [p for p in r.split("/")]:
        return "travessia para fora do repositório ('..')"
    return None


@dataclass(frozen=True)
class FonteEvidencia:
    """De onde veio a afirmação. Sem isto, `CONFIRMADO` seria só uma palavra."""
    tipo: str
    referencia: str
    descricao: str
    estado: EstadoConhecimento
    responsavel: str | None = None
    data: str | None = None
    forma_referencia: str = FORMA_ARQUIVO

    def __post_init__(self):
        if self.tipo not in TIPOS_DE_FONTE:
            raise ReceitaErro(
                f"tipo de fonte desconhecido: {self.tipo!r} "
                f"(conhecidos: {sorted(TIPOS_DE_FONTE)})")
        if self.forma_referencia not in FORMAS_DE_REFERENCIA:
            raise ReceitaErro(
                f"forma_referencia desconhecida: {self.forma_referencia!r} "
                f"(conhecidas: {sorted(FORMAS_DE_REFERENCIA)})")
        if not self.referencia:
            raise ReceitaErro(f"fonte {self.tipo}: referência vazia")
        if self.forma_referencia == FORMA_ARQUIVO:
            motivo = _referencia_de_arquivo_insegura(self.referencia)
            if motivo:
                raise ReceitaErro(
                    f"fonte {self.tipo}: {motivo} ({self.referencia!r}) — use "
                    f"caminho relativo à raiz do repo, ou declare "
                    f"forma_referencia={FORMA_IDENTIFICADOR_EXTERNO!r} / "
                    f"{FORMA_URL!r}")
        if self.data is not None and not _RE_DATA.fullmatch(self.data):
            raise ReceitaErro(
                f"fonte {self.tipo}: data {self.data!r} fora do formato "
                f"{FORMATO_DATA}")

    @property
    def tem_autoria(self) -> bool:
        return bool(self.responsavel and self.responsavel.strip())

    def para_dict(self) -> dict:
        return {"tipo": self.tipo, "referencia": self.referencia,
                "descricao": self.descricao, "estado": self.estado.value,
                "responsavel": self.responsavel, "data": self.data,
                "forma_referencia": self.forma_referencia}


def autoria_de_especialista_ausente(estado: EstadoConhecimento,
                                    fontes: tuple[FonteEvidencia, ...]) -> bool:
    """`CONFIRMADO_ESPECIALISTA` exige dizer QUEM confirmou, quando e onde.

    Vale para componente, regra dimensional, regra de acessório e aprovação
    final — uma decisão de domínio sem autor não pode ser auditada nem
    revogada."""
    if estado is not EstadoConhecimento.CONFIRMADO_ESPECIALISTA:
        return False
    return not any(f.tipo == "especialista_de_dominio" and f.tem_autoria
                   and f.data and f.referencia for f in fontes)


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
        """Confirmado de verdade: estado, papel, quantidade, orientação e —
        quando a decisão é do especialista — autoria registrada."""
        return (self.estado in ESTADOS_CONFIRMADOS
                and self.papel is not PapelComponente.NAO_CONFIRMADO
                and self.quantidade is not None
                and self.orientacao is not None
                and bool(self.fontes)
                and not autoria_de_especialista_ausente(self.estado, self.fontes))

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
        if autoria_de_especialista_ausente(self.estado, self.fontes):
            faltando.append("decisão de especialista sem autoria registrada")
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
# Regras
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
                and bool(self.expressao) and bool(self.fontes)
                and not autoria_de_especialista_ausente(self.estado, self.fontes))

    def para_dict(self) -> dict:
        return {"identificador": self.identificador,
                "descricao": self.descricao, "alvo": self.alvo,
                "expressao": self.expressao, "variaveis": list(self.variaveis),
                "unidade": self.unidade, "estado": self.estado.value,
                "fontes": [f.para_dict() for f in self.fontes]}


# Itens de acessório que uma correr de duas folhas precisa ter respondidos.
# Listar o item é registrar a PERGUNTA — não afirma modelo nem quantidade.
ITENS_DE_ACESSORIO = ("roldanas", "fecho", "contra_fecho", "escovas",
                      "vedacoes", "fixacoes")


@dataclass(frozen=True)
class RegraAcessorio:
    """Quantos acessórios entram e onde. Também sem fórmula por enquanto."""
    identificador: str
    item: str
    quantidade_expressao: str | None = None
    posicao: str | None = None
    estado: EstadoConhecimento = EstadoConhecimento.PENDENTE
    fontes: tuple[FonteEvidencia, ...] = ()

    def __post_init__(self):
        if not self.item:
            raise ReceitaErro(f"{self.identificador}: item vazio")
        if self.estado in ESTADOS_CONFIRMADOS:
            if not self.quantidade_expressao:
                raise ReceitaErro(
                    f"{self.identificador}: acessório confirmado sem "
                    f"quantidade")
            if not self.posicao:
                raise ReceitaErro(
                    f"{self.identificador}: acessório confirmado sem posição")
            if not self.fontes:
                raise ReceitaErro(
                    f"{self.identificador}: acessório confirmado sem evidência")

    @property
    def calculavel(self) -> bool:
        return (self.estado in ESTADOS_CONFIRMADOS
                and bool(self.quantidade_expressao) and bool(self.posicao)
                and bool(self.fontes)
                and not autoria_de_especialista_ausente(self.estado, self.fontes))

    def para_dict(self) -> dict:
        return {"identificador": self.identificador, "item": self.item,
                "quantidade_expressao": self.quantidade_expressao,
                "posicao": self.posicao, "estado": self.estado.value,
                "fontes": [f.para_dict() for f in self.fontes]}


# ---------------------------------------------------------------------------
# Caso real de fabricação — a ficha inteira, sem perder seção
# ---------------------------------------------------------------------------

ESTADO_CASO_AGUARDANDO = "AGUARDANDO_DADOS"
ESTADO_CASO_PARCIAL = "RECEBIDO_PARCIAL"
ESTADO_CASO_RECEBIDO = "RECEBIDO_NAO_VALIDADO"
ESTADO_CASO_VALIDADO = "VALIDADO"

IDENTIFICADORES_DE_CASO = ("CASO_A_PEQUENO", "CASO_B_MEDIO", "CASO_C_GRANDE")


@dataclass(frozen=True)
class VistaCasoReal:
    """Sem isto não há como saber o que é "esquerda" nem qual folha passa na
    frente. Todos os campos são opcionais e nenhum tem default de conteúdo."""
    lado_de_referencia: str | None = None
    folha_trilho_interno: str | None = None
    folha_trilho_externo: str | None = None
    sentidos_de_movimento: str | None = None
    posicao_do_fecho: str | None = None

    @property
    def vazia(self) -> bool:
        return not any((self.lado_de_referencia, self.folha_trilho_interno,
                        self.folha_trilho_externo, self.sentidos_de_movimento,
                        self.posicao_do_fecho))

    def para_dict(self) -> dict:
        return {"lado_de_referencia": self.lado_de_referencia,
                "folha_trilho_interno": self.folha_trilho_interno,
                "folha_trilho_externo": self.folha_trilho_externo,
                "sentidos_de_movimento": self.sentidos_de_movimento,
                "posicao_do_fecho": self.posicao_do_fecho}


@dataclass(frozen=True)
class PerfilNoCasoReal:
    """O que a ficha diz sobre um perfil. `funcao` chega como texto e só vira
    `PapelComponente` depois de validada — texto inválido não é convertido em
    palpite."""
    codigo_perfil: str
    funcao: PapelComponente | None = None
    quantidade: int | None = None
    orientacao: str | None = None
    observacoes: str | None = None
    fonte: str | None = None

    @property
    def vazio(self) -> bool:
        return not any((self.funcao, self.quantidade, self.orientacao,
                        self.observacoes, self.fonte))

    def para_dict(self) -> dict:
        return {"codigo_perfil": self.codigo_perfil,
                "funcao": self.funcao.value if self.funcao else None,
                "quantidade": self.quantidade, "orientacao": self.orientacao,
                "observacoes": self.observacoes, "fonte": self.fonte}


@dataclass(frozen=True)
class CorteReal:
    """Uma peça efetivamente cortada. É o dado do qual uma fórmula futura
    poderá ser DERIVADA — nunca o contrário."""
    perfil: str | None = None
    comprimento_mm: Decimal | None = None
    quantidade: int | None = None
    angulo: str | None = None
    observacao: str | None = None
    dados_adicionais: tuple = ()

    def para_dict(self) -> dict:
        return {"perfil": self.perfil,
                "comprimento_mm": (str(self.comprimento_mm)
                                   if self.comprimento_mm is not None else None),
                "quantidade": self.quantidade, "angulo": self.angulo,
                "observacao": self.observacao,
                "dados_adicionais": list(self.dados_adicionais)}


@dataclass(frozen=True)
class VidroReal:
    folha: str | None = None
    largura_mm: Decimal | None = None
    altura_mm: Decimal | None = None
    espessura_mm: Decimal | None = None
    observacao: str | None = None
    dados_adicionais: tuple = ()

    def para_dict(self) -> dict:
        return {"folha": self.folha,
                "largura_mm": str(self.largura_mm) if self.largura_mm is not None else None,
                "altura_mm": str(self.altura_mm) if self.altura_mm is not None else None,
                "espessura_mm": (str(self.espessura_mm)
                                 if self.espessura_mm is not None else None),
                "observacao": self.observacao,
                "dados_adicionais": list(self.dados_adicionais)}


@dataclass(frozen=True)
class BagueteReal:
    """A baguete Suprema tem DOIS lados de encaixe — qual encaixa em quê é
    parte do dado, não detalhe."""
    perfil: str | None = None
    comprimento_mm: Decimal | None = None
    quantidade: int | None = None
    lado_de_encaixe: str | None = None
    observacao: str | None = None
    dados_adicionais: tuple = ()

    def para_dict(self) -> dict:
        return {"perfil": self.perfil,
                "comprimento_mm": (str(self.comprimento_mm)
                                   if self.comprimento_mm is not None else None),
                "quantidade": self.quantidade,
                "lado_de_encaixe": self.lado_de_encaixe,
                "observacao": self.observacao,
                "dados_adicionais": list(self.dados_adicionais)}


@dataclass(frozen=True)
class AcessorioReal:
    item: str | None = None
    quantidade: int | None = None
    posicao: str | None = None
    observacao: str | None = None
    dados_adicionais: tuple = ()

    def para_dict(self) -> dict:
        return {"item": self.item, "quantidade": self.quantidade,
                "posicao": self.posicao, "observacao": self.observacao,
                "dados_adicionais": list(self.dados_adicionais)}


@dataclass(frozen=True)
class FolgaReal:
    entre: str | None = None
    valor_mm: Decimal | None = None
    medido_por: str | None = None
    observacao: str | None = None
    dados_adicionais: tuple = ()

    def para_dict(self) -> dict:
        return {"entre": self.entre,
                "valor_mm": str(self.valor_mm) if self.valor_mm is not None else None,
                "medido_por": self.medido_por, "observacao": self.observacao,
                "dados_adicionais": list(self.dados_adicionais)}


@dataclass(frozen=True)
class SobreposicaoReal:
    entre: str | None = None
    valor_mm: Decimal | None = None
    observacao: str | None = None
    dados_adicionais: tuple = ()

    def para_dict(self) -> dict:
        return {"entre": self.entre,
                "valor_mm": str(self.valor_mm) if self.valor_mm is not None else None,
                "observacao": self.observacao,
                "dados_adicionais": list(self.dados_adicionais)}


@dataclass(frozen=True)
class CasoRealFabricacao:
    """Uma janela real, medida e fabricada — a única prova de que uma fórmula
    futura está certa.

    `identificador=None` significa ficha ainda não identificada. Atribuir
    `CASO_A_PEQUENO` a uma ficha em branco seria inventar o dado que a ficha
    existe para coletar.

    Medidas em `Decimal`: uma lista de corte é documento de fabricação, e
    arredondamento binário de `float` não tem lugar nela.

    Guarda a ficha INTEIRA. Uma conversão que descartasse folgas, croquis ou
    dúvidas perderia exatamente o que foi caro de obter — a visita à
    serralheria."""
    identificador: str | None = None
    largura_total_mm: Decimal | None = None
    altura_total_mm: Decimal | None = None
    vista: VistaCasoReal = field(default_factory=VistaCasoReal)
    perfis: tuple[PerfilNoCasoReal, ...] = ()
    cortes: tuple[CorteReal, ...] = ()
    vidros: tuple[VidroReal, ...] = ()
    baguetes: tuple[BagueteReal, ...] = ()
    acessorios: tuple[AcessorioReal, ...] = ()
    folgas: tuple[FolgaReal, ...] = ()
    sobreposicoes: tuple[SobreposicaoReal, ...] = ()
    croquis: tuple = ()
    fontes: tuple[FonteEvidencia, ...] = ()
    duvidas: tuple[str, ...] = ()
    estado_validacao: str = ESTADO_CASO_AGUARDANDO

    def __post_init__(self):
        if (self.identificador is not None
                and self.identificador not in IDENTIFICADORES_DE_CASO):
            raise ReceitaErro(
                f"identificador de caso desconhecido: {self.identificador!r} "
                f"(conhecidos: {list(IDENTIFICADORES_DE_CASO)}; "
                f"não identificado é None)")
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

    @property
    def secoes_preenchidas(self) -> tuple[str, ...]:
        """Toda seção que trouxe informação — inclusive foto e dúvida.

        Uma ficha só com folgas medidas e fotos trouxe dado de campo real; não
        pode continuar classificada como `AGUARDANDO_DADOS`."""
        preenchidas = []
        if self.identificador:
            preenchidas.append("identificador")
        if self.largura_total_mm is not None:
            preenchidas.append("largura_total_mm")
        if self.altura_total_mm is not None:
            preenchidas.append("altura_total_mm")
        if not self.vista.vazia:
            preenchidas.append("vista")
        if any(not p.vazio for p in self.perfis):
            preenchidas.append("perfis")
        for nome in ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                     "sobreposicoes", "croquis", "fontes", "duvidas"):
            if getattr(self, nome):
                preenchidas.append(nome)
        return tuple(preenchidas)

    @property
    def completo_para_derivacao(self) -> bool:
        """Mínimo para tentar derivar qualquer fórmula: medidas do produto e a
        lista de corte real."""
        return bool(self.tem_medidas and self.cortes and self.vidros)

    def para_dict(self) -> dict:
        return {
            "identificador": self.identificador,
            "largura_total_mm": (str(self.largura_total_mm)
                                 if self.largura_total_mm is not None else None),
            "altura_total_mm": (str(self.altura_total_mm)
                                if self.altura_total_mm is not None else None),
            "vista": self.vista.para_dict(),
            "perfis": [p.para_dict() for p in self.perfis],
            "cortes": [c.para_dict() for c in self.cortes],
            "vidros": [v.para_dict() for v in self.vidros],
            "baguetes": [b.para_dict() for b in self.baguetes],
            "acessorios": [a.para_dict() for a in self.acessorios],
            "folgas": [f.para_dict() for f in self.folgas],
            "sobreposicoes": [s.para_dict() for s in self.sobreposicoes],
            "croquis": list(self.croquis),
            "fontes": [f.para_dict() for f in self.fontes],
            "duvidas": list(self.duvidas),
            "estado_validacao": self.estado_validacao,
            "secoes_preenchidas": list(self.secoes_preenchidas),
        }


# ---------------------------------------------------------------------------
# Aprovação do especialista
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AprovacaoEspecialista:
    """Aprovação com autor, data, escopo e evidência.

    Uma string solta em `decisoes_do_especialista` não diz quem aprovou o quê,
    nem permite revogar depois. Produção é a única porta que libera corte de
    alumínio: ela exige assinatura, não anotação."""
    decisao: str
    responsavel: str
    data: str
    fonte: FonteEvidencia
    escopo: str

    def __post_init__(self):
        for campo in ("decisao", "responsavel", "data", "escopo"):
            if not str(getattr(self, campo) or "").strip():
                raise ReceitaErro(f"aprovação sem {campo}")
        if not _RE_DATA.fullmatch(self.data):
            raise ReceitaErro(
                f"aprovação: data {self.data!r} fora do formato {FORMATO_DATA}")
        if not self.fonte.tem_autoria:
            raise ReceitaErro("aprovação com fonte sem responsável")

    def para_dict(self) -> dict:
        return {"decisao": self.decisao, "responsavel": self.responsavel,
                "data": self.data, "escopo": self.escopo,
                "fonte": self.fonte.para_dict()}


ESCOPO_APROVACAO_RECEITA = "receita"
ESCOPO_APROVACAO_FORMULAS = "formulas"


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
    regras_acessorios: tuple[RegraAcessorio, ...] = ()
    casos_reais: tuple[CasoRealFabricacao, ...] = ()
    fontes: tuple[FonteEvidencia, ...] = ()
    estado: str = ESTADO_RECEITA_PRELIMINAR
    aprovacoes: tuple[AprovacaoEspecialista, ...] = ()
    perguntas_abertas: tuple[str, ...] = ()

    @property
    def regras_dimensionais(self) -> tuple[RegraDimensional, ...]:
        return tuple(self.regras_corte) + tuple(self.regras_vidro)

    @property
    def todas_as_regras(self) -> tuple:
        """Dimensionais **e** de acessório.

        Deixar acessórios de fora daria um gate de cálculo que abre sem saber
        quantas roldanas a janela leva."""
        return self.regras_dimensionais + tuple(self.regras_acessorios)

    @property
    def preliminar(self) -> bool:
        return self.estado == ESTADO_RECEITA_PRELIMINAR

    def componente(self, codigo_perfil: str) -> ComponenteReceita:
        for c in self.componentes:
            if c.perfil.codigo_perfil == codigo_perfil:
                return c
        raise ReceitaErro(f"{self.codigo}: sem componente para {codigo_perfil}")

    def aprovacao(self, escopo: str) -> AprovacaoEspecialista | None:
        for a in self.aprovacoes:
            if a.escopo == escopo:
                return a
        return None
