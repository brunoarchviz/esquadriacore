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

RECONSTRUÇÃO PÓS-VALIDAÇÃO VISUAL DO BRUNO
A primeira versão desta cena posicionava cada peça a partir de MARGENS
ilustrativas fixas (folga central, margem folha↔quadro, margem do baguete).
O efeito colateral só ficou visível quando Bruno montou a composição na
viewport: com margens, nenhuma peça encosta em nenhuma outra, e o conjunto
inteiro lê como "peças curtas" — travessa que não fecha a folha, baguete
flutuando no meio do vidro, montante que não alcança o marco.

A regra mudou: **as peças são posicionadas pelas próprias faces, para se
encontrarem**. Nenhuma margem arbitrária sobrou. O que define onde cada peça
começa e termina é a face da peça vizinha, medida na geometria homologada —
não um número escolhido para "ficar bonito".

Três achados empíricos do diagnóstico, todos confirmados na cena anterior:

```text
SU-003        ia só até y=1200, mas o SU-001 vai até 1233 — não alcançava a
              extremidade do trilho superior (Bruno)
folhas        ambas em z≈0, coplanares: duas folhas de uma correr NÃO podem
              se sobrepor se estiverem no mesmo plano, e é por isso que "um
              dos lados ficaria sempre aberto"
travessas     SU-053 superior em y=[1200,1251], por CIMA do trilho, fora do
              vão
```

