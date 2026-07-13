"""
Sprint E.2 — traçado it3 das 9 seções da amostra (contorno_externo + vazios_internos).
It3 segue o feedback 02/03/04 do Bruno (verde = forma correta; azul = terminal
em "J" do SU-005; vermelho = erro da it2):
 - garras/trilhos usam o J APROVADO do GEO-SU-005 (transplantado do JSON):
   pendurado como no SU-005 (SU-024) e espelhado na vertical p/ trilhos
   (SU-025/228/230);
 - LG-003 refeito como calha (placa no fundo, paredes 14 com lábios p/ dentro,
   clips em pé, aleta recuada descendo 12);
 - SU-009: sem orelhas, parede de fechamento recuada p/ dentro;
 - SU-056: braço horizontal no lugar da barba, abas esquerdas mais longas,
   pé/lábio direitos removidos;
 - SU-280: puxador em cunha (fino na raiz, largo na ponta);
 - LG-006: ponte escalonada com clip, pé externo removido, lábios do topo
   mais curtos.
Orientação: card Alcoa (SU) / Gold 3 (LG). Paredes 1.6mm.
NÃO grava no JSON — só imagens para feedback.
"""
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union
from shapely.affinity import translate, scale as _scale

E = 1.6  # espessura de parede padrão

# ---------------------------------------------------------------------------
# Terminal em "J" aprovado no GEO-SU-005 (iteração 11, dados/geometrias.json,
# pontos 24-66 do contorno externo, rebaseados: haste externa em x=0, fundo
# do J em y=0). Haste à esquerda, bacia embaixo, ponta curta à direita
# subindo até y=6.4 — aberto em cima (J, não U invertido).
# ---------------------------------------------------------------------------
_J_BRUTO = [
    (54.22, 20.0), (53.979, 19.931), (53.832, 19.752), (53.8, 6.678),
    (54.211, 5.198), (53.677, 4.162), (53.604, 3.718), (53.637, 3.21),
    (53.768, 2.778), (54.046, 2.306), (54.406, 1.946), (54.789, 1.708),
    (55.31, 1.537), (55.818, 1.504), (56.262, 1.577), (56.733, 1.772),
    (57.377, 2.338), (57.755, 3.171), (57.779, 3.893), (57.509, 4.725),
    (57.6, 5.162), (57.633, 6.159), (57.793, 6.341), (58.029, 6.398),
    (58.421, 6.333), (58.894, 6.075), (59.191, 5.732), (59.388, 5.171),
    (59.4, 2.014), (59.325, 1.464), (59.096, 0.944), (58.687, 0.471),
    (57.99, 0.091), (57.386, 0.0), (54.214, 0.0), (53.664, 0.075),
    (53.144, 0.304), (52.709, 0.67), (52.275, 1.465), (52.2, 2.014),
    (52.2, 19.58), (52.131, 19.821), (51.952, 19.968),
]
J_TEMPLATE = Polygon([(x - 52.2, y) for x, y in _J_BRUTO])  # x 0..7.2, y 0..20
_J_CX_HASTE = 0.8   # centro da haste no template
_J_ALT = 20.0


def garra_j_pendurada(cx_haste, fundo=0.0, espelhar=False):
    """J do SU-005 pendurado (haste sobe até o deck ~y=20+fundo).
    espelhar=True: ponta para a esquerda (par espelhado, como no SU-005)."""
    g = J_TEMPLATE
    if espelhar:
        g = _scale(g, xfact=-1, yfact=1, origin=(_J_CX_HASTE, 0))
    return translate(g, xoff=cx_haste - _J_CX_HASTE, yoff=fundo)


