"""Receita preliminar da Janela Suprema de correr com duas folhas.

Esta receita sabe **onde cada perfil fica**, e nada além disso:

- quais oito perfis oficiais estão disponíveis;
- que ocorrência funcional cada perfil cumpre — quadro, folha interna, folha
  externa, baguete — conforme ARBITRAGEM do especialista (E.4E), cujas
  evidências primárias ainda não foram ingeridas no repositório;
- que os dois montantes centrais se ENCONTRAM, como relação entre duas peças;
- quais regras dimensionais precisam existir um dia — todas `PENDENTE`,
  todas com `expressao=None`.

Topologia não é cálculo. Nenhuma medida, folga, desconto, sobreposição ou
fórmula foi escrita: saber que o SU-040 é o montante central da folha interna
não diz de quantos milímetros ele é cortado.
"""
from __future__ import annotations

from .fontes import PERFIS_SUPREMA_E4C, referencia_oficial
from .modelos import (ESTADO_RECEITA_PRELIMINAR, ITENS_DE_ACESSORIO_BASE,
                      ComponenteReceita, EstadoConhecimento, FonteEvidencia,
                      PapelComponente, ReceitaTipologia, RegraAcessorio,
                      RegraDimensional, RelacaoEntreComponentes,
                      TipoRelacaoComponentes)

CODIGO_TIPOLOGIA = "SUPREMA_CORRER_2F"
NOME_TIPOLOGIA = "Janela Suprema de correr com duas folhas"
SISTEMA = "Suprema"
QUANTIDADE_FOLHAS = 2

# As duas folhas móveis, cada uma no seu trilho. Interno e externo é relação
# QUALITATIVA: nenhuma distância entre planos é afirmada. "Folha esquerda" e
# "folha direita" ficariam erradas na primeira janela espelhada.
# PLANO_INTERNO: plano da folha mais próximo do ambiente INTERNO da edificação.
# PLANO_EXTERNO: plano da folha mais próximo do EXTERIOR da edificação.
# É profundidade da esquadria em relação a dentro/fora do edifício — não é
# esquerda/direita, não é o lado de quem olha a foto, não é sentido de abertura.
# Por isso a convenção sobrevive ao espelhamento: espelhar troca lados, não
# troca qual folha está mais perto de dentro.
PLANO_INTERNO = "PLANO_INTERNO"
PLANO_EXTERNO = "PLANO_EXTERNO"
PLANOS_DAS_FOLHAS = (PLANO_INTERNO, PLANO_EXTERNO)

# A única coisa CONFIRMADA nesta rodada: que os oito perfis existem na
# biblioteca oficial, promovidos e auditados no E.4C.
#
# O manifesto NÃO é catálogo nem tabela de fabricação — chamá-lo assim daria a
# entender que ele diz algo sobre corte ou montagem. Ele é o registro do evento
# de promoção, e prova exatamente duas coisas: que os oito perfis existem na
# biblioteca oficial, e que os IDs GEO e as associações estão aprovados.
FONTE_PROMOCAO_E4C = FonteEvidencia(
    id_fonte="FONTE-MANIFESTO-E4C",
    tipo="manifesto_promocao",
    referencia="curadoria/promocoes/e4c/manifesto_promocao_e4b.json",
    descricao=("Promoção oficial E.4C: oito geometrias e oito associações "
               "ALCOA-SU-xxx na biblioteca. PROVA: os perfis existem, com IDs "
               "e associações aprovados. NÃO PROVA: papel na janela, "
               "quantidade, orientação, corte, vidro ou acessório."),
    estado=EstadoConhecimento.CONFIRMADO_BIBLIOTECA_OFICIAL,
    data="2026-08-02",
    # O manifesto é artefato IMUTÁVEL do evento E.4C: o hash fica registrado
    # para que qualquer alteração posterior seja detectada. Calculado uma vez e
    # fixado aqui — o modelo não toca no filesystem.
    sha256="0b68ef5783e0a8fc0626c00eef8b9dcc2a643baa92adb0871799ab2590ddc0c7",
    tamanho_bytes=11072,
)

