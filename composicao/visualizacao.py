"""Cena de visualização ESQUEMÁTICA da Suprema de correr 2 folhas.

Este módulo NÃO calcula corte, folga, sobreposição ou vidro. Ele traduz a
topologia já confirmada (`receita.construir_receita_preliminar().componentes`,
E.4E) em posições e comprimentos de desenho — números que existem só para que
a cena tenha proporção reconhecível de janela, sem nenhuma relação com medida
de fabricação.

```text
topologia (papel, orientação, folha, posição)   já confirmado, E.4E
geometria (contorno de cada perfil)             já homologada, E.4C
posição/comprimento de desenho                  ILUSTRATIVO — este módulo
```

Nenhuma constante aqui deriva de caso real, fórmula candidata ou catálogo.
Trocar os valores muda a aparência do desenho, nunca uma regra de cálculo —
não existe regra de cálculo neste módulo para mudar.
"""
from __future__ import annotations

from domain.entidades import CenaTecnica, InstanciaCena

from .modelos import ComponenteReceita, PapelComponente
from .receita import PLANO_EXTERNO, PLANO_INTERNO, construir_receita_preliminar

# ---------------------------------------------------------------------------
# Dimensões ILUSTRATIVAS — não são vão, quadro, folha, corte nem catálogo.
# Escolhidas apenas para que o desenho tenha proporção reconhecível de janela.
# ---------------------------------------------------------------------------
LARGURA_ILUSTRATIVA_MM = 2000.0
ALTURA_ILUSTRATIVA_MM = 1200.0

# Vão livre entre as duas folhas onde SU-040/SU-041 se encontram — puramente
# de desenho, para que o "encontro central" seja visível como uma lacuna, não
# como uma sobreposição. Não é a sobreposição real (E.4E registra que ela é
# dimensional e segue PENDENTE).
#
# 60mm, não 40mm: a largura real da geometria homologada do SU-040/SU-041 é
# 42,4mm — com 40mm de folga as duas peças se sobrepunham em ~2,4mm em vez de
# deixar a lacuna visível que o comentário acima promete (achado da correção
# visual pós-validação do Bruno, PR #15).
FOLGA_ENCONTRO_CENTRAL_MM = 60.0

# Margem entre o baguete (moldura do vidro) e a face interna da folha —
# ilustrativa, não é a folga de encaixe do vidro (pergunta aberta ao
# especialista, ver receita.PERGUNTAS_ABERTAS).
MARGEM_BAGUETE_MM = 60.0

# Margem entre a face externa da folha (montante lateral / travessas) e o
# quadro (marco) — ilustrativa, escolhida para exceder a maior largura de
# perfil observada nesta composição (~71mm, SU-001/002/003), garantindo que
# a folha não desenhe por cima do quadro. Sem essa margem, SU-039 (montante
# lateral) e SU-053 (travessa) caíam exatamente nas mesmas coordenadas do
# marco e ficavam ocultos atrás dele (achado da correção visual pós-validação
# do Bruno, PR #15) — não é folga de encaixe real, é só separação de desenho.
MARGEM_FOLHA_QUADRO_MM = 90.0

_LARGURA_FOLHA = (LARGURA_ILUSTRATIVA_MM - FOLGA_ENCONTRO_CENTRAL_MM) / 2

# Posição X ilustrativa de cada folha (lado a lado, não sobrepostas — a
# sobreposição real de uma correr de 2 folhas é dimensional e não está
# confirmada; representar as folhas lado a lado, com uma lacuna no centro,
# evita fingir uma medida que não temos).
_X_INICIO_FOLHA = {
    PLANO_INTERNO: 0.0,
    PLANO_EXTERNO: _LARGURA_FOLHA + FOLGA_ENCONTRO_CENTRAL_MM,
}

# Dentro de cada folha, o montante central fica do lado do encontro (voltado
# para o centro da janela) e o montante lateral do lado de fora.
_LADO_DO_MONTANTE_CENTRAL = {PLANO_INTERNO: "direita", PLANO_EXTERNO: "esquerda"}

