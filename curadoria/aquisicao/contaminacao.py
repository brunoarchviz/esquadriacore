"""
Detecção de CONTAMINAÇÃO GRÁFICA CONECTADA ao componente do perfil.

Motivo (SU-039, 26/07/2026): a linha de cota "8.2" encostou no montante e
entrou no maior componente conectado. Os três gates de aquisição passaram —
F1 = 1,0000, aspecto 0,05%, topologia correta — porque:

  - F1 compara a máscara com a rasterização do contorno extraído DELA MESMA:
    se a cota está na máscara, está nos dois lados da conta;
  - o aspecto não muda: a seta fica dentro do bounding box;
  - a topologia não muda: a cota não cria nem fecha vazio.

Este módulo fecha essa lacuna. Ele é um DETECTOR DE SUSPEITA que BLOQUEIA —
nunca um removedor universal de setas. A remoção é localizada, transacional,
reversível e sempre barrada por zona de motivo confirmado.

Assinatura da contaminação (evidência medida no SU-039):
    parede principal   mediana ≈ 0,932 mm
    linha de chamada   ≈ 0,17 mm × 6,95 mm  (fina E longa)
    resíduo fino       ≈ 0,46% da máscara
Esses números são do caso SU-039. Aqui viram razões relativas à parede do
próprio perfil, com tolerância — nunca limites absolutos universais.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Suspeita:
    """Candidato a contaminação. NUNCA é removido automaticamente."""
    indice: int
    tipo: str                      # 'linha_de_chamada' | 'massa_associada'
    espessura_mm: float
    comprimento_mm: float
    razao_parede: float            # espessura / mediana da parede
    area_mm2: float
    centro_mm: tuple
    bbox_mm: tuple
    em_zona_protegida: bool
    motivos_atingidos: list = field(default_factory=list)
    mascara: np.ndarray | None = None

    def resumo(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "mascara"}


def espessura_mediana_mm(mascara: np.ndarray, px_mm: float) -> float:
    """Espessura local mediana da parede (2× a distance transform)."""
    dt = cv2.distanceTransform(mascara.astype(np.uint8), cv2.DIST_L2, 5)
    return float(np.median(2 * dt[mascara > 0]) / px_mm)


def _zonas_para_mascara(zonas_mm, forma, px_mm, altura_mm) -> np.ndarray:
    z = np.zeros(forma, bool)
    for x0, y0, x1, y1 in (zonas_mm or []):
        c0, c1 = int(x0 * px_mm), int(np.ceil(x1 * px_mm))
        r0 = int((altura_mm - y1) * px_mm)
        r1 = int(np.ceil((altura_mm - y0) * px_mm))
        z[max(0, r0):max(0, r1), max(0, c0):max(0, c1)] = True
    return z


def detectar(mascara: np.ndarray, px_mm: float, altura_mm: float,
             zonas_protegidas=None, motivos=None,
             razao_fina_max: float = 0.35,
             comprimento_min_mm: float = 2.0,
             alongamento_min: float = 6.0) -> list[Suspeita]:
    """Traços finos E longos conectados ao componente.

    `razao_fina_max` é relativo à parede DO PRÓPRIO perfil: um traço com menos
    de 35% da espessura mediana já destoa. `alongamento_min` separa a linha de
    chamada (muito comprida para a espessura) de um lábio ou serrilha, que são
    finos mas curtos.
    """
    mediana = espessura_mediana_mm(mascara, px_mm)
    limite_px = max(1, int(round(razao_fina_max * mediana * px_mm / 2)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * limite_px + 1,) * 2)
    nucleo = cv2.morphologyEx(mascara.astype(np.uint8), cv2.MORPH_OPEN, k)
    fino = ((mascara > 0) & (cv2.dilate(nucleo, k) == 0)).astype(np.uint8)

    zonas = _zonas_para_mascara(zonas_protegidas, mascara.shape, px_mm, altura_mm)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(fino, 8)
    suspeitas = []
    for i in range(1, n):
        P = (lab == i)
        area_px = int(stats[i, cv2.CC_STAT_AREA])
        w = stats[i, cv2.CC_STAT_WIDTH] / px_mm
        h = stats[i, cv2.CC_STAT_HEIGHT] / px_mm
        comprimento = max(w, h)
        dt = cv2.distanceTransform(P.astype(np.uint8), cv2.DIST_L2, 5)
        espessura = float(2 * dt.max() / px_mm)
        if espessura <= 0:
            continue
        if comprimento < comprimento_min_mm:
            continue                       # curto: lábio, serrilha, degrau
        if comprimento / espessura < alongamento_min:
            continue                       # não é traço de chamada
        atinge = bool((P & zonas).any())
        x0 = stats[i, cv2.CC_STAT_LEFT] / px_mm
        y1 = altura_mm - stats[i, cv2.CC_STAT_TOP] / px_mm
        suspeitas.append(Suspeita(
            indice=len(suspeitas) + 1, tipo="linha_de_chamada",
            espessura_mm=round(espessura, 3),
            comprimento_mm=round(comprimento, 2),
            razao_parede=round(espessura / mediana, 3),
            area_mm2=round(area_px / px_mm ** 2, 2),
            centro_mm=(round(cent[i][0] / px_mm, 2),
                       round(altura_mm - cent[i][1] / px_mm, 2)),
            bbox_mm=(round(x0, 2), round(y1 - h, 2), round(x0 + w, 2), round(y1, 2)),
            em_zona_protegida=atinge,
            motivos_atingidos=list(motivos or []) if atinge else [],
            mascara=P))
    return suspeitas


def massa_associada(mascara: np.ndarray, suspeita: Suspeita, px_mm: float,
                    alcance_mm: float = 1.2) -> np.ndarray:
    """Massa compacta na extremidade da linha de chamada — a ponta de seta.

    A seta é SÓLIDA: sobrevive à análise de espessura e não aparece no resíduo
    fino. Só é alcançável partindo da linha de chamada, que é o discriminante.
    """
    r = max(2, int(alcance_mm * px_mm))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2)
    vizinhanca = cv2.dilate(suspeita.mascara.astype(np.uint8), k) > 0
    return (vizinhanca & (mascara > 0) & ~suspeita.mascara)


def eh_contorno_de_referencia(suspeita: Suspeita, largura_mm: float,
                              altura_mm: float, fracao_min: float = 0.30) -> bool:
    """Traço fino EXTENSO = outro perfil desenhado como referência de aplicação,
    não linha de cota.

    Distinção obrigatória (arbitragem do Bruno): a linha de cota é um traço
    isolado apontando para o perfil; o contorno de referência percorre uma
    fração grande do card nos DOIS eixos, porque é a silhueta inteira de outro
    perfil. Os dois encaminham para tratamentos diferentes — remoção local
    versus separação por espessura.
    """
    x0, y0, x1, y1 = suspeita.bbox_mm
    return ((x1 - x0) >= fracao_min * largura_mm
            and (y1 - y0) >= fracao_min * altura_mm)


def gate(mascara: np.ndarray, px_mm: float, altura_mm: float,
         zonas_protegidas=None, motivos=None,
         largura_mm: float | None = None) -> tuple[str | None, list]:
    """Estados possíveis:

    BLOQUEADO_CONTAMINACAO_GRAFICA_CONECTADA
        linha de cota / seta grudada no perfil → remoção LOCAL e transacional.
    CONTORNO_REFERENCIA_OUTRO_PERFIL_DETECTADO
        outro perfil desenhado em linha fina → SEPARAÇÃO POR ESPESSURA,
        preservando as duas camadas como evidência. Nunca remoção local.

    Bloqueia; não remove. Suspeita que toque zona de motivo confirmado exige
    ARBITRAGEM — jamais remoção automática.
    """
    s = detectar(mascara, px_mm, altura_mm, zonas_protegidas, motivos)
    if not s:
        return None, []
    if largura_mm is not None:
        for x in s:
            if eh_contorno_de_referencia(x, largura_mm, altura_mm):
                x.tipo = "contorno_referencia"
        if any(x.tipo == "contorno_referencia" for x in s):
            return "CONTORNO_REFERENCIA_OUTRO_PERFIL_DETECTADO", s
    return "BLOQUEADO_CONTAMINACAO_GRAFICA_CONECTADA", s


def remover_local(mascara: np.ndarray, suspeita: Suspeita, px_mm: float,
                  folga_mm: float = 0.4, largura_max_mm: float = 6.0):
    """Remove a linha de chamada e a massa associada, reconstruindo a parede
    pela continuidade dos trechos legítimos imediatamente antes e depois.

    Subtrair a seta e parar abriria entalhe na parede. Por isso a face é
    restaurada a partir das linhas vizinhas não contaminadas.
    """
    marcada = (suspeita.mascara | massa_associada(mascara, suspeita, px_mm))
    ys, xs = np.nonzero(marcada)
    r0, r1 = int(ys.min()), int(ys.max())
    c0, c1 = int(xs.min()), int(xs.max())
    folga = max(2, int(folga_mm * px_mm))
    largura_max = int(largura_max_mm * px_mm)
    vertical = (r1 - r0) >= (c1 - c0)

    # Não basta subtrair a seta: ela é sólida e o resto do corpo escapa da
    # análise de espessura (foi o que aconteceu no SU-039 — sobraram 1,68 mm²
    # de ponta de seta). Em vez de segmentar a seta, o trecho contaminado é
    # RECONSTRUÍDO pela continuação da parede legítima: as linhas logo antes e
    # logo depois do trecho definem o perfil correto da parede, e tudo que
    # ultrapassa esse perfil dentro da janela é contaminação.
    limpa = (mascara > 0).copy()
    if vertical:
        antes = max(0, r0 - folga)
        depois = min(mascara.shape[0] - 1, r1 + folga)
        if not (limpa[antes].any() and limpa[depois].any()):
            return (mascara > 0).astype(np.uint8), marcada
        ref = limpa[antes] & limpa[depois]        # só o que persiste nos dois
        jan = _divergencia(limpa[r0:r1 + 1], ref, c0, c1, folga, largura_max)
        for y in range(r0, r1 + 1):
            limpa[y, jan] = ref[jan]
    else:
        antes = max(0, c0 - folga)
        depois = min(mascara.shape[1] - 1, c1 + folga)
        if not (limpa[:, antes].any() and limpa[:, depois].any()):
            return (mascara > 0).astype(np.uint8), marcada
        ref = limpa[:, antes] & limpa[:, depois]
        jan = _divergencia(limpa[:, c0:c1 + 1].T, ref, r0, r1, folga, largura_max)
        for x in range(c0, c1 + 1):
            limpa[jan, x] = ref[jan]
    contaminacao = (mascara > 0) & ~limpa
    return limpa.astype(np.uint8), contaminacao


def _janela(tamanho: int, a: int, b: int, folga: int) -> np.ndarray:
    """Restringe a reconstrução à vizinhança do trecho contaminado."""
    j = np.zeros(tamanho, bool)
    j[max(0, a - folga):min(tamanho, b + folga + 1)] = True
    return j


def _divergencia(faixa: np.ndarray, ref: np.ndarray, a: int, b: int,
                 folga: int, largura_max: int) -> np.ndarray:
    """Janela de reconstrução definida pelo que DIVERGE da parede de referência.

    A ponta de seta é sólida e pode ficar longe da linha de chamada — no SU-039
    o corpo dela estava 2,4 mm adiante, fora de qualquer janela derivada só do
    traço fino. Aqui a janela cobre exatamente as colunas em que as linhas do
    trecho têm material que a parede de referência não tem.
    """
    protuberancia = (faixa & ~ref[None, :]).any(axis=0)
    if not protuberancia.any():
        return _janela(len(ref), a, b, folga)
    idx = np.nonzero(protuberancia)[0]
    ini, fim = int(idx.min()), int(idx.max())
    ini = min(ini, a); fim = max(fim, b)
    if fim - ini > largura_max:               # divergência larga demais:
        fim = ini + largura_max               # não é seta, não alargar às cegas
    return _janela(len(ref), ini, fim, folga)


# ---------------------------------------------------------------------------
# Escolha do TRATAMENTO pela topologia da CONEXÃO
#
# SU-039 e SU-024 provaram duas famílias distintas. O tratamento é escolhido
# medindo a conexão, nunca pelo código do perfil:
#
#   APÊNDICE COM TIRANTE FINO (SU-024) — bloco gráfico fora do perfil, preso
#       por tirante estreito. Quebrar a ponte o separa em componente próprio.
#       Tratamento: corte, seleção do principal, dilatação, interseção.
#       Aplicar aqui o tratamento de parede custou 11,9% da máscara.
#
#   ADERIDA À PAREDE (SU-039) — seta encostada na face, conexão larga. Não se
#       desprende por corte simples; erodir abre defeito na parede.
#       Tratamento: reconstrução local pela continuidade da parede legítima.
#
# Sem confiança suficiente: CONTAMINACAO_AMBIGUA → painel numerado e arbitragem.
# ---------------------------------------------------------------------------

APENDICE = "CONTAMINACAO_APENDICE_TIRANTE_FINO"
ADERIDA = "CONTAMINACAO_ADERIDA_PAREDE"
AMBIGUA = "CONTAMINACAO_AMBIGUA"
LIMPO = "LIMPO"


def classificar_conexao(mascara: np.ndarray, suspeita: Suspeita, px_mm: float,
                        altura_mm: float, zonas_protegidas=None,
                        fracao_principal_min: float = 0.90) -> tuple[str, dict]:
    """Mede a conexão e devolve (estado, evidência). Não altera nada."""
    ev: dict = {"espessura_tirante_mm": suspeita.espessura_mm,
                "parede_mediana_mm": round(espessura_mediana_mm(mascara, px_mm), 3)}
    if suspeita.em_zona_protegida:
        ev["motivo"] = ("a suspeita intersecta motivo confirmado — remoção "
                        "automática proibida")
        return AMBIGUA, ev

    # tentativa CONTROLADA de quebra: raio derivado do próprio tirante
    r = max(1, int(round(0.75 * suspeita.espessura_mm * px_mm / 2)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2)
    ero = cv2.erode(mascara.astype(np.uint8), k)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ero, 8)
    ev["raio_quebra_mm"] = round(r / px_mm, 3)
    ev["componentes_apos_quebra"] = int(n - 1)
    if n <= 1:
        ev["motivo"] = "a erosão dissolveu o componente"
        return AMBIGUA, ev

    maior = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    principal = cv2.dilate((lab == maior).astype(np.uint8), k) & (mascara > 0)
    fracao = float(principal.sum()) / float(max(1, (mascara > 0).sum()))
    ev["fracao_principal"] = round(fracao, 4)

    # a suspeita saiu junto com o descarte?
    sobrou = float((suspeita.mascara & (principal > 0)).sum()) / \
        float(max(1, suspeita.mascara.sum()))
    ev["fracao_suspeita_remanescente"] = round(sobrou, 4)

    if sobrou < 0.25 and fracao >= fracao_principal_min:
        ev["motivo"] = ("a quebra do tirante separou a contaminação e o "
                        "componente principal permaneceu íntegro")
        return APENDICE, ev

    # continua colada: existe parede legítima antes e depois?
    ys, xs = np.nonzero(suspeita.mascara)
    vertical = (ys.max() - ys.min()) >= (xs.max() - xs.min())
    folga = max(2, int(0.4 * px_mm))
    if vertical:
        a, b = max(0, ys.min() - folga), min(mascara.shape[0] - 1, ys.max() + folga)
        continua = bool(mascara[a].any() and mascara[b].any())
    else:
        a, b = max(0, xs.min() - folga), min(mascara.shape[1] - 1, xs.max() + folga)
        continua = bool(mascara[:, a].any() and mascara[:, b].any())
    ev["parede_continua_antes_e_depois"] = continua
    largura_conexao = suspeita.espessura_mm / max(ev["parede_mediana_mm"], 1e-6)
    ev["razao_conexao_parede"] = round(largura_conexao, 3)
    if continua and suspeita.comprimento_mm <= 0.5 * mascara.shape[1] / px_mm:
        ev["motivo"] = ("permanece conectada após a quebra e há parede legítima "
                        "contínua antes e depois: reconstrução local")
        return ADERIDA, ev
    ev["motivo"] = "conexão não classificável com segurança"
    return AMBIGUA, ev


def restaurar_zonas(original: np.ndarray, tratada: np.ndarray, px_mm: float,
                    altura_mm: float, zonas_protegidas) -> np.ndarray:
    """Devolve as zonas de motivo confirmado byte a byte da máscara original.
    O motivo fica idêntico por construção, não por sorte."""
    saida = tratada.copy()
    for x0, y0, x1, y1 in (zonas_protegidas or []):
        sl = (slice(max(0, int((altura_mm - y1) * px_mm)),
                    max(0, int((altura_mm - y0) * px_mm))),
              slice(max(0, int(x0 * px_mm)), max(0, int(x1 * px_mm))))
        saida[sl] = original[sl]
    return saida


def cortar_apendice(mascara: np.ndarray, suspeita: Suspeita, px_mm: float):
    """Rompe o tirante e descarta o bloco gráfico, sem deixar a dilatação
    reintroduzir o que já foi identificado como apêndice."""
    r = max(1, int(round(0.75 * suspeita.espessura_mm * px_mm / 2)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2)
    ero = cv2.erode(mascara.astype(np.uint8), k)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ero, 8)
    maior = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    outros = (lab > 0) & (lab != maior)
    # PROCEDÊNCIA: massa que a quebra atribuiu ao apêndice gráfico
    nao_reintroduzir = (cv2.dilate(outros.astype(np.uint8), k) > 0) & (mascara > 0)
    limpa = ((cv2.dilate((lab == maior).astype(np.uint8), k) > 0)
             & (mascara > 0) & ~nao_reintroduzir).astype(np.uint8)
    return limpa, nao_reintroduzir


def tratar(mascara: np.ndarray, suspeita: Suspeita, px_mm: float,
           altura_mm: float, zonas_protegidas=None):
    """Classifica a conexão e aplica o tratamento correspondente.

    Devolve (estado, mascara_tratada | None, contaminacao | None, evidencia).
    Em AMBIGUA nada é alterado: o caso vai para painel numerado e arbitragem.
    """
    estado, ev = classificar_conexao(mascara, suspeita, px_mm, altura_mm,
                                     zonas_protegidas)
    if estado == AMBIGUA:
        return estado, None, None, ev
    if estado == APENDICE:
        limpa, cont = cortar_apendice(mascara, suspeita, px_mm)
    else:
        limpa, cont = remover_local(mascara, suspeita, px_mm)
    limpa = restaurar_zonas(mascara, limpa, px_mm, altura_mm, zonas_protegidas)
    cont = (mascara > 0) & (limpa == 0)
    return estado, limpa, cont, ev


# ---------------------------------------------------------------------------
# ORQUESTRADOR — estratégias ORDENADAS, escolha pelo RESULTADO
#
# Não há duas famílias geométricas comprovadas. Há um problema geral —
# contaminação gráfica conectada — e estratégias tentadas da menos invasiva
# para a mais invasiva, cada uma validada e revertida se não fechar:
#
#   1. QUEBRA_CONTROLADA_DE_PONTE     (raio derivado da espessura medida)
#   2. RECONSTRUCAO_LOCAL_DA_PAREDE   (fallback, não família confirmada)
#   3. BLOQUEIO_PARA_ARBITRAGEM
#
# A classificação prévia da conexão vira DIAGNÓSTICO, não decisão. O que
# manda é o resíduo: no SU-039 o corte deixa 6 px de seta e por isso é
# REJEITADO, mesmo com o gate geral retornando LIMPO.
# ---------------------------------------------------------------------------

QUEBRA = "QUEBRA_CONTROLADA_DE_PONTE"
RECONSTRUCAO = "RECONSTRUCAO_LOCAL_DA_PAREDE"
BLOQUEIO = "BLOQUEIO_PARA_ARBITRAGEM"


def _face_legitima(mascara, suspeita, px_mm, folga_mm=0.4):
    """Continuação esperada da face da parede através do trecho contaminado.

    Derivada da PRÓPRIA parede: direção, face válida antes e depois do trecho,
    e a continuação dessa face pela região tratada.
    """
    ys, xs = np.nonzero(suspeita.mascara)
    r0, r1 = int(ys.min()), int(ys.max())
    c0, c1 = int(xs.min()), int(xs.max())
    folga = max(2, int(folga_mm * px_mm))
    vertical = (r1 - r0) >= (c1 - c0)
    if vertical:
        a = max(0, r0 - folga); b = min(mascara.shape[0] - 1, r1 + folga)
        return True, (r0, r1), ((mascara[a] > 0) & (mascara[b] > 0))
    a = max(0, c0 - folga); b = min(mascara.shape[1] - 1, c1 + folga)
    return False, (c0, c1), ((mascara[:, a] > 0) & (mascara[:, b] > 0))


def gate_residuo(original: np.ndarray, tratada: np.ndarray,
                 suspeita: Suspeita, px_mm: float,
                 tolerancia_px: int = 2,
                 procedencia: np.ndarray | None = None) -> tuple[int, np.ndarray]:
    """GATE_RESIDUO_CONTAMINACAO — material remanescente ALÉM da face legítima.

    A versão anterior media dentro de `suspeita.mascara ∪ massa_associada`, com
    alcance fixo de 1,2 mm: no SU-039 isso não alcançava o corpo da seta e o
    gate reportava 0 px onde havia 6. A referência agora é geométrica — a
    continuação da face válida da parede —, então qualquer caco de apêndice
    além dela conta, esteja onde estiver.
    """
    # Resíduo = pixels DA MASSA SUSPEITA que sobreviveram. A referência é a
    # procedência da contaminação, nunca uma face de parede reconstruída: a
    # interseção das paredes vizinhas contava material legítimo como resíduo
    # (3.699 px no SU-039, 5.800 no SU-024, todos falsos).
    if procedencia is None:
        procedencia = (suspeita.mascara
                       | massa_associada(original, suspeita, px_mm))
    residuo = np.asarray(procedencia, bool) & (np.asarray(tratada) > 0)
    # descarta cacos de discretização não conectados ao contorno final
    n, lab, st, _ = cv2.connectedComponentsWithStats(
        residuo.astype(np.uint8), 8)
    total = 0
    manter = np.zeros_like(residuo)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > tolerancia_px:
            total += int(st[i, cv2.CC_STAT_AREA])
            manter |= (lab == i)
    return total, manter


# ---------------------------------------------------------------------------
# GATE LOCAL DA FACE DENTRO DA TRANSAÇÃO
#
# O validador da face participa da aceitação de CADA tentativa, não de uma
# conferência posterior. No SU-039 a quebra da ponte zera a procedência mas
# deixa 6 px além da face e rompe a continuidade: fora da transação, o
# orquestrador aceitava a quebra e nunca chegava à reconstrução.
#
# Este bloco só TRADUZ o veredito do validador em estado de gate. A formulação
# geométrica de `validar_face_local` está congelada e não é reaberta aqui.
# ---------------------------------------------------------------------------

FACE_NAO_APLICAVEL = "NAO_APLICAVEL"
FACE_APROVADO = "APROVADO"
FACE_REJEITADO = "REJEITADO"
FACE_AMBIGUO = "AMBIGUO"
FACE_ORIENTACAO_NAO_SUPORTADA = "ORIENTACAO_NAO_SUPORTADA"

# Só estes dois deixam a tentativa seguir. AMBIGUO e ORIENTACAO_NAO_SUPORTADA
# não podem ser compensados por outro gate: terminam em arbitragem.
FACE_ESTADOS_QUE_ACEITAM = (FACE_NAO_APLICAVEL, FACE_APROVADO)

def _traducao_face() -> dict:
    """AMBIGUA_FACE e NAO_SUPORTADA são definidos junto do validador, mais
    abaixo no módulo; a tradução é montada no uso para não inverter a ordem
    de leitura do arquivo."""
    return {"ok": FACE_APROVADO, "rejeitado": FACE_REJEITADO,
            AMBIGUA_FACE: FACE_AMBIGUO,
            NAO_SUPORTADA: FACE_ORIENTACAO_NAO_SUPORTADA}


# `NAO_APLICAVEL` só existe onde a contaminação é apêndice EXTERNO desprendido
# por quebra de ponte — não há parede local a reconstruir nem a validar. Numa
# reconstrução de parede existe face por definição, e dispensar o validador ali
# seria justamente reabrir o buraco que o SU-039 expôs.
ESTRATEGIAS_QUE_ADMITEM_NAO_APLICAVEL = (QUEBRA,)


def gate_face(original, tratada, suspeita, px_mm, contexto_face=None,
              estrategia=None) -> dict:
    """Traduz o validador local da face em estado de gate transacional.

    `contexto_face` é explícito e imutável — sem global e sem estado de sessão.
    `NAO_APLICAVEL` exige justificativa registrada E estratégia compatível:
    ausência de justificativa faz o validador rodar, estratégia incompatível
    invalida a dispensa, e veredito imprevisto BLOQUEIA.
    """
    ctx = dict(contexto_face or {})
    justificativa = ctx.get("nao_aplicavel_justificativa")
    if justificativa:
        if estrategia not in ESTRATEGIAS_QUE_ADMITEM_NAO_APLICAVEL:
            return {"estado": "NAO_APLICAVEL_INVALIDO", "aprovado": False,
                    "estrategia": estrategia,
                    "motivo": (f"a dispensa da face só vale em "
                               f"{list(ESTRATEGIAS_QUE_ADMITEM_NAO_APLICAVEL)}; "
                               f"em {estrategia!r} existe face e o gate é "
                               f"obrigatório")}
        return {"estado": FACE_NAO_APLICAVEL, "aprovado": True,
                "estrategia": estrategia,
                "justificativa": str(justificativa)}
    estado, rel = validar_face_local(original, tratada, suspeita, px_mm)
    traduzido = _traducao_face().get(estado)
    if traduzido is None:                  # veredito desconhecido: bloqueia
        return {"estado": "AUSENTE", "aprovado": False,
                "motivo": f"validador devolveu estado não previsto: {estado!r}"}
    g = {"estado": traduzido,
         "aprovado": traduzido in FACE_ESTADOS_QUE_ACEITAM,
         "pixels_alem_da_face": rel.get("pixels_alem_da_face"),
         "continuidade": rel.get("continuidade_da_face"),
         "regra_quantizacao": rel.get("regra_quantizacao"),
         "limite_discreto_px": rel.get("limite_discreto_px"),
         "motivo": rel.get("motivo")}
    if traduzido == FACE_ORIENTACAO_NAO_SUPORTADA:
        g["orientacao_detectada"] = rel.get("orientacao_detectada")
    return g


def _validar_tentativa(original, tratada, suspeita, px_mm, altura_mm,
                       zonas_protegidas, largura_mm,
                       largura_esperada_mm=None, altura_esperada_mm=None,
                       tol_mm: float = 0.10, procedencia=None,
                       contexto_face=None, estrategia=None) -> tuple[bool, dict]:
    n, _ = cv2.connectedComponents(np.asarray(tratada, np.uint8), 8)
    residuo, _ = gate_residuo(original, tratada, suspeita, px_mm,
                              procedencia=procedencia)
    g_face = gate_face(original, tratada, suspeita, px_mm, contexto_face,
                       estrategia=estrategia)
    face_ok = bool(g_face.get("aprovado"))
    zonas_ok = all(
        np.array_equal(
            original[max(0, int((altura_mm - z[3]) * px_mm)):max(0, int((altura_mm - z[1]) * px_mm)),
                     max(0, int(z[0] * px_mm)):max(0, int(z[2] * px_mm))],
            tratada[max(0, int((altura_mm - z[3]) * px_mm)):max(0, int((altura_mm - z[1]) * px_mm)),
                    max(0, int(z[0] * px_mm)):max(0, int(z[2] * px_mm))])
        for z in (zonas_protegidas or []))
    # Dimensão contra a COTA DO CATÁLOGO, nunca contra o bbox contaminado: o
    # bbox encolhe legitimamente quando a anotação se projeta para fora do
    # perfil (foi o que reprovou o SU-024 indevidamente).
    ys1, xs1 = np.nonzero(tratada)
    larg = (xs1.max() - xs1.min() + 1) / px_mm
    alt = (ys1.max() - ys1.min() + 1) / px_mm
    if largura_esperada_mm is None or altura_esperada_mm is None:
        dim_ok = False
        dim_motivo = ("sem evidência dimensional do catálogo — arbitragem "
                      "necessária, proibido reutilizar o bbox contaminado")
    else:
        dim_ok = (abs(larg - largura_esperada_mm) <= tol_mm
                  and abs(alt - altura_esperada_mm) <= tol_mm)
        dim_motivo = "" if dim_ok else (
            f"dimensão {larg:.2f}×{alt:.2f} ≠ esperada "
            f"{largura_esperada_mm}×{altura_esperada_mm} (±{tol_mm})")
    adicionados = int((np.asarray(tratada) > 0).sum() - ((original > 0) & (np.asarray(tratada) > 0)).sum())
    rel = {"componentes": int(n - 1),
           "gate_procedencia": {"pixels_residuais": residuo,
                                "aprovado": residuo == 0},
           "gate_face": g_face,
           "pixels_residuais": residuo,
           "zonas_protegidas_byte_identicas": bool(zonas_ok),
           "dimensoes_esperadas_mm": [largura_esperada_mm, altura_esperada_mm],
           "dimensoes_obtidas_mm": [round(larg, 2), round(alt, 2)],
           "dimensoes_ok": bool(dim_ok),
           "pixels_adicionados": adicionados,
           "pixels_removidos": int(original.sum()) - int(np.asarray(tratada).sum())}
    # CONJUNÇÃO: procedência zerada NÃO basta. O gate da face entra aqui, junto
    # dos demais, para que a rejeição aconteça ANTES do rollback e da estratégia
    # seguinte — foi o acoplamento que faltava no SU-039.
    aceita = (n - 1 == 1 and residuo == 0 and zonas_ok and dim_ok and face_ok)
    rel["aceita"] = aceita
    rel["motivo"] = ("todos os critérios atendidos" if aceita else
                     "; ".join(filter(None, [
                         f"{n-1} componentes" if n - 1 != 1 else "",
                         f"{residuo} px de contaminação além da face legítima"
                         if residuo else "",
                         "" if zonas_ok else "zona protegida alterada",
                         dim_motivo,
                         "" if face_ok else
                         f"gate local da face {g_face['estado']}: "
                         f"{g_face.get('motivo')}"])))
    return aceita, rel


def tratar_contaminacao(mascara: np.ndarray, suspeita: Suspeita, px_mm: float,
                        altura_mm: float, largura_mm: float,
                        zonas_protegidas=None,
                        largura_esperada_mm=None, altura_esperada_mm=None,
                        contexto_face=None):
    """Orquestrador. Devolve (estrategia, mascara | None, log_transacional).

    Cada tentativa é uma transação: parte SEMPRE da máscara original, valida e
    é aceita ou revertida. Tentativa rejeitada nunca contamina a seguinte.

    Não duplica gate geométrico: quem decide se uma tentativa pode ser aceita é
    `_validar_tentativa`, gate da face incluído.
    """
    diagnostico = classificar_conexao(mascara, suspeita, px_mm, altura_mm,
                                      zonas_protegidas)[1]
    log = [{"etapa": "diagnostico", "dados": diagnostico}]
    if suspeita.em_zona_protegida:
        log.append({"estrategia": BLOQUEIO, "aceita": False,
                    "motivo": "suspeita intersecta motivo confirmado"})
        return BLOQUEIO, None, log

    for estrategia, funcao in ((QUEBRA, cortar_apendice),
                               (RECONSTRUCAO, remover_local)):
        tentativa, proc = funcao(mascara, suspeita, px_mm)  # da ORIGINAL
        tentativa = restaurar_zonas(mascara, np.asarray(tentativa, np.uint8),
                                    px_mm, altura_mm, zonas_protegidas)
        aceita, rel = _validar_tentativa(
            mascara, tentativa, suspeita, px_mm, altura_mm, zonas_protegidas,
            largura_mm, largura_esperada_mm, altura_esperada_mm,
            procedencia=proc, contexto_face=contexto_face,
            estrategia=estrategia)
        rel["estrategia"] = estrategia
        rel["rollback"] = {"realizado": not aceita}
        log.append(rel)
        if aceita:
            return estrategia, tentativa, log
        # face ambígua ou orientação sem evidência: a geometria não foi
        # compreendida. Escalar para uma estratégia MAIS invasiva sobre
        # geometria não compreendida é pior que parar.
        if rel["gate_face"]["estado"] in (FACE_AMBIGUO,
                                          FACE_ORIENTACAO_NAO_SUPORTADA,
                                          "AUSENTE", "NAO_APLICAVEL_INVALIDO"):
            log.append({"estrategia": BLOQUEIO, "aceita": False,
                        "motivo": f"gate da face em {rel['gate_face']['estado']}"
                                  f" — arbitragem, não escalar estratégia"})
            return BLOQUEIO, None, log
    log.append({"estrategia": BLOQUEIO, "aceita": False,
                "motivo": "nenhuma estratégia fechou — painel numerado e arbitragem"})
    return BLOQUEIO, None, log


# ---------------------------------------------------------------------------
# VALIDADOR_LOCAL_DE_CONTINUIDADE_DA_FACE
#
# Não detecta contaminação nem constrói máscara de remoção. Responde só duas
# perguntas, depois do tratamento:
#   - ficou material conectado além da face local legítima?
#   - a parede seguiu contínua dentro do trecho tratado?
#
# A referência vem de DUAS FAIXAS curtas vizinhas ao trecho, com mediana
# robusta — não de linha única (vulnerável a antialiasing), nem de interseção
# global (contou 3.699 px legítimos como resíduo), nem de interpolação.
# ---------------------------------------------------------------------------

AMBIGUA_FACE = "VALIDACAO_LOCAL_AMBIGUA"
NAO_SUPORTADA = "VALIDACAO_LOCAL_ORIENTACAO_NAO_SUPORTADA"

# Domínio REALMENTE comprovado (SU-039, 26/07/2026). O ramo `ceil` e as demais
# orientações existem no código mas NÃO podem aprovar artefato até terem
# evidência própria — o validador deriva as faixas da suspeita, e isso só foi
# provado quando a linha de chamada corre PARALELA à parede.
SUPORTE_VALIDADOR = {
    "parede_vertical_exterior_esquerda": "comprovado",
    "parede_vertical_exterior_direita": "nao_comprovado",
    "parede_horizontal_exterior_acima": "nao_comprovado",
    "parede_horizontal_exterior_abaixo": "nao_comprovado",
    "orientacao_por_componente_principal": "pendente",
}


def _face_de_faixa(mascara, linhas, lado_exterior_neg, eixo_vertical):
    """Coordenada da face na faixa: mediana robusta sobre as linhas válidas."""
    coords = []
    for i in linhas:
        v = mascara[i] if eixo_vertical else mascara[:, i]
        nz = np.nonzero(v)[0]
        if nz.size:
            coords.append(nz.min() if not lado_exterior_neg else nz.max())
    if not coords:
        return None, None
    return float(np.median(coords)), float(np.std(coords))


def validar_face_local(original, tratada, suspeita, px_mm,
                       recuo_mm=0.10, faixa_mm=0.35, tol_mm=0.05,
                       zonas_protegidas=None, altura_mm=None):
    """(ok | AMBIGUA_FACE, relatório). Só é aplicável quando a contaminação
    está ligada a uma parede com face observável antes e depois do trecho."""
    ys, xs = np.nonzero(suspeita.mascara)
    vertical = (ys.max() - ys.min()) >= (xs.max() - xs.min())
    a, b = (int(ys.min()), int(ys.max())) if vertical else (int(xs.min()), int(xs.max()))
    recuo = max(1, int(recuo_mm * px_mm))
    larg = max(2, int(faixa_mm * px_mm))
    lim = original.shape[0] if vertical else original.shape[1]
    ant = range(max(0, a - recuo - larg), max(1, a - recuo))
    pos = range(min(lim - 1, b + recuo), min(lim, b + recuo + larg))
    # de que lado está a massa suspeita em relação à parede?
    centro_s = float(xs.mean()) if vertical else float(ys.mean())
    perfil = np.nonzero(original[a] if vertical else original[:, a])[0]
    lado_neg = bool(perfil.size and centro_s > perfil.mean())

    f_ant, d_ant = _face_de_faixa(original, ant, lado_neg, vertical)
    f_pos, d_pos = _face_de_faixa(original, pos, lado_neg, vertical)
    rel = {"orientacao_parede": "vertical" if vertical else "horizontal",
           "trecho_px": [a, b], "faixa_px": larg, "recuo_px": recuo,
           "face_anterior": f_ant, "face_posterior": f_pos,
           "dispersao_anterior": None if d_ant is None else round(d_ant, 2),
           "dispersao_posterior": None if d_pos is None else round(d_pos, 2),
           "lado_exterior": ("esquerda" if vertical else "acima") if not lado_neg
                            else ("direita" if vertical else "abaixo")}
    # CONGELAMENTO: fora do caso comprovado (parede vertical, exterior à
    # esquerda, quantização floor), não aprova nada — bloqueia antes mesmo de
    # olhar a face. O ramo `ceil` fica no código sem poder aprovar artefato.
    if not (vertical and not lado_neg):
        rel["suporte_validador"] = SUPORTE_VALIDADOR
        rel["orientacao_detectada"] = (
            f"parede_{'vertical' if vertical else 'horizontal'}"
            f"_exterior_{rel['lado_exterior']}")
        rel["motivo"] = ("orientação sem evidência própria: não remover, não "
                         "aprovar artefato, gerar painel e arbitrar")
        rel["aceita"] = False
        return NAO_SUPORTADA, rel

    if f_ant is None or f_pos is None:
        rel["motivo"] = "faixa sem material: face não observável"
        rel["aceita"] = False
        return AMBIGUA_FACE, rel
    tol = max(1.0, tol_mm * px_mm)
    rel["tolerancia_px"] = round(tol, 2)
    rel["divergencia_faces_px"] = round(abs(f_ant - f_pos), 2)
    if abs(f_ant - f_pos) > tol:
        rel["motivo"] = ("faces divergem além da tolerância — não interpolar, "
                         "arbitragem")
        return AMBIGUA_FACE, rel
    face = (f_ant + f_pos) / 2.0
    rel["face_local_subpixel_px"] = round(face, 2)
    # QUANTIZAÇÃO ORIENTADA: a máscara raster não tem fronteira em 323,25 —
    # tem colunas discretas, e a coluna floor(face) É a borda legítima. Contar
    # x < 323,25 incluía essa coluna e produzia 164 px falsamente residuais.
    # Não é tolerância: é a convenção da grade. Pixel além do limite discreto
    # continua sendo resíduo real.
    if lado_neg:                       # exterior nas coordenadas MAIORES
        limite = int(np.ceil(face)); rel["regra_quantizacao"] = "ceil"
    else:                              # exterior nas coordenadas MENORES
        limite = int(np.floor(face)); rel["regra_quantizacao"] = "floor"
    rel["limite_discreto_px"] = limite

    alem = np.zeros_like(np.asarray(tratada, bool))
    for i in range(a, b + 1):
        v = np.asarray(tratada)[i] if vertical else np.asarray(tratada)[:, i]
        idx = np.nonzero(v)[0]
        if not idx.size:
            continue
        fora = idx[idx > limite] if lado_neg else idx[idx < limite]
        if vertical:
            alem[i, fora] = True
        else:
            alem[fora, i] = True
    # só conta o que está CONECTADO ao contorno final
    n, lab = cv2.connectedComponents(np.asarray(tratada, np.uint8), 8)
    principal = lab[np.asarray(tratada) > 0]
    rot = np.bincount(principal).argmax() if principal.size else 0
    conectado = alem & (lab == rot)
    rel["pixels_alem_da_face"] = int(conectado.sum())
    rel["area_alem_da_face_mm2"] = round(float(conectado.sum()) / px_mm ** 2, 3)
    rel["pixels_alem_desconectados"] = int(alem.sum() - conectado.sum())

    # continuidade: material presente em toda linha do trecho, junto à face
    faixa_face = max(2, int(0.15 * px_mm))
    faltas = 0
    for i in range(a, b + 1):
        if vertical:
            j0, j1 = int(face - faixa_face), int(face + faixa_face)
            tem = np.asarray(tratada)[i, max(0, j0):j1].any()
        else:
            j0, j1 = int(face - faixa_face), int(face + faixa_face)
            tem = np.asarray(tratada)[max(0, j0):j1, i].any()
        faltas += 0 if tem else 1
    rel["linhas_sem_parede"] = faltas
    rel["continuidade_da_face"] = faltas == 0
    rel["aceita"] = (rel["pixels_alem_da_face"] == 0
                     and rel["continuidade_da_face"])
    rel["motivo"] = ("face contínua e sem material além dela" if rel["aceita"]
                     else "; ".join(filter(None, [
                         f"{rel['pixels_alem_da_face']} px conectados além da face"
                         if rel["pixels_alem_da_face"] else "",
                         f"{faltas} linhas sem parede" if faltas else ""])))
    return ("ok" if rel["aceita"] else "rejeitado"), rel