def trilho_j(cx_haste, y_base_topo, cota_topo=19.1, espelhar=False):
    """J do SU-005 espelhado na vertical (trilho: haste sobe da base, bacia
    em cima, ponta curta descendo). Topo da bacia = y_base_topo + cota_topo;
    haste fura a base por ~0.9."""
    g = _scale(J_TEMPLATE, xfact=1, yfact=-1, origin=(0, _J_ALT / 2))  # y 0..20, bacia no topo
    if espelhar:
        g = _scale(g, xfact=-1, yfact=1, origin=(_J_CX_HASTE, 0))
    return translate(g, xoff=cx_haste - _J_CX_HASTE,
                     yoff=y_base_topo + cota_topo - _J_ALT)


def R(x0, y0, x1, y1):
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def clip_c(cx, cy, r_out=3.8, r_in=2.2, abertura="baixo", boca=2.4):
    """Clip redondo tipo ômega: anel com fresta apontando para `abertura`."""
    anel = Point(cx, cy).buffer(r_out, quad_segs=24).difference(
        Point(cx, cy).buffer(r_in, quad_segs=24))
    if abertura == "cima":
        fresta = R(cx - boca / 2, cy, cx + boca / 2, cy + r_out + 0.5)
    else:
        fresta = R(cx - boca / 2, cy - r_out - 0.5, cx + boca / 2, cy)
    return anel.difference(fresta)


def placa_inclinada(x0, x1, y0_esq, y0_dir, esp):
    return Polygon([(x0, y0_esq), (x1, y0_dir),
                    (x1, y0_dir + esp), (x0, y0_esq + esp)])


def suavizar(p, r=0.4):
    """Arredondamento de quinas no padrão do SU-005 (R_QUINA=0.4 via
    morfologia de buffer). Se colapsar em multi-partes, mantém o original."""
    q = p.buffer(r, join_style=1).buffer(-2 * r, join_style=1).buffer(
        r, join_style=1)
    return q if q.geom_type == "Polygon" else p


# ---------------------------------------------------------------------------
# SU-024 — Marco Superior / Correr / Veneziana Camarão (106 x 38.5)
# ---------------------------------------------------------------------------
def su024():
    partes = []
    # placa do gancho veneziana (mais curta) + aba esquerda com pezinho
    partes.append(R(0, 36.9, 16.9, 38.5))
    partes.append(R(0, 30.0, E, 38.5))
    partes.append(R(0, 30.0, 5.0, 31.6))
    # escada em Z (feedback 06): dois patamares até a vertical do deck
    partes.append(R(15.3, 31.0, 16.9, 36.9))
    partes.append(R(15.3, 31.0, 31.0, 32.6))
    partes.append(R(29.4, 27.7, 31.0, 31.0))
    partes.append(R(29.4, 27.7, 34.6, 29.3))
    partes.append(R(33.0, 0.0, 34.6, 29.3))
    # deck
    partes.append(R(33.0, 19.9, 106.0, 21.5))
    # garras em J penduradas (par espelhado como no SU-005)
    partes.append(garra_j_pendurada(53.0, espelhar=True))
    partes.append(garra_j_pendurada(88.0, espelhar=False))
    # parede direita inteira com lábio p/ esquerda no topo
    partes.append(R(104.4, 0.0, 106.0, 38.5))
    partes.append(R(101.5, 36.9, 106.0, 38.5))
    return suavizar(unary_union(partes))


