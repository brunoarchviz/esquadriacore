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

Quatro palavras que **não** são sinônimas, e que o código mantém separadas:

```text
campo preenchido     alguém escreveu algo na ficha
decisão confirmada   estado confirmado + fontes existentes + autoria quando é
                     do especialista
regra aprovada       decisão confirmada + fórmula + evidência
caso validado        registro estruturado de validação com resultado APROVADO
```

Evidência é citada por **ID**, nunca por tipo: duas fotos são duas fontes
distintas, e um índice por tipo faria a segunda apagar a primeira.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from types import MappingProxyType


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


class ResultadoAprovacao(str, Enum):
    """O que o especialista decidiu. `REPROVADO` nunca é aprovação.

    Sem isto, uma aprovação era só a existência de um registro — e um parecer
    negativo abriria o mesmo portão que um positivo."""
    APROVADO = "APROVADO"
    REPROVADO = "REPROVADO"
    REVOGADO = "REVOGADO"


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

# Identidade da evidência. Duas fotos da mesma janela são duas fontes; um
# índice por `tipo` faria a segunda sobrescrever a primeira em silêncio.
FORMATO_ID_FONTE = "FONTE-[A-Z0-9_-]+"
_RE_ID_FONTE = re.compile(r"FONTE-[A-Z0-9_-]+")

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

# Que TIPO de evidência sustenta que TIPO de confirmação. Não é uma escala
# numérica: cada confirmação tem natureza própria. Uma foto não confirma cota
# de catálogo, e um catálogo não confirma o que foi medido numa janela real.
TIPOS_QUE_SUSTENTAM = {
    EstadoConhecimento.CONFIRMADO_CATALOGO: frozenset({
        "catalogo", "tabela_de_fabricacao"}),
    EstadoConhecimento.CONFIRMADO_BIBLIOTECA_OFICIAL: frozenset({
        "manifesto_promocao", "biblioteca_oficial"}),
    EstadoConhecimento.CONFIRMADO_ESPECIALISTA: frozenset({
        "especialista_de_dominio"}),
    EstadoConhecimento.CONFIRMADO_CASO_REAL: frozenset({
        "medicao_fisica", "foto", "croqui", "lista_de_corte_real",
        "software_externo", "tabela_de_fabricacao"}),
    EstadoConhecimento.DERIVADO_DE_REGRA_APROVADA: frozenset({
        "especialista_de_dominio", "tabela_de_fabricacao", "software_externo"}),
}


# ---------------------------------------------------------------------------
# Imutabilidade profunda
# ---------------------------------------------------------------------------

def congelar_dados_adicionais(valor):
    """Cópia profundamente imutável do conteúdo livre.

    `frozen=True` congela os ATRIBUTOS do dataclass, não o conteúdo de um
    `dict`. Sem isto, quem passou o dicionário continuaria podendo alterá-lo
    depois — e o "registro auditável" mudaria por baixo de quem o leu."""
    if isinstance(valor, Mapping):
        return MappingProxyType({str(k): congelar_dados_adicionais(v)
                                 for k, v in valor.items()})
    if isinstance(valor, (list, tuple)):
        return tuple(congelar_dados_adicionais(v) for v in valor)
    if isinstance(valor, (set, frozenset)):
        return frozenset(congelar_dados_adicionais(v) for v in valor)
    return valor