# Ordem de desenho dos 4 baguetes de uma folha (2 horizontais + 2 verticais).
# A arbitragem NÃO fixou qual baguete é o superior/inferior ou
# esquerdo/direito (receita._BAGUETES_DA_FOLHA: posicao=None em todos) — a
# ordem abaixo é só uma ESCOLHA DE DESENHO para não sobrepor as 4 peças no
# mesmo lugar, não uma afirmação de domínio.
_ORDEM_DE_DESENHO_DO_BAGUETE = {
    "BAGUETE-HORIZONTAL-1": "topo",
    "BAGUETE-HORIZONTAL-2": "base",
    "BAGUETE-VERTICAL-1": "esquerda",
    "BAGUETE-VERTICAL-2": "direita",
}


def _sufixo_do_componente(componente: ComponenteReceita) -> str:
    """Último segmento do identificador — ex. 'MONTANTE-CENTRAL',
    'BAGUETE-HORIZONTAL-1'. Usado só para saber qual baguete é qual, já que o
    papel sozinho (BAGUETE) não distingue os quatro de uma folha."""
    return componente.identificador.rsplit(":", 1)[-1]


def _posicao_e_comprimento(componente: ComponenteReceita) -> tuple[tuple[float, float], float]:
    """(posicao_mm, comprimento_mm) ilustrativos para UM componente da
    topologia confirmada. Lê só papel/orientação/folha/posição — nunca
    inventa um papel novo."""
    papel = componente.papel

    if papel is PapelComponente.MARCO_SUPERIOR:
        return (0.0, ALTURA_ILUSTRATIVA_MM), LARGURA_ILUSTRATIVA_MM
    if papel is PapelComponente.MARCO_INFERIOR:
        return (0.0, 0.0), LARGURA_ILUSTRATIVA_MM
    if papel is PapelComponente.MARCO_LATERAL:
        # As duas ocorrências são idênticas na topologia (lateral neutro,
        # E.4E) — o desenho as separa esquerda/direita só para não desenhar
        # as duas no mesmo lugar, sem que isso vire identidade de domínio.
        lado_x = 0.0 if componente.identificador.endswith("LATERAL-1") \
            else LARGURA_ILUSTRATIVA_MM
        return (lado_x, 0.0), ALTURA_ILUSTRATIVA_MM

    if componente.folha is None:
        raise ValueError(
            f"{componente.identificador}: papel de folha sem `folha` "
            f"definida — topologia mudou de forma que este módulo não prevê")
    x0 = _X_INICIO_FOLHA[componente.folha]

    if papel is PapelComponente.MONTANTE_LATERAL_FOLHA:
        # Recuado MARGEM_FOLHA_QUADRO_MM da face do quadro (ver comentário na
        # constante) — sem o recuo, cai exatamente sobre o marco lateral.
        lado = "esquerda" if _LADO_DO_MONTANTE_CENTRAL[componente.folha] == "direita" \
            else "direita"
        x = x0 + MARGEM_FOLHA_QUADRO_MM if lado == "esquerda" \
            else x0 + _LARGURA_FOLHA - MARGEM_FOLHA_QUADRO_MM
        return (x, 0.0), ALTURA_ILUSTRATIVA_MM
    if papel is PapelComponente.MONTANTE_CENTRAL_FOLHA:
        lado = _LADO_DO_MONTANTE_CENTRAL[componente.folha]
        x = x0 if lado == "esquerda" else x0 + _LARGURA_FOLHA
        return (x, 0.0), ALTURA_ILUSTRATIVA_MM
    if papel in (PapelComponente.TRAVESSA_SUPERIOR_FOLHA,
                PapelComponente.TRAVESSA_INFERIOR_FOLHA):
        # Recua só a ponta que toca o quadro (a ponta do encontro central já
        # tem folga suficiente via FOLGA_ENCONTRO_CENTRAL_MM) — mesmo motivo
        # do recuo do montante lateral, mesma constante.
        x_travessa = x0 + MARGEM_FOLHA_QUADRO_MM if componente.folha == PLANO_INTERNO else x0
        comprimento_travessa = _LARGURA_FOLHA - MARGEM_FOLHA_QUADRO_MM
        y = ALTURA_ILUSTRATIVA_MM if papel is PapelComponente.TRAVESSA_SUPERIOR_FOLHA else 0.0
        return (x_travessa, y), comprimento_travessa

    if papel is PapelComponente.BAGUETE:
        sufixo = _sufixo_do_componente(componente)
        lado = _ORDEM_DE_DESENHO_DO_BAGUETE[sufixo]
        x_vidro0 = x0 + MARGEM_BAGUETE_MM
        largura_vidro = _LARGURA_FOLHA - 2 * MARGEM_BAGUETE_MM
        y_vidro0 = MARGEM_BAGUETE_MM
        altura_vidro = ALTURA_ILUSTRATIVA_MM - 2 * MARGEM_BAGUETE_MM
        if lado == "topo":
            return (x_vidro0, y_vidro0 + altura_vidro), largura_vidro
        if lado == "base":
            return (x_vidro0, y_vidro0), largura_vidro
        if lado == "esquerda":
            return (x_vidro0, y_vidro0), altura_vidro
        return (x_vidro0 + largura_vidro, y_vidro0), altura_vidro

    raise ValueError(f"{componente.identificador}: papel {papel} sem regra "
                     f"de desenho neste módulo")