O que continua ILUSTRATIVO e não é medida de fabricação: as dimensões do
envelope (2000×1200), a profundidade de cada plano de folha, e a decisão de
que a sobreposição central vale a largura do montante central. Trocar esses
valores muda a aparência do desenho, nunca uma regra de cálculo — não existe
regra de cálculo neste módulo para mudar.
"""
from __future__ import annotations

import numpy as np

from core_engine.renderer import _pontos_no_mundo
from domain.entidades import CenaTecnica, InstanciaCena

from .modelos import ComponenteReceita, PapelComponente
from .receita import PLANO_EXTERNO, PLANO_INTERNO, construir_receita_preliminar

# ---------------------------------------------------------------------------
# Envelope ILUSTRATIVO — não é vão, quadro, folha, corte nem catálogo.
# Ancorado no SU-002: Bruno validou o trilho inferior exatamente onde estava
# e pediu que ele fosse a referência fixa; tudo abaixo é medido a partir dele.
# ---------------------------------------------------------------------------
LARGURA_ILUSTRATIVA_MM = 2000.0
ALTURA_ILUSTRATIVA_MM = 1200.0

# Profundidade (Z) em que a face frontal de cada folha começa. As duas folhas
# de uma correr vivem em planos distintos — sem isso elas não podem correr uma
# sobre a outra, e a composição não fecha de jeito nenhum. Os dois valores
# cabem dentro da profundidade do marco (71mm, medida em SU-001/SU-002) e são
# de desenho: a distância real entre planos é dimensional e segue PENDENTE.
Z_DA_FOLHA = {PLANO_INTERNO: 6.0, PLANO_EXTERNO: 38.0}

# Recuo do baguete dentro do plano da própria folha — só para ele não brigar
# em Z com o montante que o segura.
Z_RECUO_DO_BAGUETE_MM = 4.0

# ---------------------------------------------------------------------------
# Orientação de cada peça, em ângulos do frame local (rx, ry, rz).
#
# NÃO HÁ ESPELHAMENTO em lugar nenhum, e isso é uma decisão de domínio, não
# de estilo: uma barra extrudada não pode ser espelhada no mundo físico —
# precisaria de outra matriz de extrusão. Um par esquerda/direita da mesma
# barra é sempre a MESMA seção girada 180° em torno do próprio eixo. Foi
# exatamente essa a correção que Bruno fez no SU-003 na viewport (trocou o
# espelho por rotação), e ela foi generalizada para todos os pares.
#
# SU-003: os ângulos vieram da validação visual do Bruno. Eles rolam o perfil
# 90° em torno do próprio eixo, e o efeito é que o marco lateral passa a ter
# 26mm de largura e 71mm de profundidade — a MESMA profundidade dos trilhos
# SU-001/SU-002. Na versão anterior ele estava deitado (71 de largura, 26 de
# profundidade) e o quadro não tinha profundidade coerente.
# ---------------------------------------------------------------------------
ORIENTACAO = {
    "QUADRO-SUPERIOR": (0, 0, 0),
    "QUADRO-INFERIOR": (0, 0, 0),
    "QUADRO-LATERAL-1": (180, 0, 90),
    "QUADRO-LATERAL-2": (0, 0, 90),
    "MONTANTE-CENTRAL": (90, 0, 90),
    "TRAVESSA-INFERIOR": (0, 0, 0),
    "TRAVESSA-SUPERIOR": (180, 0, 0),
    "BAGUETE-HORIZONTAL-1": (180, 0, 0),
    "BAGUETE-HORIZONTAL-2": (0, 0, 0),
    "BAGUETE-VERTICAL-1": (90, 0, 90),
    "BAGUETE-VERTICAL-2": (270, 0, 90),
}
# O montante lateral é o único que depende da folha: os dois são a mesma
# barra em lados opostos, logo giram 180° um em relação ao outro.
ORIENTACAO_MONTANTE_LATERAL = {PLANO_INTERNO: (90, 0, 90),
                               PLANO_EXTERNO: (270, 0, 90)}


def _sufixo(componente: ComponenteReceita) -> str:
    return componente.identificador.rsplit(":", 1)[-1]


def _orientacao(componente: ComponenteReceita) -> tuple[float, float, float]:
    if componente.papel is PapelComponente.MONTANTE_LATERAL_FOLHA:
        return ORIENTACAO_MONTANTE_LATERAL[componente.folha]
    return ORIENTACAO[_sufixo(componente)]


# ---------------------------------------------------------------------------
# Medida da seção NO MUNDO
#
# A pergunta que a montagem faz o tempo todo é "quanto esta peça ocupa em X,
# depois de girada?". Responder isso lendo a bounding box do catálogo daria a
# resposta errada assim que a peça fosse rolada — foi esse o erro que deixou o
# marco lateral com a profundidade trocada. Aqui a resposta vem da MESMA
# função que o renderer usa para desenhar, então o que a montagem calcula e o
# que aparece na imagem não podem divergir.
# ---------------------------------------------------------------------------

def _secao_no_mundo(contorno, rotacao_xyz) -> dict:
    pts = _pontos_no_mundo(contorno, 0.0, 0.0, (0.0, 0.0), rotacao_xyz, 0.0)
    return {eixo: (float(pts[:, i].min()), float(pts[:, i].max()))
            for i, eixo in enumerate("xyz")}


def _deslocamento(secao: dict, eixo: str, face: float, encostar: str) -> float:
    """Translação que põe a face pedida da peça exatamente em `face`."""
    minimo, maximo = secao[eixo]
    return face - (minimo if encostar == "inicio" else maximo)


class _Montagem:
    """Monta a cena medindo cada peça pela vizinha, nunca por margem fixa."""

    def __init__(self, receita):
        self.receita = receita
        self.secoes = {}
        for c in receita.componentes:
            rot = _orientacao(c)
            chave = (c.perfil.perfil_id_oficial, rot)
            if chave not in self.secoes:
                self.secoes[chave] = _secao_no_mundo(
                    _contorno_de(c.perfil.perfil_id_oficial), rot)
        self._calcular()

    def secao(self, componente):
        return self.secoes[(componente.perfil.perfil_id_oficial,
                            _orientacao(componente))]

    # -- geometria derivada, toda a partir do SU-002 -----------------------
    def _calcular(self):
        comp = {_sufixo(c): c for c in self.receita.componentes}
        L, H = LARGURA_ILUSTRATIVA_MM, ALTURA_ILUSTRATIVA_MM

        # Quadro: SU-001 e SU-002 ficam onde Bruno validou. O envelope é o que
        # eles descrevem, e não um número escolhido à parte.
        self.topo_do_quadro = H + self.secao(comp["QUADRO-SUPERIOR"])["y"][1]
        self.vao_y = (self.secao(comp["QUADRO-INFERIOR"])["y"][1],  # topo do SU-002
                      H)                                           # base do SU-001

        # O marco lateral vai do fundo até a extremidade do trilho superior:
        # Bruno mostrou que ele deve alcançar o topo do SU-001 e passar o
        # trilho, para o parafuso entrar no olhal (o "J invertido").
        self.altura_do_lateral = self.topo_do_quadro
        larg_lateral = _largura(self.secao(comp["QUADRO-LATERAL-1"]), "x")
        self.vao_x = (larg_lateral, L - larg_lateral)

        # Folhas: a sobreposição central vale a largura do montante central,
        # de modo que SU-040 e SU-041 ocupem a MESMA faixa em X e se cruzem
        # em planos diferentes — é assim que a mão de amigo lê como encaixe,
        # e não como duas peças separadas por uma lacuna.
        self.sobreposicao = _largura(self.secao(comp["MONTANTE-CENTRAL"]), "x")
        vao_livre = self.vao_x[1] - self.vao_x[0]
        self.largura_da_folha = (vao_livre + self.sobreposicao) / 2
        self.x_da_folha = {
            PLANO_INTERNO: (self.vao_x[0], self.vao_x[0] + self.largura_da_folha),
            PLANO_EXTERNO: (self.vao_x[1] - self.largura_da_folha, self.vao_x[1]),
        }
        self.altura_da_folha = self.vao_y[1] - self.vao_y[0]
        self.larg_montante_lateral = _largura(
            self.secao(comp["MONTANTE-LATERAL"]), "x")
        self.altura_da_travessa = _largura(
            self.secao(comp["TRAVESSA-INFERIOR"]), "y")

    def vao_da_folha_x(self, folha):
        """Faixa X entre as faces internas dos DOIS montantes da folha — é
        onde a travessa começa e termina, e onde o vidro (e o baguete) cabe."""
        x0, x1 = self.x_da_folha[folha]
        if folha is PLANO_INTERNO:
            return (x0 + self.larg_montante_lateral, x1 - self.sobreposicao)
        return (x0 + self.sobreposicao, x1 - self.larg_montante_lateral)

    def vao_da_folha_y(self):
        """Faixa Y entre as faces internas das duas travessas."""
        return (self.vao_y[0] + self.altura_da_travessa,
                self.vao_y[1] - self.altura_da_travessa)

    def montante_lateral_x(self, folha):
        """Faixa X ocupada pelo montante lateral da folha."""
        x0, x1 = self.x_da_folha[folha]
        larg = self.larg_montante_lateral
        return (x0, x0 + larg) if folha is PLANO_INTERNO else (x1 - larg, x1)

    def montante_central_x(self):
        """A MESMA faixa para os dois planos — é o encontro central."""
        x0, x1 = self.x_da_folha[PLANO_INTERNO]
        return (x1 - self.sobreposicao, x1)


def _largura(secao, eixo):
    return secao[eixo][1] - secao[eixo][0]


_CONTORNOS: dict = {}


def _contorno_de(perfil_id: str):
    """Contorno homologado do perfil, via contrato de consumo. Em cache: a
    montagem consulta a mesma seção muitas vezes."""
    if perfil_id not in _CONTORNOS:
        from contrato.consumo import carregar_biblioteca
        bib = carregar_biblioteca()
        assoc = next(a for a in bib.associacoes if a.perfil_id == perfil_id)
        geo = bib.geometria(assoc.geometria_padrao_id)
        _CONTORNOS[perfil_id] = geo.contorno_externo
    return _CONTORNOS[perfil_id]


def _posicao_e_comprimento(componente: ComponenteReceita, m: _Montagem):
    """(x, y, z, comprimento) de UM componente, tudo medido pelas faces das
    peças vizinhas. Lê só papel/orientação/folha — nunca inventa um papel."""
    papel = componente.papel
    sec = m.secao(componente)
    sufixo = _sufixo(componente)

    if papel in (PapelComponente.MARCO_SUPERIOR, PapelComponente.MARCO_INFERIOR):
        # Referência fixa de Bruno: os dois trilhos ficam exatamente onde
        # estavam. Alterá-los invalidaria a validação visual já feita.
        y = ALTURA_ILUSTRATIVA_MM if papel is PapelComponente.MARCO_SUPERIOR else 0.0
        return (0.0, y, 0.0), LARGURA_ILUSTRATIVA_MM

    if papel is PapelComponente.MARCO_LATERAL:
        primeiro = sufixo.endswith("LATERAL-1")
        face = 0.0 if primeiro else LARGURA_ILUSTRATIVA_MM
        x = _deslocamento(sec, "x", face, "inicio" if primeiro else "fim")
        z = _deslocamento(sec, "z", 0.0, "inicio")
        return (x, 0.0, z), m.altura_do_lateral

    if componente.folha is None:
        raise ValueError(
            f"{componente.identificador}: papel de folha sem `folha` "
            f"definida — topologia mudou de forma que este módulo não prevê")
    z_folha = Z_DA_FOLHA[componente.folha]

    if papel is PapelComponente.MONTANTE_LATERAL_FOLHA:
        faixa = m.montante_lateral_x(componente.folha)
        x = _deslocamento(sec, "x", faixa[0], "inicio")
        z = _deslocamento(sec, "z", z_folha, "inicio")
        return (x, m.vao_y[0], z), m.altura_da_folha

    if papel is PapelComponente.MONTANTE_CENTRAL_FOLHA:
        faixa = m.montante_central_x()
        x = _deslocamento(sec, "x", faixa[0], "inicio")
        z = _deslocamento(sec, "z", z_folha, "inicio")
        return (x, m.vao_y[0], z), m.altura_da_folha

    if papel in (PapelComponente.TRAVESSA_SUPERIOR_FOLHA,
                 PapelComponente.TRAVESSA_INFERIOR_FOLHA):
        # A travessa vai de montante a montante: as faces internas dos dois
        # verticais da folha, e nada mais. É o que fecha a folha.
        x0, x1 = m.vao_da_folha_x(componente.folha)
        superior = papel is PapelComponente.TRAVESSA_SUPERIOR_FOLHA
        y = _deslocamento(sec, "y", m.vao_y[1] if superior else m.vao_y[0],
                          "fim" if superior else "inicio")
        z = _deslocamento(sec, "z", z_folha, "inicio")
        return (_deslocamento(sec, "x", x0, "inicio"), y, z), x1 - x0

    if papel is PapelComponente.BAGUETE:
        x0, x1 = m.vao_da_folha_x(componente.folha)
        y0, y1 = m.vao_da_folha_y()
        z = _deslocamento(sec, "z", z_folha + Z_RECUO_DO_BAGUETE_MM, "inicio")
        if sufixo.startswith("BAGUETE-HORIZONTAL"):
            topo = sufixo.endswith("-1")
            y = _deslocamento(sec, "y", y1 if topo else y0,
                              "fim" if topo else "inicio")
            return (_deslocamento(sec, "x", x0, "inicio"), y, z), x1 - x0
        esquerda = sufixo.endswith("-1")
        x = _deslocamento(sec, "x", x0 if esquerda else x1,
                          "inicio" if esquerda else "fim")
        return (x, y0, z), y1 - y0

    raise ValueError(f"{componente.identificador}: papel {papel} sem regra "
                     f"de desenho neste módulo")


def montar_cena_suprema_2f(receita=None) -> CenaTecnica:
    """Monta a Cena a partir da topologia JÁ CONFIRMADA — não deriva, não
    completa, não inventa ocorrência. Se a topologia mudar (novo papel, nova
    peça), este módulo levanta erro explícito em vez de desenhar algo errado.

    `receita=None` usa `construir_receita_preliminar()` — a mesma fonte que o
    gate de visualização já lê."""
    receita = receita or construir_receita_preliminar()
    m = _Montagem(receita)
    instancias = []
    for c in receita.componentes:
        (x, y, z), comprimento = _posicao_e_comprimento(c, m)
        rot = _orientacao(c)
        instancias.append(InstanciaCena(
            instancia_id=c.identificador,
            perfil_id=c.perfil.perfil_id_oficial,
            posicao_mm=(x, y),
            rotacao_graus=90.0 if c.orientacao == "vertical" else 0.0,
            comprimento_mm=comprimento,
            rotacao_xyz=rot,
            posicao_z_mm=z,
        ))
    return CenaTecnica(id=f"{receita.codigo}:CENA-ILUSTRATIVA",
                       tipo_id=receita.codigo, instancias=instancias)