def descongelar_dados_adicionais(valor):
    """Cópia nova e mutável, para serializar. Mexer nela não afeta o modelo."""
    if isinstance(valor, Mapping):
        return {k: descongelar_dados_adicionais(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [descongelar_dados_adicionais(v) for v in valor]
    if isinstance(valor, (set, frozenset)):
        return sorted(descongelar_dados_adicionais(v) for v in valor)
    return valor


def data_invalida(valor: str) -> str | None:
    """Motivo pelo qual a data é inválida, ou None se for uma data real.

    Conferir só o formato aceitaria `2026-02-30` — que parece uma data e não
    é. Uma evidência datada num dia inexistente não pode ser auditada."""
    if not _RE_DATA.fullmatch(valor or ""):
        return f"fora do formato {FORMATO_DATA}"
    try:
        date.fromisoformat(valor)
    except ValueError:
        return "não é uma data real do calendário"
    return None


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
    """De onde veio a afirmação. Sem isto, `CONFIRMADO` seria só uma palavra.

    `id_fonte` é obrigatório e único. Citar evidência por `tipo` era ambíguo:
    com duas fontes `especialista_de_dominio`, a afirmação não dizia a qual das
    duas se referia — e o índice por tipo escolhia uma delas em silêncio."""
    id_fonte: str
    tipo: str
    referencia: str
    descricao: str
    estado: EstadoConhecimento
    responsavel: str | None = None
    data: str | None = None
    forma_referencia: str = FORMA_ARQUIVO

    def __post_init__(self):
        if not _RE_ID_FONTE.fullmatch(self.id_fonte or ""):
            raise ReceitaErro(
                f"id_fonte inválido: {self.id_fonte!r} — esperado "
                f"{FORMATO_ID_FONTE}. Fonte sem identificação não recebe ID "
                f"automático: duas fontes iguais ficariam indistinguíveis.")
        if self.tipo not in TIPOS_DE_FONTE:
            raise ReceitaErro(
                f"{self.id_fonte}: tipo de fonte desconhecido: {self.tipo!r} "
                f"(conhecidos: {sorted(TIPOS_DE_FONTE)})")
        if self.forma_referencia not in FORMAS_DE_REFERENCIA:
            raise ReceitaErro(
                f"{self.id_fonte}: forma_referencia desconhecida: "
                f"{self.forma_referencia!r} "
                f"(conhecidas: {sorted(FORMAS_DE_REFERENCIA)})")
        if not self.referencia:
            raise ReceitaErro(f"{self.id_fonte}: referência vazia")
        if self.forma_referencia == FORMA_ARQUIVO:
            motivo = _referencia_de_arquivo_insegura(self.referencia)
            if motivo:
                raise ReceitaErro(
                    f"{self.id_fonte}: {motivo} ({self.referencia!r}) — use "
                    f"caminho relativo à raiz do repo, ou declare "
                    f"forma_referencia={FORMA_IDENTIFICADOR_EXTERNO!r} / "
                    f"{FORMA_URL!r}")
        if self.data is not None:
            motivo = data_invalida(self.data)
            if motivo:
                raise ReceitaErro(
                    f"{self.id_fonte}: data {self.data!r} {motivo}")

    @property
    def tem_autoria(self) -> bool:
        return bool(self.responsavel and self.responsavel.strip())

    @property
    def autoria_completa(self) -> bool:
        """Autoria auditável: quem, quando e onde."""
        return bool(self.tem_autoria and self.data and self.referencia)

    def para_dict(self) -> dict:
        return {"id_fonte": self.id_fonte, "tipo": self.tipo,
                "referencia": self.referencia,
                "descricao": self.descricao, "estado": self.estado.value,
                "responsavel": self.responsavel, "data": self.data,
                "forma_referencia": self.forma_referencia}


def indexar_fontes(fontes) -> dict:
    """`id_fonte` -> fonte. Recusa IDs repetidos.

    Um índice por tipo perderia a segunda fonte do mesmo tipo; por ID, duas
    fotos continuam sendo duas fotos."""
    indice = {}
    for f in fontes:
        if f.id_fonte in indice:
            raise ReceitaErro(f"id_fonte duplicado: {f.id_fonte}")
        indice[f.id_fonte] = f
    return indice


def autoria_de_especialista_ausente(estado: EstadoConhecimento,
                                    fontes: tuple[FonteEvidencia, ...]) -> bool:
    """`CONFIRMADO_ESPECIALISTA` exige dizer QUEM confirmou, quando e onde.

    Vale para componente, regra dimensional, regra de acessório e aprovação
    final — uma decisão de domínio sem autor não pode ser auditada nem
    revogada."""
    if estado is not EstadoConhecimento.CONFIRMADO_ESPECIALISTA:
        return False
    return not any(f.tipo == "especialista_de_dominio" and f.autoria_completa
                   for f in fontes)


def fonte_compativel_com_afirmacao(fonte: FonteEvidencia,
                                   estado_afirmacao: EstadoConhecimento) -> bool:
    """A fonte sustenta ESTE tipo de confirmação?

    Existir não basta. Uma fonte `PENDENTE` confirmando um
    `CONFIRMADO_CASO_REAL` seria uma afirmação firme apoiada em nada — e o
    sistema diria que a janela foi medida quando ninguém mediu."""
    if estado_afirmacao not in ESTADOS_CONFIRMADOS:
        return False
    if fonte.estado is not estado_afirmacao:
        return False
    if fonte.tipo not in TIPOS_QUE_SUSTENTAM[estado_afirmacao]:
        return False
    if estado_afirmacao is EstadoConhecimento.CONFIRMADO_ESPECIALISTA:
        return fonte.autoria_completa
    return True


def incompatibilidades_da_afirmacao(estado, fontes_ids, indice_fontes) -> tuple[str, ...]:
    """Motivos pelos quais a evidência citada NÃO sustenta a afirmação.

    Devolve texto, não booleano: uma afirmação confirmada com fonte incompatível
    tem de virar erro visível, não sumir em silêncio da lista de confirmações."""
    if estado is None:
        return ("afirmação sem estado",)
    if estado in ESTADOS_NAO_CALCULAVEIS:
        return (f"estado {estado.value} não confirma",)
    if estado not in ESTADOS_CONFIRMADOS:
        return (f"estado desconhecido: {estado}",)

    ids = tuple(fontes_ids or ())
    if not ids:
        return ("afirmação confirmada sem fontes_ids",)
    problemas = []
    vistos = set()
    for i in ids:
        if i in vistos:
            problemas.append(f"fonte repetida na mesma afirmação: {i}")
        vistos.add(i)
        if i not in indice_fontes:
            problemas.append(f"fonte inexistente: {i}")
    if problemas:
        return tuple(problemas)

    fontes = tuple(indice_fontes[i] for i in ids)
    for f in fontes:
        if f.estado in ESTADOS_NAO_CALCULAVEIS:
            problemas.append(
                f"{f.id_fonte} está {f.estado.value} e não sustenta confirmação")
    if not any(fonte_compativel_com_afirmacao(f, estado) for f in fontes):
        esperado = sorted(TIPOS_QUE_SUSTENTAM[estado])
        problemas.append(
            f"nenhuma fonte compatível com {estado.value} "
            f"(esperado estado {estado.value} e tipo em {esperado}"
            + (" com autoria completa"
               if estado is EstadoConhecimento.CONFIRMADO_ESPECIALISTA else "")
            + ")")
    return tuple(problemas)


def afirmacao_confirmada(estado, fontes_ids, indice_fontes) -> bool:
    """Uma afirmação só é confirmada com estado, evidência existente, apta e
    semanticamente compatível.

    Uma fonte global no documento não confirma seção nenhuma: a evidência tem
    de estar ligada à afirmação específica — e sustentá-la."""
    return not incompatibilidades_da_afirmacao(estado, fontes_ids,
                                               indice_fontes)


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
# Caso real de fabricação — cada afirmação com seu próprio estado e evidência
# ---------------------------------------------------------------------------

ESTADO_CASO_AGUARDANDO = "AGUARDANDO_DADOS"
ESTADO_CASO_PARCIAL = "RECEBIDO_PARCIAL"
ESTADO_CASO_RECEBIDO = "RECEBIDO_NAO_VALIDADO"
ESTADO_CASO_VALIDADO = "VALIDADO"

ESTADOS_DE_RECEBIMENTO = (ESTADO_CASO_AGUARDANDO, ESTADO_CASO_PARCIAL,
                          ESTADO_CASO_RECEBIDO)

IDENTIFICADORES_DE_CASO = ("CASO_A_PEQUENO", "CASO_B_MEDIO", "CASO_C_GRANDE")


@dataclass(frozen=True)
class Afirmacao:
    """Base das afirmações da ficha: estado, evidência e extensão explícita.

    `dados_adicionais` é o ÚNICO lugar onde conteúdo livre é aceito. Fora dele,
    campo desconhecido reprova — senão um erro de digitação viraria dado
    perdido, e a ficha pareceria completa."""
    estado: EstadoConhecimento | None = None
    fontes_ids: tuple[str, ...] = ()
    dados_adicionais: Mapping = field(default_factory=dict)

    def __post_init__(self):
        # Cópia profunda e congelada: quem passou o dicionário não pode mais
        # alterá-lo por fora depois que o registro foi criado.
        object.__setattr__(self, "dados_adicionais",
                           congelar_dados_adicionais(self.dados_adicionais))
        object.__setattr__(self, "fontes_ids", tuple(self.fontes_ids or ()))

    def confirmada(self, indice_fontes) -> bool:
        return afirmacao_confirmada(self.estado, self.fontes_ids, indice_fontes)

    def incompatibilidades(self, indice_fontes) -> tuple[str, ...]:
        return incompatibilidades_da_afirmacao(self.estado, self.fontes_ids,
                                               indice_fontes)

    def _base_dict(self) -> dict:
        return {"estado": self.estado.value if self.estado else None,
                "fontes_ids": list(self.fontes_ids),
                "dados_adicionais": descongelar_dados_adicionais(
                    self.dados_adicionais),
                "dados_adicionais_interpretados": False}


@dataclass(frozen=True)
class VistaCasoReal(Afirmacao):
    """Sem isto não há como saber o que é "esquerda" nem qual folha passa na
    frente. Todos os campos são opcionais e nenhum tem default de conteúdo."""
    lado_de_referencia: str | None = None
    folha_trilho_interno: str | None = None
    folha_trilho_externo: str | None = None
    sentidos_de_movimento: str | None = None
    posicao_do_fecho: str | None = None

    CAMPOS = ("lado_de_referencia", "folha_trilho_interno",
              "folha_trilho_externo", "sentidos_de_movimento",
              "posicao_do_fecho")

    @property
    def vazia(self) -> bool:
        return not any(getattr(self, c) for c in self.CAMPOS) \
            and not self.dados_adicionais

    def para_dict(self) -> dict:
        d = {c: getattr(self, c) for c in self.CAMPOS}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class PerfilNoCasoReal(Afirmacao):
    """O que a ficha diz sobre um perfil. `funcao` chega como texto e só vira
    `PapelComponente` depois de validada — texto inválido não é convertido em
    palpite."""
    codigo_perfil: str = ""
    funcao: PapelComponente | None = None
    quantidade: int | None = None
    orientacao: str | None = None
    observacoes: str | None = None

    CAMPOS = ("funcao", "quantidade", "orientacao", "observacoes")

    @property
    def vazio(self) -> bool:
        return not any(getattr(self, c) for c in self.CAMPOS) \
            and not self.fontes_ids and not self.dados_adicionais

    def para_dict(self) -> dict:
        d = {"codigo_perfil": self.codigo_perfil,
             "funcao": self.funcao.value if self.funcao else None,
             "quantidade": self.quantidade, "orientacao": self.orientacao,
             "observacoes": self.observacoes}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class CorteReal(Afirmacao):
    """Uma peça efetivamente cortada. É o dado do qual uma fórmula futura
    poderá ser DERIVADA — nunca o contrário."""
    perfil: str | None = None
    comprimento_mm: Decimal | None = None
    quantidade: int | None = None
    angulo: str | None = None
    observacao: str | None = None

    def para_dict(self) -> dict:
        d = {"perfil": self.perfil,
             "comprimento_mm": (str(self.comprimento_mm)
                                if self.comprimento_mm is not None else None),
             "quantidade": self.quantidade, "angulo": self.angulo,
             "observacao": self.observacao}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class VidroReal(Afirmacao):
    folha: str | None = None
    largura_mm: Decimal | None = None
    altura_mm: Decimal | None = None
    espessura_mm: Decimal | None = None
    observacao: str | None = None

    def para_dict(self) -> dict:
        d = {"folha": self.folha,
             "largura_mm": str(self.largura_mm) if self.largura_mm is not None else None,
             "altura_mm": str(self.altura_mm) if self.altura_mm is not None else None,
             "espessura_mm": (str(self.espessura_mm)
                              if self.espessura_mm is not None else None),
             "observacao": self.observacao}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class BagueteReal(Afirmacao):
    """A baguete Suprema tem DOIS lados de encaixe — qual encaixa em quê é
    parte do dado, não detalhe."""
    perfil: str | None = None
    comprimento_mm: Decimal | None = None
    quantidade: int | None = None
    lado_de_encaixe: str | None = None
    observacao: str | None = None

    def para_dict(self) -> dict:
        d = {"perfil": self.perfil,
             "comprimento_mm": (str(self.comprimento_mm)
                                if self.comprimento_mm is not None else None),
             "quantidade": self.quantidade,
             "lado_de_encaixe": self.lado_de_encaixe,
             "observacao": self.observacao}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class AcessorioReal(Afirmacao):
    item: str | None = None
    quantidade: int | None = None
    posicao: str | None = None
    observacao: str | None = None

    def para_dict(self) -> dict:
        d = {"item": self.item, "quantidade": self.quantidade,
             "posicao": self.posicao, "observacao": self.observacao}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class FolgaReal(Afirmacao):
    entre: str | None = None
    valor_mm: Decimal | None = None
    medido_por: str | None = None
    observacao: str | None = None

    def para_dict(self) -> dict:
        d = {"entre": self.entre,
             "valor_mm": str(self.valor_mm) if self.valor_mm is not None else None,
             "medido_por": self.medido_por, "observacao": self.observacao}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class SobreposicaoReal(Afirmacao):
    entre: str | None = None
    valor_mm: Decimal | None = None
    observacao: str | None = None

    def para_dict(self) -> dict:
        d = {"entre": self.entre,
             "valor_mm": str(self.valor_mm) if self.valor_mm is not None else None,
             "observacao": self.observacao}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class CroquiCasoReal:
    """Evidência visual, não decisão dimensional.

    Croqui é matéria-prima de fonte: ele vira uma `FonteEvidencia` própria (com
    `id_fonte`) quando alguém quiser citá-lo. Por isso não carrega `estado` nem
    `responsavel` — duas representações do mesmo fato entrariam em conflito."""
    tipo: str | None = None
    referencia: str | None = None
    descricao: str | None = None

    def para_dict(self) -> dict:
        return {"tipo": self.tipo, "referencia": self.referencia,
                "descricao": self.descricao}


@dataclass(frozen=True)
class ValidacaoCasoReal:
    """Registro estruturado de que alguém conferiu o caso e o aceitou.

    Antes, `estado_validacao="VALIDADO"` era uma string que qualquer código
    podia escrever — e o gate de produção acreditava. Validar é um ato com
    autor, data e evidência."""
    resultado: ResultadoAprovacao
    responsavel: str
    data: str
    fontes_ids: tuple[str, ...] = ()
    observacao: str | None = None

    def __post_init__(self):
        if not isinstance(self.resultado, ResultadoAprovacao):
            raise ReceitaErro(
                f"validação com resultado inválido: {self.resultado!r}")
        if not str(self.responsavel or "").strip():
            raise ReceitaErro("validação de caso sem responsável")
        motivo = data_invalida(self.data or "")
        if motivo:
            raise ReceitaErro(f"validação de caso: data {self.data!r} {motivo}")
        if not self.fontes_ids:
            raise ReceitaErro("validação de caso sem fontes")
        if len(set(self.fontes_ids)) != len(self.fontes_ids):
            raise ReceitaErro(
                f"validação de caso com fonte repetida: {self.fontes_ids}")

    @property
    def aprovada(self) -> bool:
        return self.resultado is ResultadoAprovacao.APROVADO

    def para_dict(self) -> dict:
        return {"resultado": self.resultado.value,
                "responsavel": self.responsavel, "data": self.data,
                "fontes_ids": list(self.fontes_ids),
                "observacao": self.observacao}


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
    estado_dimensoes: EstadoConhecimento | None = None
    fontes_ids_dimensoes: tuple[str, ...] = ()
    vista: VistaCasoReal = field(default_factory=VistaCasoReal)
    perfis: tuple[PerfilNoCasoReal, ...] = ()
    cortes: tuple[CorteReal, ...] = ()
    vidros: tuple[VidroReal, ...] = ()
    baguetes: tuple[BagueteReal, ...] = ()
    acessorios: tuple[AcessorioReal, ...] = ()
    folgas: tuple[FolgaReal, ...] = ()
    sobreposicoes: tuple[SobreposicaoReal, ...] = ()
    croquis: tuple[CroquiCasoReal, ...] = ()
    fontes: tuple[FonteEvidencia, ...] = ()
    duvidas: tuple[str, ...] = ()
    dados_adicionais: Mapping = field(default_factory=dict)
    estado_recebimento: str = ESTADO_CASO_AGUARDANDO
    validacao: ValidacaoCasoReal | None = None

    def __post_init__(self):
        object.__setattr__(self, "dados_adicionais",
                           congelar_dados_adicionais(self.dados_adicionais))
        if (self.identificador is not None
                and self.identificador not in IDENTIFICADORES_DE_CASO):
            raise ReceitaErro(
                f"identificador de caso desconhecido: {self.identificador!r} "
                f"(conhecidos: {list(IDENTIFICADORES_DE_CASO)}; "
                f"não identificado é None)")
        if self.estado_recebimento not in ESTADOS_DE_RECEBIMENTO:
            raise ReceitaErro(
                f"estado_recebimento inválido: {self.estado_recebimento!r} "
                f"(conhecidos: {list(ESTADOS_DE_RECEBIMENTO)}). "
                f"'{ESTADO_CASO_VALIDADO}' NÃO se escreve: é derivado de uma "
                f"ValidacaoCasoReal aprovada.")
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
        try:
            indexar_fontes(self.fontes)
        except ReceitaErro as e:
            raise ReceitaErro(f"{self.identificador}: {e}") from e

    @property
    def indice_fontes(self) -> dict:
        return {f.id_fonte: f for f in self.fontes}

    @property
    def estado_validacao(self) -> str:
        """`VALIDADO` só existe com registro estruturado aprovado."""
        if self.validacao is not None and self.validacao.aprovada:
            return ESTADO_CASO_VALIDADO
        return self.estado_recebimento

    @property
    def validado(self) -> bool:
        return self.estado_validacao == ESTADO_CASO_VALIDADO

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
        if self.dados_adicionais:
            preenchidas.append("dados_adicionais")
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
            "estado_dimensoes": (self.estado_dimensoes.value
                                 if self.estado_dimensoes else None),
            "fontes_ids_dimensoes": list(self.fontes_ids_dimensoes),
            "vista": self.vista.para_dict(),
            "perfis": [p.para_dict() for p in self.perfis],
            "cortes": [c.para_dict() for c in self.cortes],
            "vidros": [v.para_dict() for v in self.vidros],
            "baguetes": [b.para_dict() for b in self.baguetes],
            "acessorios": [a.para_dict() for a in self.acessorios],
            "folgas": [f.para_dict() for f in self.folgas],
            "sobreposicoes": [s.para_dict() for s in self.sobreposicoes],
            "croquis": [c.para_dict() for c in self.croquis],
            "fontes": [f.para_dict() for f in self.fontes],
            "duvidas": list(self.duvidas),
            "dados_adicionais": descongelar_dados_adicionais(
                self.dados_adicionais),
            "dados_adicionais_interpretados": False,
            "estado_recebimento": self.estado_recebimento,
            "estado_validacao": self.estado_validacao,
            "validacao": self.validacao.para_dict() if self.validacao else None,
            "secoes_preenchidas": list(self.secoes_preenchidas),
        }


# ---------------------------------------------------------------------------
# Aprovação do especialista
# ---------------------------------------------------------------------------

ESCOPO_APROVACAO_RECEITA = "receita"
ESCOPO_APROVACAO_FORMULAS = "formulas"
ESCOPOS_DE_APROVACAO = (ESCOPO_APROVACAO_RECEITA, ESCOPO_APROVACAO_FORMULAS)


@dataclass(frozen=True)
class AprovacaoEspecialista:
    """Aprovação com resultado, autor, data, escopo e evidência **registrada**.

    `resultado` é um enum, não texto livre: antes, a mera existência de um
    registro abria o portão, e um parecer NEGATIVO abriria o mesmo portão que
    um positivo.

    A evidência é citada por `fonte_id`, resolvido no registro central da
    receita. Carregar o objeto `FonteEvidencia` aqui permitia aprovar com uma
    fonte que não existe em lugar nenhum — evidência que ninguém consegue
    auditar depois."""
    resultado: ResultadoAprovacao
    responsavel: str
    data: str
    fonte_id: str
    escopo: str
    observacao: str | None = None

    def __post_init__(self):
        if not isinstance(self.resultado, ResultadoAprovacao):
            raise ReceitaErro(f"aprovação com resultado inválido: "
                              f"{self.resultado!r}")
        for campo in ("responsavel", "data", "fonte_id", "escopo"):
            if not str(getattr(self, campo) or "").strip():
                raise ReceitaErro(f"aprovação sem {campo}")
        if self.escopo not in ESCOPOS_DE_APROVACAO:
            raise ReceitaErro(
                f"escopo de aprovação desconhecido: {self.escopo!r} "
                f"(conhecidos: {list(ESCOPOS_DE_APROVACAO)})")
        if not _RE_ID_FONTE.fullmatch(self.fonte_id):
            raise ReceitaErro(
                f"aprovação com fonte_id fora do formato: {self.fonte_id!r} "
                f"(esperado {FORMATO_ID_FONTE})")
        motivo = data_invalida(self.data)
        if motivo:
            raise ReceitaErro(f"aprovação: data {self.data!r} {motivo}")

    @property
    def aprovada(self) -> bool:
        return self.resultado is ResultadoAprovacao.APROVADO

    def para_dict(self) -> dict:
        return {"resultado": self.resultado.value,
                "responsavel": self.responsavel,
                "data": self.data, "escopo": self.escopo,
                "observacao": self.observacao,
                "fonte_id": self.fonte_id}


def problemas_da_fonte_de_aprovacao(aprovacao: "AprovacaoEspecialista",
                                    indice: dict) -> tuple[str, ...]:
    """A evidência citada existe, é de especialista, está confirmada e bate.

    Aprovar é o ato que libera corte de alumínio: a assinatura, a data e a
    evidência têm de contar a mesma história."""
    fonte = indice.get(aprovacao.fonte_id)
    if fonte is None:
        return (f"fonte {aprovacao.fonte_id} não está registrada na receita",)
    problemas = []
    if fonte.tipo != "especialista_de_dominio":
        problemas.append(
            f"fonte {fonte.id_fonte} é {fonte.tipo!r} — aprovação final é "
            f"decisão de domínio e exige especialista_de_dominio")
    if fonte.estado is not EstadoConhecimento.CONFIRMADO_ESPECIALISTA:
        problemas.append(
            f"fonte {fonte.id_fonte} está {fonte.estado.value}, não "
            f"CONFIRMADO_ESPECIALISTA")
    if not fonte.autoria_completa:
        problemas.append(f"fonte {fonte.id_fonte} sem autoria completa")
    elif fonte.responsavel.strip() != aprovacao.responsavel.strip():
        problemas.append(
            f"aprovação assinada por {aprovacao.responsavel!r} com evidência "
            f"de {fonte.responsavel!r} — assinatura e evidência têm de ser da "
            f"mesma pessoa")
    if fonte.data and fonte.data != aprovacao.data:
        problemas.append(
            f"aprovação datada em {aprovacao.data} com evidência de "
            f"{fonte.data} — datas divergentes")
    return tuple(problemas)


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


def indice_fontes_receita(receita: ReceitaTipologia) -> dict:
    """Todas as fontes da receita por ID — determinístico e sem colisão.

    Varre receita, componentes, regras e casos. Dois registros com o mesmo ID e
    conteúdo diferente reprovam: seria a mesma evidência dizendo duas coisas."""
    indice: dict = {}
    grupos = [receita.fontes]
    grupos += [c.fontes for c in receita.componentes]
    grupos += [r.fontes for r in receita.todas_as_regras]
    grupos += [c.fontes for c in receita.casos_reais]
    for grupo in grupos:
        for f in grupo:
            anterior = indice.get(f.id_fonte)
            if anterior is not None and anterior != f:
                raise ReceitaErro(
                    f"id_fonte {f.id_fonte} usado por duas fontes diferentes — "
                    f"a mesma evidência não pode dizer duas coisas")
            indice[f.id_fonte] = f
    return indice


def aprovacoes_por_escopo(receita: ReceitaTipologia,
                          escopo: str) -> tuple[AprovacaoEspecialista, ...]:
    """TODAS as aprovações daquele escopo — nunca só a primeira.

    Devolver a primeira encontrada esconderia um segundo parecer conflitante, e
    a ordem da tupla decidiria se a produção abre."""
    return tuple(a for a in receita.aprovacoes if a.escopo == escopo)
