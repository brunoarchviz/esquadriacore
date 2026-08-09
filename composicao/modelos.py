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
    # Papel lateral NEUTRO. Gravar esquerda/direita como identidade da receita
    # impediria espelhar a janela sem trocar a tipologia — a lateralidade é
    # configuração de uma instância, não da receita técnica.
    MARCO_LATERAL = "MARCO_LATERAL"
    # Preservados por compatibilidade: receitas anteriores podem usá-los.
    MARCO_LATERAL_ESQUERDO = "MARCO_LATERAL_ESQUERDO"
    MARCO_LATERAL_DIREITO = "MARCO_LATERAL_DIREITO"
    TRAVESSA_SUPERIOR_FOLHA = "TRAVESSA_SUPERIOR_FOLHA"
    TRAVESSA_INFERIOR_FOLHA = "TRAVESSA_INFERIOR_FOLHA"
    MONTANTE_LATERAL_FOLHA = "MONTANTE_LATERAL_FOLHA"
    # Posição estrutural do montante que fica no centro da folha. É o papel do
    # perfil "mão de amigo" — que é montante, não ferragem.
    MONTANTE_CENTRAL_FOLHA = "MONTANTE_CENTRAL_FOLHA"
    # Preservado por compatibilidade. NÃO usar para o encontro central da
    # Suprema 2F: lá o encontro é uma RELAÇÃO entre duas peças de folhas
    # diferentes, não o papel de uma peça (ver RelacaoEntreComponentes).
    ENCONTRO_CENTRAL = "ENCONTRO_CENTRAL"
    MAO_DE_AMIGO = "MAO_DE_AMIGO"
    BAGUETE = "BAGUETE"
    NAO_CONFIRMADO = "NAO_CONFIRMADO"


# Papéis que descrevem o quadro fixo, não a folha móvel. Serve para separar,
# na contagem, o que é estrutura de esquadria do que é acabamento do vidro.
PAPEIS_DE_QUADRO = frozenset({
    PapelComponente.MARCO_SUPERIOR, PapelComponente.MARCO_INFERIOR,
    PapelComponente.MARCO_LATERAL, PapelComponente.MARCO_LATERAL_ESQUERDO,
    PapelComponente.MARCO_LATERAL_DIREITO,
})

# Papéis que formam o quadro estrutural de uma folha móvel.
PAPEIS_ESTRUTURAIS_DE_FOLHA = frozenset({
    PapelComponente.TRAVESSA_SUPERIOR_FOLHA,
    PapelComponente.TRAVESSA_INFERIOR_FOLHA,
    PapelComponente.MONTANTE_LATERAL_FOLHA,
    PapelComponente.MONTANTE_CENTRAL_FOLHA,
})

# O baguete prende o vidro; ele não forma o quadro da folha. Mantê-lo
# distinguível é o que permite contar 12 ocorrências estruturais e 8 de
# baguete sem misturar as duas coisas.
PAPEIS_DE_BAGUETE = frozenset({PapelComponente.BAGUETE})


# `manifesto_promocao` e `biblioteca_oficial` descrevem o que o E.4C produziu.
# Chamá-lo de `catalogo` ou `tabela_de_fabricacao` criaria procedência
# enganosa: o manifesto prova que os perfis EXISTEM na biblioteca, não o que
# eles fazem numa janela.
TIPOS_DE_FONTE = frozenset({
    "catalogo", "medicao_fisica", "especialista_de_dominio",
    "lista_de_corte_real", "software_externo", "foto", "croqui",
    "tabela_de_fabricacao", "manifesto_promocao", "biblioteca_oficial",
    "validacao_caso_real", "conferencia_caso_receita",
    "registro_de_campo", "benchmark_externo", "referencia_sistema_anterior",
})

# Fontes que NUNCA sustentam confirmação física, por natureza e não por
# configuração. O Wvetro roda outro projeto e o VidroSys é sistema anterior do
# próprio Bruno: os dois podem corroborar estrutura e quantidade, e nenhum dos
# dois viu a janela fotografada. Deixá-los declarar `CONFIRMADO_*` faria um
# benchmark abrir gate de produção — por isso a recusa é na construção da
# fonte, não numa checagem que alguém pode esquecer de chamar.
TIPOS_SEM_AUTORIDADE_FISICA = frozenset({
    "benchmark_externo", "referencia_sistema_anterior",
})

# Como a `referencia` da fonte deve ser lida. A regra de caminho relativo vale
# só para arquivo: um DOI, um número de pedido ou uma URL não são caminhos.
FORMA_ARQUIVO = "arquivo"
FORMA_IDENTIFICADOR_EXTERNO = "identificador_externo"
FORMA_URL = "url"
# Artefato que vive FORA da raiz do repositório, endereçado por raiz LÓGICA +
# caminho relativo. O acervo bruto (21 MB de fotos, ficha e relatórios) não
# entra no Git — mas a evidência precisa ser citável mesmo assim. Guardar
# `/home/<usuario>/...` amarraria o repositório a uma máquina; guardar
# `SUPREMA_CORRER_2F` + `02_janela_pequena/foto.jpeg` + sha256 identifica o
# artefato sem dizer onde ele está montado hoje.
FORMA_ACERVO_EXTERNO = "acervo_externo"
FORMAS_DE_REFERENCIA = frozenset({FORMA_ARQUIVO, FORMA_IDENTIFICADOR_EXTERNO,
                                  FORMA_URL, FORMA_ACERVO_EXTERNO})

# Formas cuja `referencia` é caminho: valem as mesmas proteções contra absoluto,
# `~` e `..`. URL e identificador externo não são caminhos e ficam de fora.
FORMAS_DE_CAMINHO = frozenset({FORMA_ARQUIVO, FORMA_ACERVO_EXTERNO})

# Nome da raiz lógica — rótulo do acervo, nunca um caminho. `SUPREMA_CORRER_2F`
# é rótulo; `/home/<usuario>/Documentos/...` seria endereço de máquina.
FORMATO_RAIZ_LOGICA = "[A-Z0-9][A-Z0-9_]*"
_RE_RAIZ_LOGICA = re.compile(r"[A-Z0-9][A-Z0-9_]*")

