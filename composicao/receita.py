"""Receita preliminar da Janela Suprema de correr com duas folhas.

Esta receita **não sabe montar a janela**. Ela sabe apenas:

- quais oito perfis oficiais estão disponíveis;
- que existe um vocabulário de papéis funcionais possíveis;
- quais regras dimensionais precisam existir um dia — todas `PENDENTE`,
  todas com `expressao=None`.

Nenhum papel foi atribuído, nenhuma quantidade foi estimada, nenhuma fórmula
foi escrita. Um `MARCO_SUPERIOR` chutado aqui viraria corte errado depois, e o
erro só apareceria no alumínio cortado.
"""
from __future__ import annotations

from .fontes import PERFIS_SUPREMA_E4C, referencia_oficial
from .modelos import (ESTADO_RECEITA_PRELIMINAR, ITENS_DE_ACESSORIO,
                      ComponenteReceita, EstadoConhecimento, FonteEvidencia,
                      PapelComponente, ReceitaTipologia, RegraAcessorio,
                      RegraDimensional)

CODIGO_TIPOLOGIA = "SUPREMA_CORRER_2F"
NOME_TIPOLOGIA = "Janela Suprema de correr com duas folhas"
SISTEMA = "Suprema"
QUANTIDADE_FOLHAS = 2

# A única coisa CONFIRMADA nesta rodada: que os oito perfis existem na
# biblioteca oficial, promovidos e auditados no E.4C.
#
# O manifesto NÃO é catálogo nem tabela de fabricação — chamá-lo assim daria a
# entender que ele diz algo sobre corte ou montagem. Ele é o registro do evento
# de promoção, e prova exatamente duas coisas: que os oito perfis existem na
# biblioteca oficial, e que os IDs GEO e as associações estão aprovados.
FONTE_PROMOCAO_E4C = FonteEvidencia(
    tipo="manifesto_promocao",
    referencia="curadoria/promocoes/e4c/manifesto_promocao_e4b.json",
    descricao=("Promoção oficial E.4C: oito geometrias e oito associações "
               "ALCOA-SU-xxx na biblioteca. PROVA: os perfis existem, com IDs "
               "e associações aprovados. NÃO PROVA: papel na janela, "
               "quantidade, orientação, corte, vidro ou acessório."),
    estado=EstadoConhecimento.CONFIRMADO_BIBLIOTECA_OFICIAL,
    data="2026-08-02",
)

# Regras que a tipologia vai precisar. Declarar o alvo é registrar a pergunta;
# responder exige o especialista e casos reais.
ALVOS_DE_CORTE = (
    ("corte_marco_superior", "Comprimento de corte do marco superior"),
    ("corte_marco_inferior", "Comprimento de corte do marco inferior"),
    ("corte_marco_lateral", "Comprimento de corte dos marcos laterais"),
    ("largura_folha", "Largura de cada folha móvel"),
    ("altura_folha", "Altura de cada folha móvel"),
    ("corte_baguete_horizontal", "Comprimento das baguetes horizontais"),
    ("corte_baguete_vertical", "Comprimento das baguetes verticais"),
)

ALVOS_DE_VIDRO = (
    ("largura_vidro", "Largura da chapa de vidro por folha"),
    ("altura_vidro", "Altura da chapa de vidro por folha"),
)

PERGUNTAS_ABERTAS = (
    "Qual perfil cumpre cada papel na janela (marco, travessa, montante, "
    "encontro central, mão-de-amigo, baguete)?",
    "Quantas peças de cada perfil entram numa janela de duas folhas?",
    "Qual a orientação de corte de cada peça (vertical, horizontal, 45°)?",
    "Qual o desconto de corte de cada perfil em relação à medida de vão?",
    "Quais as folgas de montagem entre folha e marco, e entre as duas folhas?",
    "Qual a sobreposição no encontro central?",
    "Como o vidro é dimensionado a partir da folha (folga de encaixe, calços)?",
    "Que acessórios entram (roldanas, fecho, contra-fecho, escovas, vedações, "
    "fixações), em que quantidade e em que posição?",
    "Qual folha corre no trilho interno e qual no externo, vista de que lado?",
    "Onde fica o fecho e qual o sentido de movimento de cada folha?",
)