def _deve_espelhar(componente: ComponenteReceita) -> bool:
    """Perfis de esquadria não são simétricos (confirmado na geometria
    homologada de SU-003 e SU-102 — refletir o contorno produz uma forma
    mensuravelmente diferente da original, não a mesma peça). Um par visual
    esquerda/direita ou topo/base desenhado com a MESMA seção transversal nos
    dois lados deixa pelo menos um deles de cabeça para trás. Espelha-se
    sempre o segundo membro do par (LATERAL-2, base, direita), mantendo o
    primeiro (LATERAL-1, topo, esquerda) como referência não alterada.

    Achado da correção visual pós-validação do Bruno (PR #15): ele não
    conseguiu determinar visualmente qual dos dois sentidos é o correto para
    SU-003/SU-102 — esta é a escolha de desenho proposta para nova
    conferência, não uma afirmação de que está definitivamente certa."""
    papel = componente.papel
    if papel is PapelComponente.MARCO_LATERAL:
        return componente.identificador.endswith("LATERAL-2")
    if papel is PapelComponente.BAGUETE:
        sufixo = _sufixo_do_componente(componente)
        lado = _ORDEM_DE_DESENHO_DO_BAGUETE[sufixo]
        return lado in ("base", "direita")
    return False


def montar_cena_suprema_2f(receita=None) -> CenaTecnica:
    """Monta a Cena a partir da topologia JÁ CONFIRMADA — não deriva, não
    completa, não inventa ocorrência. Se a topologia mudar (novo papel, nova
    peça), este módulo levanta erro explícito em vez de desenhar algo errado.

    `receita=None` usa `construir_receita_preliminar()` — a mesma fonte que o
    gate de visualização já lê."""
    receita = receita or construir_receita_preliminar()
    instancias = []
    for c in receita.componentes:
        posicao_mm, comprimento_mm = _posicao_e_comprimento(c)
        rotacao_graus = 90.0 if c.orientacao == "vertical" else 0.0
        if _deve_espelhar(c):
            rotacao_graus += 180.0
        instancias.append(InstanciaCena(
            instancia_id=c.identificador,
            perfil_id=c.perfil.perfil_id_oficial,
            posicao_mm=posicao_mm,
            rotacao_graus=rotacao_graus,
            comprimento_mm=comprimento_mm,
        ))
    return CenaTecnica(id=f"{receita.codigo}:CENA-ILUSTRATIVA",
                       tipo_id=receita.codigo, instancias=instancias)