# REGISTRO DERIVADO DE ARBITRAGEM — não é evidência física primária.
#
# O documento apontado aqui é o registro escrito de uma decisão de especialista.
# `especialista_de_dominio` é o tipo mais honesto que o contrato oferece: ele
# afirma "um especialista decidiu", não "existe foto provando". Não há tipo de
# arbitragem no vocabulário, e ampliar o schema de fontes só para batizar esta
# fonte seria trocar precisão de rótulo por dívida de modelo.
#
# O sha256 abaixo prova a INTEGRIDADE DO DOCUMENTO e quais decisões ele
# registra. Não prova que o SU-001 está no quadro superior de uma janela real:
# um arquivo íntegro pode registrar uma decisão errada.
#
# As evidências primárias que originaram a arbitragem — três janelas físicas,
# o quadro da Grande sem folhas, ficha de campo, fotografias e os benchmarks
# externos — NÃO estão no repositório e NÃO foram ingeridas. Nenhum path, hash
# ou id_fonte foi criado para elas: fabricar esses registros faria a receita
# parecer lastreada em prova física quando está lastreada em decisão.
FONTE_TOPOLOGIA_E4E = FonteEvidencia(
    id_fonte="FONTE-TOPOLOGIA-E4E",
    tipo="especialista_de_dominio",
    referencia="curadoria/handoffs/e4e/topologia_suprema_2f.md",
    descricao=("REGISTRO DERIVADO DE ARBITRAGEM DE DOMÍNIO, não evidência "
               "física primária. Registra a decisão do especialista sobre a "
               "topologia da Suprema de correr 2 folhas: papel e plano de "
               "cada ocorrência, e o encontro central como relação entre o "
               "montante da folha interna e o da folha externa. O hash prova "
               "a integridade DESTE documento e quais decisões ele registra — "
               "não prova a composição física de nenhuma janela. Evidências "
               "primárias (três janelas reais, quadro sem folhas, ficha de "
               "campo, fotografias, benchmarks externos): PENDENTE DE "
               "INGESTÃO DAS EVIDÊNCIAS PRIMÁRIAS — ausentes do repositório, "
               "sem path, sem hash e sem id_fonte nesta rodada. NÃO PROVA: "
               "comprimento de corte, folga, vidro ou acessório."),
    estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
    responsavel="Bruno",
    data="2026-08-09",
    sha256="a2134ed8c1c01c9e4f6b78ecb783cb1804dd64a16556f2273d47b7f7f68fcd45",
    tamanho_bytes=8607,
)

# ---------------------------------------------------------------------------
# Topologia: ocorrências funcionais
# ---------------------------------------------------------------------------
# (identificador, perfil, papel, orientação, folha, posição)
#
# Um perfil pode aparecer em várias ocorrências, e a ocorrência é que é única.
# SU-003 entra duas vezes com o MESMO papel neutro `MARCO_LATERAL` — gravar
# esquerda/direita amarraria a receita a um lado, e ela precisa ser espelhável.
# SU-053 entra quatro vezes; SU-102, oito.
_QUADRO = (
    ("QUADRO-SUPERIOR", "SU-001", PapelComponente.MARCO_SUPERIOR,
     "horizontal", None, "superior"),
    ("QUADRO-INFERIOR", "SU-002", PapelComponente.MARCO_INFERIOR,
     "horizontal", None, "inferior"),
    ("QUADRO-LATERAL-1", "SU-003", PapelComponente.MARCO_LATERAL,
     "vertical", None, "lateral"),
    ("QUADRO-LATERAL-2", "SU-003", PapelComponente.MARCO_LATERAL,
     "vertical", None, "lateral"),
)