# Até ONDE uma evidência vale. É diferente da NATUREZA dela.
#
# Uma ficha de levantamento preenchida em campo é registro PRIMÁRIO: quem a
# escreveu estava na frente da janela. Mas uma ficha única que cobre as três
# janelas é artefato COMPARTILHADO — ela não distingue um exemplar do outro.
# Rebaixar a ficha a "não primária" para o fingerprint de independência passar
# seria mentir sobre a origem do dado; o que muda entre os dois casos não é a
# natureza da fonte, é a abrangência dela.
ABRANGENCIA_EXEMPLAR = "EXEMPLAR"
ABRANGENCIA_COMPARTILHADA = "COMPARTILHADA"
ABRANGENCIAS_DE_FONTE = frozenset({ABRANGENCIA_EXEMPLAR,
                                   ABRANGENCIA_COMPARTILHADA})

FORMATO_DATA = "AAAA-MM-DD"
_RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")

# Identidade da evidência. Duas fotos da mesma janela são duas fontes; um
# índice por `tipo` faria a segunda sobrescrever a primeira em silêncio.
FORMATO_ID_FONTE = "FONTE-[A-Z0-9_-]+"
_RE_ID_FONTE = re.compile(r"FONTE-[A-Z0-9_-]+")
_RE_SHA256 = re.compile(r"[0-9a-f]{64}")

# Alvos que já sabemos que a tipologia precisa responder. É cobertura MÍNIMA,
# não universo fechado: a serralheria pode revelar uma regra que ninguém previu,
# e recusá-la por não estar nesta lista jogaria fora conhecimento novo.
ALVOS_DIMENSIONAIS_BASE = (
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

# De onde veio um alvo ou acessório que não estava na lista base. Item extra
# sem procedência é item extra silencioso — e aí a lista deixaria de significar
# alguma coisa.
ORIGEM_DESCOBERTO_EM_CAMPO = "DESCOBERTO_EM_CAMPO"
ORIGEM_DECIDIDO_POR_ESPECIALISTA = "DECIDIDO_POR_ESPECIALISTA"
ORIGENS_DE_ITEM_ADICIONAL = (ORIGEM_DESCOBERTO_EM_CAMPO,
                             ORIGEM_DECIDIDO_POR_ESPECIALISTA)

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
    # `registro_de_campo` entra aqui porque a ficha de levantamento é onde a
    # peça recebe NOME: nenhuma foto do acervo mostra código SU legível, e sem
    # a ficha "isto é o SU-040" não teria origem nenhuma.
    EstadoConhecimento.CONFIRMADO_CASO_REAL: frozenset({
        "medicao_fisica", "foto", "croqui", "lista_de_corte_real",
        "software_externo", "tabela_de_fabricacao", "validacao_caso_real",
        "conferencia_caso_receita", "registro_de_campo"}),
    EstadoConhecimento.DERIVADO_DE_REGRA_APROVADA: frozenset({
        "especialista_de_dominio", "tabela_de_fabricacao", "software_externo"}),
}


# Quem pode ASSINAR a validação final de um caso. Uma foto prova que a janela
# existe; ela não registra que alguém conferiu a lista de corte contra a peça.
# Manifesto e catálogo ficam de fora: falam da biblioteca, não desta janela.
TIPOS_APTOS_PARA_VALIDAR_CASO = frozenset({
    "validacao_caso_real", "especialista_de_dominio", "lista_de_corte_real",
    "tabela_de_fabricacao",
})

# Quem pode assinar a CONFERÊNCIA do resultado calculado contra o caso real.
# Uma foto mostra a janela; ela não registra que alguém comparou número a
# número. Catálogo, manifesto e biblioteca falam do produto, não desta
# comparação.
# Cada tipo de fonte só assina no estado que lhe corresponde: um especialista
# afirma CONFIRMADO_ESPECIALISTA, uma conferência de campo afirma
# CONFIRMADO_CASO_REAL. Aceitar qualquer estado "não pendente" deixaria passar
# um especialista_de_dominio marcado como caso real — procedência trocada.
ESTADO_EXIGIDO_POR_TIPO_DE_ASSINATURA = {
    "conferencia_caso_receita": EstadoConhecimento.CONFIRMADO_CASO_REAL,
    "validacao_caso_real": EstadoConhecimento.CONFIRMADO_CASO_REAL,
    "especialista_de_dominio": EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
    "lista_de_corte_real": EstadoConhecimento.CONFIRMADO_CASO_REAL,
    "tabela_de_fabricacao": EstadoConhecimento.CONFIRMADO_CASO_REAL,
}

TIPOS_APTOS_PARA_CONFERIR_RECEITA = frozenset({
    "conferencia_caso_receita", "especialista_de_dominio",
    "validacao_caso_real",
})


def estado_incompativel_com_assinatura(fonte) -> str | None:
    """Motivo pelo qual o par (tipo, estado) da fonte não assina, ou None."""
    esperado = ESTADO_EXIGIDO_POR_TIPO_DE_ASSINATURA.get(fonte.tipo)
    if esperado is None:
        return f"tipo {fonte.tipo!r} não assina conferência nem validação"
    if fonte.estado is not esperado:
        return (f"{fonte.tipo} assina em {esperado.value}, não em "
                f"{fonte.estado.value}")
    return None


# ---------------------------------------------------------------------------
# Imutabilidade profunda
# ---------------------------------------------------------------------------

def como_tupla(valor, campo: str = "coleção") -> tuple:
    """Cópia imutável de uma coleção. `None` é tupla vazia por convenção.

    Copiar é o ponto: guardar a lista recebida deixaria o chamador alterando o
    registro depois de construído. Recusa `str` e mapeamento — iterar uma
    string daria caracteres soltos, e um dicionário daria só as chaves, os dois
    em silêncio."""
    if valor is None:
        return ()
    if isinstance(valor, str) or isinstance(valor, bytes):
        raise ReceitaErro(
            f"{campo}: recebeu texto onde se espera uma coleção ({valor!r})")
    if isinstance(valor, Mapping):
        raise ReceitaErro(
            f"{campo}: recebeu mapeamento onde se espera uma coleção — "
            f"iterá-lo devolveria só as chaves")
    try:
        return tuple(valor)
    except TypeError as e:
        raise ReceitaErro(f"{campo}: valor não iterável ({valor!r})") from e

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