# ---------------------------------------------------------------------------
# SU-025 — Marco Inferior / Correr / Veneziana Camarão (106 de largura)
# ---------------------------------------------------------------------------
def su025():
    partes = []
    # gancho veneziana inferior esquerdo
    partes.append(R(0, 0, 15.3, E))
    partes.append(R(0, 0, E, 8.5))
    partes.append(R(0, 6.9, 4.6, 8.5))
    # gancho interno (nervura p/ direita removida — feedback 08)
    partes.append(R(13.7, E, 15.3, 7.0))
    # escada de 2 degraus subindo ao deck (posições do verde)
    partes.append(R(13.7, 6.2, 29.0, 7.8))
    partes.append(R(27.4, 7.8, 29.0, 11.9))
    partes.append(R(27.4, 10.3, 32.0, 11.9))
    partes.append(R(30.4, 11.9, 32.0, 19.4))
    # deck inclinado raso
    partes.append(Polygon([(30.4, 17.8), (104.4, 20.4),
                           (104.4, 22.0), (30.4, 19.4)]))
    # trilhos em J sobre o deck (garra 1 espelhada — ponta p/ fora)
    for cx, esp in ((53.0, True), (88.0, False)):
        y_deck = 19.4 + (22.0 - 19.4) * (cx - 30.4) / (104.4 - 30.4)
        partes.append(trilho_j(cx, y_deck, cota_topo=17.0, espelhar=esp))
    # aleta direita: sobe a 53; embaixo desce 6 com jog p/ fora e mais 17
    partes.append(R(104.4, 14.0, 106.0, 53.0))
    partes.append(R(104.4, 12.4, 107.0, 14.0))
    partes.append(R(105.4, -4.6, 107.0, 12.4))
    return suavizar(unary_union(partes))


# ---------------------------------------------------------------------------
# SU-009 — Coluna para maxim-ar (caixa 69.6 x 26; fechamento recuado)
# ---------------------------------------------------------------------------
def su009():
    W = 69.6
    partes = []
    partes.append(R(0, 0, E, 26.0))                        # parede esquerda
    partes.append(R(0, 26.0 - E, W, 26.0))                 # teto até a ponta
    partes.append(R(0, 0, W, E))                           # fundo até a ponta
    partes.append(R(67.4, 0, 69.0, 26.0))                  # fechamento (recuado
    # ~2mm p/ trás, contra a aleta — feedback 08)
    # aleta em dois segmentos — o trecho entre as paredes foi removido
    # (linha de trás, feedback 05)
    partes.append(R(W - E, 24.4, W, 38.75))
    partes.append(R(W - E, -12.75, W, E))
    partes.append(clip_c(18.0, 26.0 - E - 2.4, r_out=2.8, r_in=1.6,
                         abertura="baixo", boca=2.2))
    partes.append(clip_c(53.0, E + 2.4, r_out=2.8, r_in=1.6,
                         abertura="cima", boca=2.2))
    return suavizar(unary_union(partes))


# ---------------------------------------------------------------------------
# SU-056 — Montante mão de amigo (38.9 x 25; braço porta-espiga horizontal)
# ---------------------------------------------------------------------------
def su056():
    W = 38.9
    partes = []
    partes.append(R(0, 0, W, E))                           # fundo
    # teto vazado entre os mastros (feedback 09) — a área entre eles abre
    # para a câmara principal
    partes.append(R(0, 25.0 - E, 22.2, 25.0))
    partes.append(R(27.2, 25.0 - E, W, 25.0))
    partes.append(R(35.5 - E, 0, 35.5, 25.0))              # parede direita interna
    partes.append(R(12.0, 0, 12.0 + E, 25.0))              # divisória em 12
    # ganchos esquerdos
    partes.append(R(0, 25.0 - E, 4.6, 25.0))
    partes.append(R(0, 19.5, E, 25.0))
    partes.append(R(0, 0, 4.6, E))
    partes.append(R(0, 0, E, 5.5))
    # zona superior refeita conforme azul (feedback 08): dois mastros com
    # travessa em H, lábios no topo formando canal, e espiga diagonal
    partes.append(R(20.6, 23.8, 22.2, 32.2))               # mastro 1 (sem lábio —
    # feedback 10)
    partes.append(R(27.2, 23.8, 28.8, 32.2))               # mastro 2
    partes.append(R(20.6, 27.2, 28.8, 28.8))               # travessa (desceu 1mm —
    # feedback 10)
    partes.append(R(26.6, 30.6, 28.8, 32.2))               # lábio mastro 2 p/ dentro
    partes.append(R(20.6, 30.6, 22.8, 32.2))               # lábio mastro 1 espelhado
    # (simétrico ao do mastro 2 em relação à fresta central — feedback 11)
    partes.append(Polygon([(14.0, 31.3), (14.6, 32.7),     # espiga diagonal
                           (21.3, 30.3), (20.7, 28.9)]))
    # aleta externa direita
    partes.append(R(W - E, 21.5, W, 32.5))
    # gancho p/ cima na ponta direita do fundo
    partes.append(R(W - E, 0, W, 4.0))
    return suavizar(unary_union(partes))