# As duas folhas têm a MESMA composição estrutural; o que as distingue é o
# montante central — SU-040 na interna, SU-041 na externa (os perfis "mão de
# amigo", que são montantes, não ferragem).
_MONTANTE_CENTRAL_DA_FOLHA = {
    PLANO_INTERNO: "SU-040",
    PLANO_EXTERNO: "SU-041",
}

_ESTRUTURA_DA_FOLHA = (
    ("MONTANTE-LATERAL", "SU-039", PapelComponente.MONTANTE_LATERAL_FOLHA,
     "vertical", "lateral"),
    ("MONTANTE-CENTRAL", None, PapelComponente.MONTANTE_CENTRAL_FOLHA,
     "vertical", "central"),
    ("TRAVESSA-SUPERIOR", "SU-053", PapelComponente.TRAVESSA_SUPERIOR_FOLHA,
     "horizontal", "superior"),
    ("TRAVESSA-INFERIOR", "SU-053", PapelComponente.TRAVESSA_INFERIOR_FOLHA,
     "horizontal", "inferior"),
)

# O baguete prende o vidro; não faz parte do quadro estrutural da folha. Fica
# distinguível pelo papel `BAGUETE`, para que contar peças estruturais não
# passe a incluir acabamento.
#
# A arbitragem estabeleceu UMA coisa: 2 horizontais + 2 verticais por folha.
# Os sufixos -1 e -2 desambiguam ocorrências e nada mais. Ler HORIZONTAL-1 como
# "superior" ou VERTICAL-1 como "esquerda" seria inventar identidade que a
# arbitragem não fixou — e que a ingestão das primárias ainda pode contradizer.
# Por isso `posicao` fica None: não declarar é mais honesto que declarar errado.
_BAGUETES_DA_FOLHA = (
    ("BAGUETE-HORIZONTAL-1", "horizontal", None),
    ("BAGUETE-HORIZONTAL-2", "horizontal", None),
    ("BAGUETE-VERTICAL-1", "vertical", None),
    ("BAGUETE-VERTICAL-2", "vertical", None),
)

_SUFIXO_DA_FOLHA = {PLANO_INTERNO: "FOLHA-INTERNA",
                    PLANO_EXTERNO: "FOLHA-EXTERNA"}

ID_MONTANTE_CENTRAL = {
    plano: f"{CODIGO_TIPOLOGIA}:{_SUFIXO_DA_FOLHA[plano]}:MONTANTE-CENTRAL"
    for plano in PLANOS_DAS_FOLHAS
}


def _componente(sufixo, codigo_perfil, papel, orientacao, folha, posicao):
    """Uma ocorrência funcional confirmada em posição — e só em posição."""
    return ComponenteReceita(
        identificador=f"{CODIGO_TIPOLOGIA}:{sufixo}",
        perfil=referencia_oficial(codigo_perfil),
        papel=papel,
        quantidade=1,                       # uma peça por ocorrência
        orientacao=orientacao,
        folha=folha,
        posicao=posicao,
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        fontes=(FONTE_TOPOLOGIA_E4E,),
    )


def _componentes_da_topologia() -> tuple[ComponenteReceita, ...]:
    itens = [_componente(*linha) for linha in _QUADRO]
    for plano in PLANOS_DAS_FOLHAS:
        prefixo = _SUFIXO_DA_FOLHA[plano]
        for sufixo, perfil, papel, orientacao, posicao in _ESTRUTURA_DA_FOLHA:
            itens.append(_componente(
                f"{prefixo}:{sufixo}",
                perfil or _MONTANTE_CENTRAL_DA_FOLHA[plano],
                papel, orientacao, plano, posicao))
        for sufixo, orientacao, posicao in _BAGUETES_DA_FOLHA:
            itens.append(_componente(f"{prefixo}:{sufixo}", "SU-102",
                                     PapelComponente.BAGUETE, orientacao,
                                     plano, posicao))
    return tuple(itens)