def validar_decimal_positivo_finito(valor, campo: str) -> None:
    """Medida preenchida é `Decimal` finito e positivo. Vazia é `None`.

    O carregador de YAML já cobrava isso, mas objeto construído em código
    passava direto: `CorteReal(comprimento_mm=Decimal("NaN"))` viraria uma peça
    com medida que não é número. A fronteira tem de estar no modelo."""
    if valor is None:
        return
    if not isinstance(valor, Decimal):
        raise ReceitaErro(
            f"{campo}: medida tem de ser Decimal, recebido "
            f"{type(valor).__name__} ({valor!r})")
    if not valor.is_finite():
        raise ReceitaErro(f"{campo}: medida não finita ({valor})")
    if valor <= 0:
        raise ReceitaErro(
            f"{campo}: medida {valor} — real é positiva; desconhecida é None")


def validar_inteiro_positivo_estrito(valor, campo: str) -> None:
    """Quantidade preenchida é `int` positivo. `True` não é quantidade.

    Em Python `isinstance(True, int)` é verdadeiro: sem esta checagem,
    `quantidade=True` viraria uma peça."""
    if valor is None:
        return
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ReceitaErro(
            f"{campo}: quantidade tem de ser int, recebido "
            f"{type(valor).__name__} ({valor!r})")
    if valor <= 0:
        raise ReceitaErro(
            f"{campo}: quantidade {valor} — desconhecida é None, nunca 0")


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
    para fora do repositório, onde a evidência não sobrevive ao clone.

    Vale igual para `acervo_externo`: lá o caminho é relativo à raiz LÓGICA, e
    um `..` sairia do acervo declarado do mesmo jeito."""
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
    sha256: str | None = None
    tamanho_bytes: int | None = None
    raiz_logica: str | None = None
    abrangencia: str = ABRANGENCIA_EXEMPLAR

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
        if self.abrangencia not in ABRANGENCIAS_DE_FONTE:
            raise ReceitaErro(
                f"{self.id_fonte}: abrangência desconhecida: "
                f"{self.abrangencia!r} "
                f"(conhecidas: {sorted(ABRANGENCIAS_DE_FONTE)})")
        if (self.tipo in TIPOS_SEM_AUTORIDADE_FISICA
                and self.estado in ESTADOS_CONFIRMADOS):
            raise ReceitaErro(
                f"{self.id_fonte}: {self.tipo} não confirma nada — declarado "
                f"{self.estado.value}. Benchmark externo e sistema anterior "
                f"corroboram; nenhum dos dois viu a janela real, e deixá-los "
                f"confirmar abriria gate com evidência que não existe. Use "
                f"{EstadoConhecimento.PENDENTE.value} e cite a fonte com papel "
                f"corroborativo.")
        if not self.referencia:
            raise ReceitaErro(f"{self.id_fonte}: referência vazia")
        if self.forma_referencia in FORMAS_DE_CAMINHO:
            motivo = _referencia_de_arquivo_insegura(self.referencia)
            if motivo:
                raise ReceitaErro(
                    f"{self.id_fonte}: {motivo} ({self.referencia!r}) — use "
                    f"caminho relativo à raiz do repo, ou declare "
                    f"forma_referencia={FORMA_IDENTIFICADOR_EXTERNO!r} / "
                    f"{FORMA_URL!r}")
        if self.forma_referencia == FORMA_ACERVO_EXTERNO:
            if not self.raiz_logica:
                raise ReceitaErro(
                    f"{self.id_fonte}: {FORMA_ACERVO_EXTERNO} exige "
                    f"raiz_logica — sem ela o caminho relativo não tem a que "
                    f"se referir, e a evidência viraria um nome solto.")
            if not _RE_RAIZ_LOGICA.fullmatch(self.raiz_logica):
                raise ReceitaErro(
                    f"{self.id_fonte}: raiz_logica inválida: "
                    f"{self.raiz_logica!r} — esperado {FORMATO_RAIZ_LOGICA}. "
                    f"É um RÓTULO de acervo, não um caminho de máquina.")
        elif self.raiz_logica is not None:
            raise ReceitaErro(
                f"{self.id_fonte}: raiz_logica só faz sentido com "
                f"forma_referencia={FORMA_ACERVO_EXTERNO!r}, não com "
                f"{self.forma_referencia!r}")
        if self.data is not None:
            motivo = data_invalida(self.data)
            if motivo:
                raise ReceitaErro(
                    f"{self.id_fonte}: data {self.data!r} {motivo}")
        if self.sha256 is not None and not _RE_SHA256.fullmatch(self.sha256):
            raise ReceitaErro(
                f"{self.id_fonte}: sha256 fora do formato ({self.sha256!r}) — "
                f"esperado 64 dígitos hexadecimais minúsculos")
        validar_inteiro_positivo_estrito(self.tamanho_bytes,
                                         f"{self.id_fonte}.tamanho_bytes")

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
                "forma_referencia": self.forma_referencia,
                "sha256": self.sha256, "tamanho_bytes": self.tamanho_bytes,
                "raiz_logica": self.raiz_logica,
                "abrangencia": self.abrangencia}

    @property
    def identifica_exemplar(self) -> bool:
        """Serve para provar que ESTA janela é diferente daquela?

        Natureza primária não basta: a ficha única das três janelas é primária
        e não distingue exemplar nenhum."""
        return (self.tipo in TIPOS_DE_EVIDENCIA_PRIMARIA
                and self.abrangencia == ABRANGENCIA_EXEMPLAR)


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


def incompatibilidades_das_fontes_embutidas(estado, fontes) -> tuple[str, ...]:
    """Mesma matriz da ficha, aplicada às fontes que vivem DENTRO do modelo.

    Componentes e regras carregam objetos `FonteEvidencia` em vez de IDs. Sem
    isto, a receita ficava com dois pesos: a ficha do especialista era cobrada
    pela compatibilidade semântica, e a receita não — um componente
    `CONFIRMADO_CASO_REAL` apoiado só num catálogo passaria."""
    fontes = tuple(fontes or ())
    if estado is None:
        return ("sem estado",)
    if estado in ESTADOS_NAO_CALCULAVEIS:
        return (f"estado {estado.value} não confirma",)
    if estado not in ESTADOS_CONFIRMADOS:
        return (f"estado desconhecido: {estado}",)
    if not fontes:
        return ("confirmado sem fonte",)

    problemas = []
    por_id = {}
    for f in fontes:
        anterior = por_id.get(f.id_fonte)
        if anterior is not None:
            problemas.append(
                f"id_fonte repetido: {f.id_fonte}"
                + ("" if anterior == f else " com conteúdos diferentes"))
        por_id[f.id_fonte] = f
        if f.estado in ESTADOS_NAO_CALCULAVEIS:
            problemas.append(
                f"{f.id_fonte} está {f.estado.value} e não sustenta confirmação")
    if not any(fonte_compativel_com_afirmacao(f, estado) for f in fontes):
        problemas.append(
            f"nenhuma fonte compatível com {estado.value} "
            f"(esperado estado {estado.value} e tipo em "
            f"{sorted(TIPOS_QUE_SUSTENTAM[estado])}"
            + (" com autoria completa"
               if estado is EstadoConhecimento.CONFIRMADO_ESPECIALISTA else "")
            + f"; encontrado "
            + str(sorted({f"{f.id_fonte}:{f.tipo}/{f.estado.value}"
                          for f in fontes})) + ")")
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
        object.__setattr__(self, "fontes",
                           como_tupla(self.fontes, f"{self.identificador}.fontes"))
        object.__setattr__(self, "observacoes",
                           como_tupla(self.observacoes,
                                      f"{self.identificador}.observacoes"))
        validar_inteiro_positivo_estrito(self.quantidade,
                                         f"{self.identificador}.quantidade")

    @property
    def confirmado(self) -> bool:
        """Confirmado de verdade: estado, papel, quantidade, orientação e
        evidência que sustente o que se afirma."""
        return (self.papel is not PapelComponente.NAO_CONFIRMADO
                and self.quantidade is not None
                and self.orientacao is not None
                and not incompatibilidades_das_fontes_embutidas(self.estado,
                                                                self.fontes))

    def pendencias(self) -> tuple[str, ...]:
        faltando = []
        if self.papel is PapelComponente.NAO_CONFIRMADO:
            faltando.append("papel não confirmado")
        if self.quantidade is None:
            faltando.append("quantidade não informada")
        if self.orientacao is None:
            faltando.append("orientação não informada")
        faltando += list(incompatibilidades_das_fontes_embutidas(self.estado,
                                                                 self.fontes))
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
    origem_do_alvo: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "fontes",
                           como_tupla(self.fontes, f"{self.identificador}.fontes"))
        object.__setattr__(self, "variaveis",
                           como_tupla(self.variaveis,
                                      f"{self.identificador}.variaveis"))
        # Alvo fora da lista base é legítimo — a serralheria pode revelar uma
        # regra que ninguém previu. O que não se aceita é item extra SILENCIOSO:
        # ele precisa dizer de onde veio e o que é.
        if self.alvo not in ALVOS_DIMENSIONAIS_BASE:
            if self.origem_do_alvo not in ORIGENS_DE_ITEM_ADICIONAL:
                raise ReceitaErro(
                    f"{self.identificador}: alvo {self.alvo!r} fora da lista "
                    f"base exige origem_do_alvo em "
                    f"{list(ORIGENS_DE_ITEM_ADICIONAL)}")
            if not self.descricao:
                raise ReceitaErro(
                    f"{self.identificador}: alvo adicional sem descrição")
        if self.estado in ESTADOS_CONFIRMADOS and not self.expressao:
            raise ReceitaErro(
                f"{self.identificador}: regra confirmada sem expressão")
        if self.estado in ESTADOS_CONFIRMADOS and not self.fontes:
            raise ReceitaErro(
                f"{self.identificador}: regra confirmada sem evidência")

    @property
    def calculavel(self) -> bool:
        return not self.impedimentos()

    def impedimentos(self) -> tuple[str, ...]:
        """Por que esta regra ainda não pode calcular."""
        faltando = []
        if not self.expressao:
            faltando.append("sem expressão")
        elif not self.variaveis:
            # Uma fórmula sem variáveis declaradas é uma constante disfarçada:
            # ninguém sabe de que medida ela depende.
            faltando.append("expressão sem variáveis declaradas")
        faltando += list(incompatibilidades_das_fontes_embutidas(self.estado,
                                                                 self.fontes))
        return tuple(faltando)

    def para_dict(self) -> dict:
        return {"identificador": self.identificador,
                "descricao": self.descricao, "alvo": self.alvo,
                "expressao": self.expressao, "variaveis": list(self.variaveis),
                "unidade": self.unidade, "estado": self.estado.value,
                "origem_do_alvo": self.origem_do_alvo,
                "fontes": [f.para_dict() for f in self.fontes]}


# Itens de acessório que uma correr de duas folhas precisa ter respondidos.
# Listar o item é registrar a PERGUNTA — não afirma modelo nem quantidade.
ITENS_DE_ACESSORIO_BASE = ("roldanas", "fecho", "contra_fecho", "escovas",
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
    descricao: str = ""
    origem_do_item: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "fontes",
                           como_tupla(self.fontes, f"{self.identificador}.fontes"))
        if not self.item:
            raise ReceitaErro(f"{self.identificador}: item vazio")
        if self.item not in ITENS_DE_ACESSORIO_BASE:
            if self.origem_do_item not in ORIGENS_DE_ITEM_ADICIONAL:
                raise ReceitaErro(
                    f"{self.identificador}: acessório {self.item!r} fora da "
                    f"lista base exige origem_do_item em "
                    f"{list(ORIGENS_DE_ITEM_ADICIONAL)}")
            if not self.descricao:
                raise ReceitaErro(
                    f"{self.identificador}: acessório adicional sem descrição")
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
        return not self.impedimentos()

    def impedimentos(self) -> tuple[str, ...]:
        faltando = []
        if not self.quantidade_expressao:
            faltando.append("sem quantidade")
        if not self.posicao:
            faltando.append("sem posição")
        faltando += list(incompatibilidades_das_fontes_embutidas(self.estado,
                                                                 self.fontes))
        return tuple(faltando)

    def para_dict(self) -> dict:
        return {"identificador": self.identificador, "item": self.item,
                "quantidade_expressao": self.quantidade_expressao,
                "posicao": self.posicao, "estado": self.estado.value,
                "descricao": self.descricao,
                "origem_do_item": self.origem_do_item,
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
        object.__setattr__(self, "fontes_ids",
                           como_tupla(self.fontes_ids, "fontes_ids"))

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
class AplicacaoPerfil(Afirmacao):
    """UMA ocorrência funcional de um perfil na janela.

    O mesmo perfil pode aparecer em duas laterais, nas duas folhas, em papéis
    diferentes e com comprimentos diferentes. Um bloco único por perfil forçaria
    a ficha a escolher um papel só — e o segundo uso sumiria."""
    id_componente: str | None = None
    funcao: PapelComponente | None = None
    quantidade: int | None = None
    orientacao: str | None = None
    folha: str | None = None
    posicao: str | None = None

    CAMPOS = ("id_componente", "funcao", "quantidade", "orientacao", "folha",
              "posicao")

    def __post_init__(self):
        super().__post_init__()
        validar_inteiro_positivo_estrito(self.quantidade,
                                         "aplicacao.quantidade")

    @property
    def vazia(self) -> bool:
        return not any(getattr(self, c) for c in self.CAMPOS) \
            and not self.fontes_ids and not self.dados_adicionais

    def para_dict(self) -> dict:
        d = {"id_componente": self.id_componente,
             "funcao": self.funcao.value if self.funcao else None,
             "quantidade": self.quantidade, "orientacao": self.orientacao,
             "folha": self.folha, "posicao": self.posicao}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class PerfilNoCasoReal(Afirmacao):
    """O que a ficha diz sobre um perfil — e suas APLICAÇÕES na janela.

    Perfil é o produto extrudado; aplicação é o papel que ele exerce numa
    posição. Confundir os dois faria o sistema afirmar que o SU-003 tem uma
    única função, quando ele pode ser marco esquerdo e direito ao mesmo tempo."""
    codigo_perfil: str = ""
    observacoes_gerais: str | None = None
    aplicacoes: tuple[AplicacaoPerfil, ...] = ()

    CAMPOS = ("observacoes_gerais",)

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, "aplicacoes",
                           como_tupla(self.aplicacoes,
                                      f"perfis.{self.codigo_perfil}.aplicacoes"))

    @property
    def vazio(self) -> bool:
        return (not self.observacoes_gerais and not self.fontes_ids
                and not self.dados_adicionais
                and all(a.vazia for a in self.aplicacoes))

    def para_dict(self) -> dict:
        d = {"codigo_perfil": self.codigo_perfil,
             "observacoes_gerais": self.observacoes_gerais,
             "aplicacoes": [a.para_dict() for a in self.aplicacoes]}
        d.update(self._base_dict())
        return d


@dataclass(frozen=True)
class CorteReal(Afirmacao):
    """Uma peça efetivamente cortada. É o dado do qual uma fórmula futura
    poderá ser DERIVADA — nunca o contrário.

    `componente_id` liga a peça à ocorrência funcional que a produziu. Sem
    isso, dois cortes do mesmo perfil com comprimentos diferentes não dizem
    qual é o marco e qual é a travessa."""
    perfil: str | None = None
    comprimento_mm: Decimal | None = None
    quantidade: int | None = None
    angulo: str | None = None
    observacao: str | None = None
    componente_id: str | None = None

    def __post_init__(self):
        super().__post_init__()
        validar_decimal_positivo_finito(self.comprimento_mm,
                                        "corte.comprimento_mm")
        validar_inteiro_positivo_estrito(self.quantidade, "corte.quantidade")

    def para_dict(self) -> dict:
        d = {"perfil": self.perfil, "componente_id": self.componente_id,
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

    def __post_init__(self):
        super().__post_init__()
        for campo in ("largura_mm", "altura_mm", "espessura_mm"):
            validar_decimal_positivo_finito(getattr(self, campo),
                                            f"vidro.{campo}")

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

    def __post_init__(self):
        super().__post_init__()
        validar_decimal_positivo_finito(self.comprimento_mm,
                                        "baguete.comprimento_mm")
        validar_inteiro_positivo_estrito(self.quantidade, "baguete.quantidade")

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

    def __post_init__(self):
        super().__post_init__()
        validar_inteiro_positivo_estrito(self.quantidade, "acessorio.quantidade")

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

    def __post_init__(self):
        super().__post_init__()
        validar_decimal_positivo_finito(self.valor_mm, "folga.valor_mm")

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

    def __post_init__(self):
        super().__post_init__()
        validar_decimal_positivo_finito(self.valor_mm, "sobreposicao.valor_mm")

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
        object.__setattr__(self, "fontes_ids",
                           como_tupla(self.fontes_ids, "validacao.fontes_ids"))
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
    id_exemplar: str | None = None
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

    COLECOES = ("fontes_ids_dimensoes", "perfis", "cortes", "vidros",
                "baguetes", "acessorios", "folgas", "sobreposicoes", "croquis",
                "fontes", "duvidas")

    def __post_init__(self):
        object.__setattr__(self, "dados_adicionais",
                           congelar_dados_adicionais(self.dados_adicionais))
        for campo in self.COLECOES:
            object.__setattr__(self, campo,
                               como_tupla(getattr(self, campo),
                                          f"caso_real.{campo}"))
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
            validar_decimal_positivo_finito(getattr(self, campo),
                                            f"{self.identificador}.{campo}")
        try:
            indexar_fontes(self.fontes)
        except ReceitaErro as e:
            raise ReceitaErro(f"{self.identificador}: {e}") from e

    @property
    def indice_fontes(self) -> dict:
        return {f.id_fonte: f for f in self.fontes}

    @property
    def validacao_declarada_aprovada(self) -> bool:
        """O que o documento AFIRMA. Não é o mesmo que estar validado.

        O estado efetivo depende também das fontes serem aptas e dos dados
        serem íntegros — e isso quem decide é `validar.estado_validacao_caso`.
        Expor `validado=True` aqui diria que o caso serve de prova enquanto o
        gate ainda o considera inválido."""
        return self.validacao is not None and self.validacao.aprovada

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
        if self.id_exemplar:
            preenchidas.append("id_exemplar")
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
        """Mínimo ESTRUTURAL para tentar derivar qualquer fórmula.

        `bool(cortes) and bool(vidros)` aceitava tuplas de objetos vazios: uma
        ficha sem uma única peça descrita seria classificada como recebida por
        completo. Aqui cada lista precisa ter ao menos um item que descreva
        algo — sem exigir aprovação final, que é outra etapa."""
        if not self.tem_medidas:
            return False
        corte_util = any(c.perfil and c.comprimento_mm is not None
                         and c.quantidade is not None for c in self.cortes)
        vidro_util = any(v.folha and v.largura_mm is not None
                         and v.altura_mm is not None
                         and v.espessura_mm is not None for v in self.vidros)
        return corte_util and vidro_util

    def para_dict(self) -> dict:
        return {
            "identificador": self.identificador,
            "id_exemplar": self.id_exemplar,
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
            "validacao_declarada_aprovada": self.validacao_declarada_aprovada,
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


class OrigemResultadoCalculo(str, Enum):
    """Quem produziu a saída. Fixture de teste NUNCA libera fabricação.

    Sem esta distinção, uma tupla de strings montada num teste abriria o mesmo
    portão que a saída de um motor real — e o portão libera corte de alumínio."""
    MOTOR_CALCULO = "MOTOR_CALCULO"
    FIXTURE_TESTE = "FIXTURE_TESTE"


@dataclass(frozen=True)
class CorteCalculado:
    """Uma peça que o cálculo diz que deve ser cortada."""
    componente_id: str
    perfil: str
    comprimento_mm: Decimal
    quantidade: int

    def __post_init__(self):
        for campo in ("componente_id", "perfil"):
            if not str(getattr(self, campo) or "").strip():
                raise ReceitaErro(f"corte calculado sem {campo}")
        validar_decimal_positivo_finito(self.comprimento_mm,
                                        "corte_calculado.comprimento_mm")
        if self.comprimento_mm is None:
            raise ReceitaErro("corte calculado sem comprimento_mm")
        validar_inteiro_positivo_estrito(self.quantidade,
                                         "corte_calculado.quantidade")
        if self.quantidade is None:
            raise ReceitaErro("corte calculado sem quantidade")

    def chave(self) -> tuple:
        return (self.componente_id, self.perfil, self.comprimento_mm,
                self.quantidade)

    def para_dict(self) -> dict:
        return {"componente_id": self.componente_id, "perfil": self.perfil,
                "comprimento_mm": str(self.comprimento_mm),
                "quantidade": self.quantidade}


@dataclass(frozen=True)
class VidroCalculado:
    folha: str
    largura_mm: Decimal
    altura_mm: Decimal
    espessura_mm: Decimal

    def __post_init__(self):
        if not str(self.folha or "").strip():
            raise ReceitaErro("vidro calculado sem folha")
        for campo in ("largura_mm", "altura_mm", "espessura_mm"):
            v = getattr(self, campo)
            validar_decimal_positivo_finito(v, f"vidro_calculado.{campo}")
            if v is None:
                raise ReceitaErro(f"vidro calculado sem {campo}")

    def chave(self) -> tuple:
        return (self.folha, self.largura_mm, self.altura_mm, self.espessura_mm)

    def para_dict(self) -> dict:
        return {"folha": self.folha, "largura_mm": str(self.largura_mm),
                "altura_mm": str(self.altura_mm),
                "espessura_mm": str(self.espessura_mm)}


@dataclass(frozen=True)
class AcessorioCalculado:
    item: str
    quantidade: int
    posicao: str

    def __post_init__(self):
        for campo in ("item", "posicao"):
            if not str(getattr(self, campo) or "").strip():
                raise ReceitaErro(f"acessório calculado sem {campo}")
        validar_inteiro_positivo_estrito(self.quantidade,
                                         "acessorio_calculado.quantidade")
        if self.quantidade is None:
            raise ReceitaErro("acessório calculado sem quantidade")

    def chave(self) -> tuple:
        return (self.item, self.quantidade, self.posicao)

    def para_dict(self) -> dict:
        return {"item": self.item, "quantidade": self.quantidade,
                "posicao": self.posicao}


@dataclass(frozen=True)
class ResultadoCalculoCaso:
    """A saída que o motor de cálculo produzirá — quando existir.

    O contrato existe agora para que a conferência possa apontar para ELE. Sem
    isso, "conferi cortes, vidros e acessórios" é uma afirmação sem objeto:
    conferiu contra o quê?

    `origem` separa a saída de um motor real de uma fixture de teste. A E.4D não
    tem motor: nenhum resultado `MOTOR_CALCULO` existe aqui, e por isso o gate
    de produção continua fechado em qualquer fixture."""
    id_resultado: str
    caso_id: str
    receita_codigo: str
    gerado_por: str
    origem: OrigemResultadoCalculo
    componentes: tuple[str, ...] = ()
    cortes: tuple[CorteCalculado, ...] = ()
    vidros: tuple[VidroCalculado, ...] = ()
    acessorios: tuple[AcessorioCalculado, ...] = ()
    versao_motor: str | None = None

    TIPOS = {"cortes": CorteCalculado, "vidros": VidroCalculado,
             "acessorios": AcessorioCalculado}

    def __post_init__(self):
        object.__setattr__(self, "componentes",
                           como_tupla(self.componentes, "resultado.componentes"))
        for campo, tipo in self.TIPOS.items():
            itens = como_tupla(getattr(self, campo), f"resultado.{campo}")
            fora = [type(i).__name__ for i in itens if not isinstance(i, tipo)]
            if fora:
                raise ReceitaErro(
                    f"resultado.{campo}: elementos de tipo inesperado {fora} "
                    f"(esperado {tipo.__name__}) — uma tupla de strings não é "
                    f"saída de cálculo")
            object.__setattr__(self, campo, itens)
        for campo in ("id_resultado", "caso_id", "receita_codigo", "gerado_por"):
            if not str(getattr(self, campo) or "").strip():
                raise ReceitaErro(f"resultado de cálculo sem {campo}")
        if not isinstance(self.origem, OrigemResultadoCalculo):
            raise ReceitaErro(
                f"resultado com origem inválida: {self.origem!r} "
                f"(esperado {[o.value for o in OrigemResultadoCalculo]})")
        if (self.origem is OrigemResultadoCalculo.MOTOR_CALCULO
                and not str(self.versao_motor or "").strip()):
            raise ReceitaErro(
                f"{self.id_resultado}: resultado de MOTOR_CALCULO exige "
                f"versao_motor — sem ela não há como reproduzir o cálculo")

    @property
    def de_motor(self) -> bool:
        return self.origem is OrigemResultadoCalculo.MOTOR_CALCULO

    @property
    def tem_conteudo(self) -> bool:
        """Resultado vazio não prova cálculo nenhum."""
        return bool(self.componentes and self.cortes and self.vidros)

    def para_dict(self) -> dict:
        return {"id_resultado": self.id_resultado, "caso_id": self.caso_id,
                "receita_codigo": self.receita_codigo,
                "gerado_por": self.gerado_por, "origem": self.origem.value,
                "versao_motor": self.versao_motor,
                "componentes": list(self.componentes),
                "cortes": [c.para_dict() for c in self.cortes],
                "vidros": [v.para_dict() for v in self.vidros],
                "acessorios": [a.para_dict() for a in self.acessorios]}


@dataclass(frozen=True)
class ConferenciaCasoContraReceita:
    """Registro de que a receita foi comparada, item a item, com uma janela real.

    Sem isto, "caso validado" significa apenas que os dados do caso estão
    íntegros — nada garante que a receita PRODUZ aquele caso. É a diferença
    entre ter a lista de corte e ter conferido a lista contra o que o sistema
    calcularia."""
    caso_id: str
    resultado: ResultadoAprovacao
    responsavel: str
    data: str
    fonte_id: str
    resultado_calculo_id: str = ""
    componentes_conferidos: tuple[str, ...] = ()
    cortes_conferidos: bool = False
    vidros_conferidos: bool = False
    acessorios_conferidos: bool = False
    divergencias: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "componentes_conferidos",
                           como_tupla(self.componentes_conferidos,
                                      "conferencia.componentes_conferidos"))
        object.__setattr__(self, "divergencias",
                           como_tupla(self.divergencias,
                                      "conferencia.divergencias"))
        if not isinstance(self.resultado, ResultadoAprovacao):
            raise ReceitaErro(
                f"conferência com resultado inválido: {self.resultado!r}")
        for campo in ("caso_id", "responsavel", "data", "fonte_id",
                      "resultado_calculo_id"):
            if not str(getattr(self, campo) or "").strip():
                raise ReceitaErro(
                    f"conferência sem {campo}"
                    + (" — conferir exige um resultado calculado para comparar"
                       if campo == "resultado_calculo_id" else ""))
        motivo = data_invalida(self.data)
        if motivo:
            raise ReceitaErro(f"conferência: data {self.data!r} {motivo}")
        if not _RE_ID_FONTE.fullmatch(self.fonte_id):
            raise ReceitaErro(
                f"conferência com fonte_id fora do formato: {self.fonte_id!r}")

    @property
    def aprovada(self) -> bool:
        """Aprovada de verdade: sem divergências e com as três frentes vistas."""
        return (self.resultado is ResultadoAprovacao.APROVADO
                and not self.divergencias
                and self.cortes_conferidos and self.vidros_conferidos
                and self.acessorios_conferidos)

    def para_dict(self) -> dict:
        return {"caso_id": self.caso_id, "resultado": self.resultado.value,
                "responsavel": self.responsavel, "data": self.data,
                "fonte_id": self.fonte_id,
                "resultado_calculo_id": self.resultado_calculo_id,
                "componentes_conferidos": list(self.componentes_conferidos),
                "cortes_conferidos": self.cortes_conferidos,
                "vidros_conferidos": self.vidros_conferidos,
                "acessorios_conferidos": self.acessorios_conferidos,
                "divergencias": list(self.divergencias)}


def assinatura_documental_caso(caso: CasoRealFabricacao) -> str:
    """Impressão digital do EXEMPLAR — não das medidas.

    Medidas diferentes não provam três janelas: a mesma lista de corte pode ser
    reaproveitada com números trocados. A assinatura junta exemplar, medidas,
    evidência primária, cortes e vidros; duas iguais são o mesmo documento."""
    import hashlib
    partes = [
        f"exemplar={caso.id_exemplar or ''}",
        f"dimensoes={caso.largura_total_mm}x{caso.altura_total_mm}",
        "fontes=" + ";".join(sorted(
            f"{f.id_fonte}|{f.tipo}|{f.referencia}|{f.sha256 or ''}"
            for f in caso.fontes)),
        "cortes=" + ";".join(sorted(
            f"{c.componente_id or ''}|{c.perfil}|{c.comprimento_mm}|{c.quantidade}"
            for c in caso.cortes)),
        "vidros=" + ";".join(sorted(
            f"{v.folha}|{v.largura_mm}|{v.altura_mm}|{v.espessura_mm}"
            for v in caso.vidros)),
    ]
    return hashlib.sha256("\n".join(partes).encode("utf-8")).hexdigest()


# NATUREZA da evidência: quem produziu o registro estava diante da coisa.
# `registro_de_campo` pertence a este conjunto — a ficha foi preenchida na
# frente da janela. Se ela identifica UM exemplar ou vale para vários é outra
# pergunta, respondida por `abrangencia`, não por este conjunto.
TIPOS_DE_EVIDENCIA_PRIMARIA = frozenset({
    "medicao_fisica", "foto", "croqui", "lista_de_corte_real",
    "validacao_caso_real", "conferencia_caso_receita", "registro_de_campo",
})


def fingerprint_fonte_primaria(fonte: FonteEvidencia) -> str:
    """Identidade do ARTEFATO, não do caminho.

    O mesmo arquivo copiado para três pastas continua sendo um artefato só: por
    isso o hash manda quando existe. Sem ele, três cópias do mesmo croqui
    passariam como três evidências independentes."""
    if fonte.sha256:
        return f"sha256:{fonte.sha256}"
    if fonte.forma_referencia == FORMA_URL:
        return f"url:{fonte.referencia.strip().rstrip('/').lower()}"
    if fonte.forma_referencia == FORMA_IDENTIFICADOR_EXTERNO:
        return f"id:{fonte.referencia.strip()}"
    return f"arquivo:{fonte.referencia.strip()}"


def fingerprints_primarios_do_caso(caso: CasoRealFabricacao) -> frozenset:
    """Evidência que IDENTIFICA esta janela física.

    Catálogo, manifesto e biblioteca podem ser compartilhados entre casos —
    falam do produto, não do exemplar. Fonte primária declarada
    `COMPARTILHADA` sai daqui pelo mesmo motivo, e continua primária: uma ficha
    de campo que cobre as três janelas prova que alguém mediu as três, não que
    esta é diferente daquela."""
    return frozenset(fingerprint_fonte_primaria(f) for f in caso.fontes
                     if f.identifica_exemplar)


def fontes_primarias_do_caso(caso: CasoRealFabricacao) -> frozenset:
    """Compatibilidade: fingerprints da evidência primária."""
    return fingerprints_primarios_do_caso(caso)


# ---------------------------------------------------------------------------
# Relação entre componentes
# ---------------------------------------------------------------------------

class TipoRelacaoComponentes(str, Enum):
    """Relações POSSÍVEIS entre duas ocorrências funcionais.

    `ENCONTRO_CENTRAL` é o caso da correr de duas folhas: os dois montantes
    centrais se encontram, cada um na sua folha e no seu plano. Não existe uma
    terceira peça chamada "encontro" — existe uma relação entre duas peças."""
    ENCONTRO_CENTRAL = "ENCONTRO_CENTRAL"


# Relações binárias: exatamente dois participantes, nem mais nem menos.
ARIDADE_DA_RELACAO = {
    TipoRelacaoComponentes.ENCONTRO_CENTRAL: 2,
}

# Relações cujos participantes têm de estar em folhas diferentes. Dois
# montantes da MESMA folha não se encontram — eles são a mesma folha.
RELACOES_ENTRE_FOLHAS_DIFERENTES = frozenset({
    TipoRelacaoComponentes.ENCONTRO_CENTRAL,
})


@dataclass(frozen=True)
class RelacaoEntreComponentes:
    """Liga ocorrências funcionais por IDENTIFICADOR, não por código de perfil.

    Citar "SU-040 encontra SU-041" seria ambíguo assim que um perfil aparecer
    em mais de uma ocorrência: qual das ocorrências encontra qual? A relação
    aponta para os identificadores dos componentes."""
    tipo: TipoRelacaoComponentes
    participantes: tuple[str, ...]
    estado: EstadoConhecimento = EstadoConhecimento.PENDENTE
    fontes: tuple[FonteEvidencia, ...] = ()
    observacao: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "participantes",
                           como_tupla(self.participantes,
                                      "relacao.participantes"))
        object.__setattr__(self, "fontes",
                           como_tupla(self.fontes, "relacao.fontes"))
        if not isinstance(self.tipo, TipoRelacaoComponentes):
            raise ReceitaErro(
                f"relação com tipo inválido: {self.tipo!r} "
                f"(esperado {[t.value for t in TipoRelacaoComponentes]})")
        vazios = [p for p in self.participantes if not str(p or "").strip()]
        if vazios:
            raise ReceitaErro(f"{self.tipo.value}: participante vazio")
        if len(set(self.participantes)) != len(self.participantes):
            raise ReceitaErro(
                f"{self.tipo.value}: participante repetido "
                f"{list(self.participantes)} — uma peça não se relaciona "
                f"consigo mesma")
        esperada = ARIDADE_DA_RELACAO.get(self.tipo)
        if esperada is not None and len(self.participantes) != esperada:
            raise ReceitaErro(
                f"{self.tipo.value}: {len(self.participantes)} participantes "
                f"(esperado exatamente {esperada})")

    @property
    def identificador(self) -> str:
        return f"{self.tipo.value}:{'|'.join(self.participantes)}"

    def para_dict(self) -> dict:
        return {"tipo": self.tipo.value,
                "participantes": list(self.participantes),
                "estado": self.estado.value,
                "observacao": self.observacao,
                "fontes": [f.para_dict() for f in self.fontes]}


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
    perfis_disponiveis: tuple[ReferenciaPerfilOficial, ...] = ()
    componentes: tuple[ComponenteReceita, ...] = ()
    relacoes: tuple[RelacaoEntreComponentes, ...] = ()
    regras_corte: tuple[RegraDimensional, ...] = ()
    regras_vidro: tuple[RegraDimensional, ...] = ()
    regras_acessorios: tuple[RegraAcessorio, ...] = ()
    casos_reais: tuple[CasoRealFabricacao, ...] = ()
    fontes: tuple[FonteEvidencia, ...] = ()
    estado: str = ESTADO_RECEITA_PRELIMINAR
    aprovacoes: tuple[AprovacaoEspecialista, ...] = ()
    resultados_calculados: tuple[ResultadoCalculoCaso, ...] = ()
    conferencias: tuple[ConferenciaCasoContraReceita, ...] = ()
    perguntas_abertas: tuple[str, ...] = ()

    COLECOES = {
        "perfis_disponiveis": ReferenciaPerfilOficial,
        "componentes": ComponenteReceita,
        "relacoes": RelacaoEntreComponentes,
        "regras_corte": RegraDimensional,
        "regras_vidro": RegraDimensional,
        "regras_acessorios": RegraAcessorio,
        "casos_reais": CasoRealFabricacao,
        "fontes": FonteEvidencia,
        "aprovacoes": AprovacaoEspecialista,
        "resultados_calculados": ResultadoCalculoCaso,
        "conferencias": ConferenciaCasoContraReceita,
        "perguntas_abertas": str,
    }

    def __post_init__(self):
        for campo, tipo in self.COLECOES.items():
            itens = como_tupla(getattr(self, campo), f"{self.codigo}.{campo}")
            fora = [type(i).__name__ for i in itens if not isinstance(i, tipo)]
            if fora:
                raise ReceitaErro(
                    f"{self.codigo}.{campo}: elementos de tipo inesperado "
                    f"{fora} (esperado {tipo.__name__})")
            object.__setattr__(self, campo, itens)

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

    @property
    def codigos_disponiveis(self) -> tuple[str, ...]:
        return tuple(p.codigo_perfil for p in self.perfis_disponiveis)

    def componentes_do_perfil(self, codigo_perfil: str) -> tuple[ComponenteReceita, ...]:
        """Todas as ocorrências daquele perfil — podem ser zero, uma ou várias."""
        return tuple(c for c in self.componentes
                     if c.perfil.codigo_perfil == codigo_perfil)

    def relacoes_do_tipo(self, tipo: TipoRelacaoComponentes) -> tuple:
        return tuple(r for r in self.relacoes if r.tipo is tipo)

    def componentes_da_folha(self, folha: str) -> tuple[ComponenteReceita, ...]:
        return tuple(c for c in self.componentes if c.folha == folha)

    def componente_por_id(self, identificador: str) -> ComponenteReceita | None:
        for c in self.componentes:
            if c.identificador == identificador:
                return c
        return None

    def conferencia_do_caso(self, caso_id: str):
        return tuple(c for c in self.conferencias if c.caso_id == caso_id)

    def resultado_calculado(self, id_resultado: str):
        for r in self.resultados_calculados:
            if r.id_resultado == id_resultado:
                return r
        return None


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