# ---------------------------------------------------------------------------
# SU-280 — Montante lateral / folha com puxador em cunha (55.2 x 64.8)
# ---------------------------------------------------------------------------
def su280():
    Wc = 25.6
    topo = 64.8
    partes = []
    partes.append(R(0, 0, E, topo))                        # parede esq. inteira
    partes.append(R(Wc - E, 11.5, Wc, topo))               # parede direita
    # bolsa de encaixe aberta no topo
    partes.append(R(0, topo - E, 6.0, topo))
    partes.append(R(4.4, topo - 3.8, 6.0, topo))
    partes.append(R(Wc - 6.0, topo - E, Wc, topo))
    partes.append(R(Wc - 6.0, topo - 3.8, Wc - 4.4, topo))
    partes.append(R(1.4, 54.2, 6.0, 55.8))                 # nervura esq.
    partes.append(R(Wc - 6.0, 54.2, Wc - 1.4, 55.8))       # nervura dir.
    # dentes verticais alinhados na prumada dos lábios do topo (espelho da
    # linha superior — feedback 09)
    partes.append(R(4.4, 54.2, 6.0, 57.4))
    partes.append(R(Wc - 6.0, 54.2, Wc - 4.4, 57.4))
    # topo da câmara fechada
    partes.append(R(0, 49.0, Wc, 50.6))
    # fundo escalonado da câmara
    partes.append(R(7.5, 15.5, Wc, 17.1))
    partes.append(R(5.9, 12.5, 7.5, 17.1))
    partes.append(R(0, 12.5, 7.5, 14.1))
    # puxador em cunha com ponta bem arredondada (pingadeira externa
    # removida — linha de trás, feedback 05)
    cunha = Polygon([(23.0, 13.5), (52.9, 15.0), (52.9, 10.4), (23.0, 11.9)])
    ponta = Point(52.9, 12.7).buffer(2.3, quad_segs=24)
    partes.append(cunha.union(ponta))
    return suavizar(unary_union(partes))


# ---------------------------------------------------------------------------
# SU-228 — Marco Inferior Porta de Correr / Correr 2 (68.2; parede 37.1)
# ---------------------------------------------------------------------------
def su228():
    W = 68.2
    partes = [placa_inclinada(0, W, 0, 2.2, E)]
    partes.append(R(0, -1.5, E, E))                        # pinguinho esq.
    # garra 1 espelhada (ponta p/ fora); pezinho até y=0 sob cada haste
    for cx, esp in ((16.6, True), (51.6, False)):
        y_base = E + 2.2 * cx / W
        partes.append(trilho_j(cx, y_base, espelhar=esp))
        partes.append(R(cx - 0.8, 0, cx + 0.8, 2.2 * cx / W + 0.6))
    partes.append(R(W - E, -2.3, W, 34.8))                 # parede direita 37.1
    return suavizar(unary_union(partes))


# ---------------------------------------------------------------------------
# SU-230 — Marco Inferior / Correr 3 (103.2; parede 37)
# ---------------------------------------------------------------------------
def su230():
    W = 103.2
    partes = [placa_inclinada(0, W, 0, 2.8, E)]
    # garras 1 e 2 espelhadas (azul); pezinho até y=0 sob cada haste (verde)
    for cx, esp in ((16.6, True), (51.6, True), (86.6, False)):
        y_base = E + 2.8 * cx / W
        partes.append(trilho_j(cx, y_base, espelhar=esp))
        partes.append(R(cx - 0.8, 0, cx + 0.8, 2.8 * cx / W + 0.6))
    partes.append(R(W - E, -2.5, W, 34.5))                 # parede direita 37
    return suavizar(unary_union(partes))