def _relacoes_da_topologia() -> tuple[RelacaoEntreComponentes, ...]:
    """O encontro central é uma RELAÇÃO, não uma peça.

    São dois montantes, um em cada folha, cada um no seu plano. Não existe
    terceira peça, e nenhuma das duas tem "encontro" como papel."""
    return (RelacaoEntreComponentes(
        tipo=TipoRelacaoComponentes.ENCONTRO_CENTRAL,
        participantes=(ID_MONTANTE_CENTRAL[PLANO_INTERNO],
                       ID_MONTANTE_CENTRAL[PLANO_EXTERNO]),
        estado=EstadoConhecimento.CONFIRMADO_ESPECIALISTA,
        fontes=(FONTE_TOPOLOGIA_E4E,),
        observacao=("Montantes centrais das duas folhas se encontram no fecho. "
                    "A sobreposição entre eles é dimensional e segue PENDENTE."),
    ),)


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

# Respondidas em E.4E e removidas daqui: qual perfil cumpre cada papel, em
# quantas ocorrências, com que orientação, e qual folha corre em cada plano.
# Continuam abertas todas as perguntas DIMENSIONAIS.
PERGUNTAS_ABERTAS = (
    "Qual o desconto de corte de cada perfil em relação à medida de vão?",
    "Quais as folgas de montagem entre folha e marco, e entre as duas folhas?",
    "Qual a sobreposição no encontro central?",
    "Como o vidro é dimensionado a partir da folha (folga de encaixe, calços)?",
    "Que acessórios entram (roldanas, fecho, contra-fecho, escovas, vedações, "
    "fixações), em que quantidade e em que posição?",
    "As evidências primárias (três janelas reais, quadro sem folhas, ficha de "
    "campo, fotografias, benchmarks) ainda NÃO foram ingeridas: a topologia "
    "está lastreada em arbitragem de domínio, não em artefato verificado no "
    "repositório. Confirmam a topologia quando forem ingeridas?",
    "Qual baguete de cada par horizontal/vertical é o superior e qual o "
    "inferior — e isso chega a importar para corte?",
    "Onde fica o fecho e qual o sentido de movimento de cada folha?",
    "O corte de cada peça é reto ou em 45°, e em quais extremidades?",
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
        descricao=f"Quantidade e posição de {item} na janela",
        quantidade_expressao=None,
        posicao=None,
        estado=EstadoConhecimento.PENDENTE,
        fontes=(),
    )


def construir_receita_preliminar() -> ReceitaTipologia:
    """Receita preliminar — determinística e sem efeito colateral.

    Não lê disco, não altera nada, e duas chamadas produzem receitas iguais."""
    regras_corte = tuple(_regra_pendente(a, d, "corte") for a, d in ALVOS_DE_CORTE)
    regras_vidro = tuple(_regra_pendente(a, d, "vidro") for a, d in ALVOS_DE_VIDRO)
    return ReceitaTipologia(
        codigo=CODIGO_TIPOLOGIA,
        nome=NOME_TIPOLOGIA,
        sistema=SISTEMA,
        quantidade_folhas=QUANTIDADE_FOLHAS,
        # INVENTÁRIO: os oito perfis disponíveis para a tipologia.
        # OCORRÊNCIAS: onde cada um entra. Um perfil não é uma peça — SU-003
        # aparece duas vezes, SU-053 quatro, SU-102 oito.
        perfis_disponiveis=tuple(referencia_oficial(c)
                                 for c in PERFIS_SUPREMA_E4C),
        componentes=_componentes_da_topologia(),
        relacoes=_relacoes_da_topologia(),
        regras_corte=regras_corte,
        regras_vidro=regras_vidro,
        regras_acessorios=tuple(_regra_acessorio_pendente(i)
                                for i in ITENS_DE_ACESSORIO_BASE),
        casos_reais=(),
        fontes=(FONTE_PROMOCAO_E4C, FONTE_TOPOLOGIA_E4E),
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