def _componente_preliminar(codigo_perfil: str) -> ComponenteReceita:
    """Referência oficial ao perfil, SEM papel atribuído.

    O estado é `PENDENTE` e o papel é `NAO_CONFIRMADO` de propósito: a única
    evidência que existe é a de que o perfil está na biblioteca."""
    return ComponenteReceita(
        identificador=f"{CODIGO_TIPOLOGIA}:{codigo_perfil}",
        perfil=referencia_oficial(codigo_perfil),
        papel=PapelComponente.NAO_CONFIRMADO,
        quantidade=None,
        orientacao=None,
        folha=None,
        posicao=None,
        estado=EstadoConhecimento.PENDENTE,
        fontes=(FONTE_PROMOCAO_E4C,),
        observacoes=(
            "perfil oficial disponível; papel funcional na tipologia ainda "
            "não confirmado pelo especialista de domínio",
        ),
    )


def _regra_pendente(alvo: str, descricao: str, grupo: str) -> RegraDimensional:
    return RegraDimensional(
        identificador=f"{CODIGO_TIPOLOGIA}:{alvo}",
        descricao=descricao,
        alvo=alvo,
        expressao=None,                     # nenhuma fórmula foi confirmada
        variaveis=(),
        unidade="mm",
        estado=EstadoConhecimento.PENDENTE,
        fontes=(),
    )


def _regra_acessorio_pendente(item: str) -> RegraAcessorio:
    """Registra a PERGUNTA sobre um acessório, sem afirmar modelo ou quantidade.

    Deixar a lista vazia seria pior: o gate de cálculo poderia abrir sem que
    ninguém tivesse perguntado quantas roldanas a janela leva."""
    return RegraAcessorio(
        identificador=f"{CODIGO_TIPOLOGIA}:acessorio:{item}",
        item=item,
        quantidade_expressao=None,
        posicao=None,
        estado=EstadoConhecimento.PENDENTE,
        fontes=(),
    )


def construir_receita_preliminar() -> ReceitaTipologia:
    """Receita preliminar — determinística e sem efeito colateral.

    Não lê disco, não altera nada, e duas chamadas produzem receitas iguais."""
    componentes = tuple(_componente_preliminar(c) for c in PERFIS_SUPREMA_E4C)
    regras_corte = tuple(_regra_pendente(a, d, "corte") for a, d in ALVOS_DE_CORTE)
    regras_vidro = tuple(_regra_pendente(a, d, "vidro") for a, d in ALVOS_DE_VIDRO)
    return ReceitaTipologia(
        codigo=CODIGO_TIPOLOGIA,
        nome=NOME_TIPOLOGIA,
        sistema=SISTEMA,
        quantidade_folhas=QUANTIDADE_FOLHAS,
        componentes=componentes,
        regras_corte=regras_corte,
        regras_vidro=regras_vidro,
        regras_acessorios=tuple(_regra_acessorio_pendente(i)
                                for i in ITENS_DE_ACESSORIO),
        casos_reais=(),
        fontes=(FONTE_PROMOCAO_E4C,),
        estado=ESTADO_RECEITA_PRELIMINAR,
        aprovacoes=(),
        perguntas_abertas=PERGUNTAS_ABERTAS,
    )


def variaveis_disponiveis() -> tuple[dict, ...]:
    """Vocabulário de variáveis que uma fórmula futura poderá usar.

    Listar a variável não define fórmula nenhuma — é o dicionário do que se
    pode perguntar, para que a resposta do especialista tenha onde encaixar."""
    return (
        {"nome": "largura_total_mm", "origem": "medida do vão / do caso real",
         "estado": EstadoConhecimento.PENDENTE.value},
        {"nome": "altura_total_mm", "origem": "medida do vão / do caso real",
         "estado": EstadoConhecimento.PENDENTE.value},
        {"nome": "quantidade_folhas", "origem": "tipologia (=2)",
         "estado": EstadoConhecimento.CONFIRMADO_CATALOGO.value},
        {"nome": "largura_perfil_mm", "origem": "bounding box da geometria oficial",
         "estado": EstadoConhecimento.CONFIRMADO_CATALOGO.value},
        {"nome": "altura_perfil_mm", "origem": "bounding box da geometria oficial",
         "estado": EstadoConhecimento.CONFIRMADO_CATALOGO.value},
        {"nome": "desconto_de_corte_mm", "origem": "especialista de domínio",
         "estado": EstadoConhecimento.PENDENTE.value},
        {"nome": "folga_de_montagem_mm", "origem": "especialista de domínio",
         "estado": EstadoConhecimento.PENDENTE.value},
        {"nome": "sobreposicao_central_mm", "origem": "especialista de domínio",
         "estado": EstadoConhecimento.PENDENTE.value},
        {"nome": "folga_de_vidro_mm", "origem": "especialista de domínio",
         "estado": EstadoConhecimento.PENDENTE.value},
    )