# ---------------------------------------------------------------------------
# LG-003 — Marco Bandeira / Peitoril Gold: CALHA (102.2; paredes 14)
# ---------------------------------------------------------------------------
def lg003():
    W = 102.2
    partes = []
    partes.append(R(0, -14.0, W, -12.4))                   # placa no fundo
    partes.append(R(0, -14.0, E, 0))                       # parede esquerda
    partes.append(R(0, -E, 5.0, 0))                        # lábio p/ dentro
    partes.append(R(W - E, -14.0, W, 0))                   # parede direita
    partes.append(R(96.6, -E, W, 0))                       # lábio p/ dentro
    partes.append(R(98.5, -26.0, 100.1, -12.4))            # aleta recuada desce 12
    for cx in (28.8, 73.4):                                # clips em pé na placa
        partes.append(clip_c(cx, -12.4 + 2.3, r_out=2.6, r_in=1.5,
                             abertura="cima", boca=2.0))
    return unary_union(partes)


# ---------------------------------------------------------------------------
# LG-006 — Folha Inferior/Superior Gold (28.5 x 56.3; ponte escalonada)
# ---------------------------------------------------------------------------
def lg006():
    W = 28.5
    topo = 56.3
    partes = []
    partes.append(R(0, 0, E, topo))                        # parede esq. 56.3
    partes.append(R(W - E, 15.0, W, topo))                 # parede dir. 41.3
    # ganchos de baguete no topo (lábios mais curtos que na it2)
    partes.append(R(0, topo - E, 5.6, topo))
    partes.append(R(4.0, topo - 3.5, 5.6, topo))
    partes.append(R(W - 5.6, topo - E, W, topo))
    partes.append(R(W - 5.6, topo - 3.5, W - 4.0, topo))
    # nervuras internas (par superior estendido até a prumada do lábio,
    # onde assenta o dente)
    partes.append(R(E, 46.5, 5.6, 48.1))
    partes.append(R(W - 5.6, 46.5, W - E, 48.1))
    partes.append(R(E, 35.0, 3.8, 36.6))
    partes.append(R(W - 3.8, 35.0, W - E, 36.6))
    # dentes verticais alinhados na prumada dos lábios do topo (espelho da
    # linha de cima — feedback 09)
    partes.append(R(4.0, 46.5, 5.6, 51.0))
    partes.append(R(W - 5.6, 46.5, W - 4.0, 51.0))
    # ponte escalonada: bancada baixa à esquerda + tampo com clip
    partes.append(R(1.4, 15.5, 6.0, 17.1))
    partes.append(R(4.4, 15.5, 6.0, 20.5))
    partes.append(R(4.4, 18.9, 27.1, 20.5))
    partes.append(clip_c(13.0, 20.5 + 2.4, r_out=3.0, r_in=1.7,
                         abertura="cima", boca=2.2))
    return unary_union(partes)


SECOES = {
    "GEO-SU-024": su024,
    "GEO-SU-025": su025,
    "GEO-SU-009": su009,
    "GEO-SU-056": su056,
    "GEO-SU-280": su280,
    "GEO-SU-228": su228,
    "GEO-SU-230": su230,
    "GEO-LG-003": lg003,
    "GEO-LG-006": lg006,
}


def contornos(poly):
    """Extrai (contorno_externo, vazios_internos) de um Polygon shapely."""
    if poly.geom_type != "Polygon":
        raise ValueError(f"seção não é um polígono único: {poly.geom_type} "
                         f"({len(poly.geoms)} partes)")
    ext = [(round(x, 2), round(y, 2)) for x, y in poly.exterior.coords[:-1]]
    vaz = [[(round(x, 2), round(y, 2)) for x, y in anel.coords[:-1]]
           for anel in poly.interiors]
    return ext, vaz
