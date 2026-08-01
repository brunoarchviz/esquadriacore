"""
Localização e orientação de OCORRÊNCIAS de motivo na máscara do perfil.

Cada ocorrência é medida por si: posição no referencial local normalizado do
perfil (0–1 em x e y, origem no canto inferior-esquerdo do bbox), região para
onde abre e direção da boca. Nada aqui vale como regra universal de família —
são atributos da ocorrência, registrados na evidência.

Vocabulário de orientação (pacote de correção do Bruno, 25/07/2026):
    superior · inferior · esquerda · direita · exterior · camara_interna
"""
from __future__ import annotations

import cv2
import numpy as np


def _exterior(solid: np.ndarray) -> np.ndarray:
    m = np.pad(solid, 1)
    marc = (1 - m).astype(np.uint8)
    cv2.floodFill(marc, np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8),
                  (0, 0), 2)
    return (marc == 2)[1:-1, 1:-1]


def regioes_de_fundo(solid: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Exterior + cada câmara interna. Um motivo pode abrir para qualquer uma
    delas — no SU-225 há uma escovinha de cada."""
    ext = _exterior(solid)
    internas = (solid == 0) & ~ext
    regioes = [("exterior", ext)] if ext.any() else []
    n, lab = cv2.connectedComponents(internas.astype(np.uint8), 4)
    for i in range(1, n):
        R = (lab == i)
        if R.sum() > 16:
            regioes.append(("camara_interna", R))
    return regioes


def bolsos(solid: np.ndarray, px_mm: float, boca_max_mm: float = 5.0
           ) -> list[dict]:
    """Bolsos de fundo selados por UM fechamento morfológico.

    A boca é medida pela GEOMETRIA (extensão da interface bolso↔região aberta),
    não pelo raio que a selou — medida estável e independente do passo.
    """
    achados = []
    r_px = max(2, int(boca_max_mm / 2 * px_mm))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r_px + 1,) * 2)
    fechado = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, k) > 0
    viz = np.ones((3, 3), np.uint8)
    altura, largura = solid.shape
    for regiao, REG in regioes_de_fundo(solid):
        selado = fechado & REG
        if not selado.any():
            continue
        aberto = REG & ~selado
        aberto_dil = cv2.dilate(aberto.astype(np.uint8), viz).astype(bool)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(
            selado.astype(np.uint8), 8)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < (0.3 * px_mm) ** 2:
                continue
            P = (lab == i)
            boca = P & aberto_dil
            by, bx = np.nonzero(boca)
            if len(bx) == 0:
                continue                      # sem boca: é câmara, não bolso
            py, px_ = np.nonzero(P)
            boca_mm = (max(bx.max() - bx.min(), by.max() - by.min()) + 1) / px_mm
            dt = cv2.distanceTransform(P.astype(np.uint8), cv2.DIST_L2, 5)
            # direção: da massa do bolso para a boca, no referencial da imagem
            dx = float(bx.mean() - px_.mean())
            dy = float(py.mean() - by.mean())     # y da imagem cresce p/ baixo
            if abs(dx) > abs(dy):
                direcao = "direita" if dx > 0 else "esquerda"
            else:
                direcao = "superior" if dy > 0 else "inferior"
            achados.append({
                "regiao": regiao,
                "direcao": direcao,
                "orientacao": [direcao, regiao],
                "boca_mm": round(float(boca_mm), 2),
                "diametro_interno_mm": round(float(2 * dt.max() / px_mm), 2),
                "area_mm2": round(float(P.sum()) / px_mm ** 2, 2),
                "posicao_rel": [round(float(px_.mean()) / largura, 3),
                                round(1 - float(py.mean()) / altura, 3)],
                "posicao_mm": [round(float(px_.mean()) / px_mm, 2),
                               round((altura - float(py.mean())) / px_mm, 2)],
                "mascara": P,
            })
    return achados


def padronizar(solid: np.ndarray, px_mm: float, alvo_px_mm: float = 24.0):
    """Leva o perfil à MESMA resolução antes de medir.

    Sem isso a medida não é comparável entre perfis: a mesma boca medida a 12
    e a 24 px/mm variou 0,3 mm — mais que qualquer diferença que se queira
    afirmar entre famílias.
    """
    largura_mm = solid.shape[1] / px_mm
    f = alvo_px_mm / px_mm
    novo = cv2.resize(solid, (max(8, int(round(solid.shape[1] * f))),
                              max(8, int(round(solid.shape[0] * f)))),
                      interpolation=cv2.INTER_NEAREST)
    return novo, novo.shape[1] / largura_mm


def ocorrencias_de_escovinha(solid: np.ndarray, px_mm: float,
                             razao_min: float = 1.35,
                             boca_max_mm: float = 4.5,
                             alvo_px_mm: float = 24.0) -> list[dict]:
    """Canais tipo fechadura: interior nitidamente maior que a boca.

    Devolve UMA entrada POR OCORRÊNCIA (um perfil pode ter várias), cada uma
    com posição, orientação e medidas próprias.
    """
    solid, px_mm = padronizar(solid, px_mm, alvo_px_mm)
    out = []
    for b in bolsos(solid, px_mm, boca_max_mm=5.0):
        if b["boca_mm"] <= 0:
            continue
        razao = b["diametro_interno_mm"] / b["boca_mm"]
        if (razao >= razao_min and b["boca_mm"] <= boca_max_mm
                and b["diametro_interno_mm"] >= 1.5):
            b["razao_interno_boca"] = round(razao, 2)
            out.append(b)
    out.sort(key=lambda b: (-b["area_mm2"], b["posicao_rel"][1]))
    for i, b in enumerate(out, 1):
        b["ocorrencia"] = i
    return out


def zona_da_ocorrencia(ocorrencia: dict, largura_mm: float, altura_mm: float,
                       folga_mm: float = 1.2) -> list[float]:
    """Zona protegida [x0,y0,x1,y1] em mm ao redor da ocorrência.
    Cada ocorrência tem a SUA zona — uma escovinha não protege a outra."""
    cx, cy = ocorrencia["posicao_mm"]
    raio = max(ocorrencia["diametro_interno_mm"], ocorrencia["boca_mm"]) / 2 \
        + folga_mm
    return [round(max(0.0, cx - raio), 2), round(max(0.0, cy - raio), 2),
            round(min(largura_mm, cx + raio), 2),
            round(min(altura_mm, cy + raio), 2)]


# ---------------------------------------------------------------------------
# Discriminação OLHAL × CANAL DE ESCOVINHA
#
# Correção crítica do Bruno (25/07/2026): um detector genérico de "bolso"
# encontra o OLHAL e o chama de escovinha. Os dois são motivos distintos que
# convivem no mesmo perfil. Na SEÇÃO transversal:
#
#   OLHAL      → câmara arredondada dominante (aloja o parafuso); a boca é
#                só a fenda do "C". Alta circularidade, baixa retangularidade.
#   ESCOVINHA  → bolso LONGITUDINAL (retangular em seção) atrás de uma boca
#                estreita, com lábios de retenção que avançam para dentro.
#
# Não classificar por área, orientação, circularidade isolada, proximidade da
# borda nem "é um vazio aberto". Enquanto não houver ground truth aprovado pelo
# Bruno, o resultado é CANDIDATO — nunca confirmação.
# ---------------------------------------------------------------------------

def _features_forma(P: np.ndarray, px_mm: float) -> dict:
    """Descritores de forma do bolso, em unidades comparáveis."""
    cnts, _ = cv2.findContours(P.astype(np.uint8), cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    area = float(cv2.contourArea(c))
    perim = float(cv2.arcLength(c, True))
    (_, _), (rw, rh), _ = cv2.minAreaRect(c)
    ret_area = float(rw * rh)
    dt = cv2.distanceTransform(P.astype(np.uint8), cv2.DIST_L2, 5)
    lado_maior, lado_menor = max(rw, rh), max(min(rw, rh), 1e-6)
    return {
        # 1.0 = círculo perfeito; retângulo alongado « 0.6
        "circularidade": round(4 * np.pi * area / max(perim ** 2, 1e-6), 3),
        # círculo preenche 0.785 do seu retângulo; retângulo preenche ~1.0
        "retangularidade": round(area / max(ret_area, 1e-6), 3),
        "alongamento": round(lado_maior / lado_menor, 2),
        "lado_maior_mm": round(lado_maior / px_mm, 2),
        "lado_menor_mm": round(lado_menor / px_mm, 2),
        "raio_inscrito_mm": round(float(dt.max()) / px_mm, 2),
    }


def _tem_labios(P: np.ndarray, solid: np.ndarray, boca: np.ndarray) -> bool:
    """Lábios de retenção: a boca é MAIS ESTREITA que o bolso logo atrás dela.
    É o que segura a base da escova — um olhal em C não tem esse degrau."""
    ys, xs = np.nonzero(boca)
    if len(xs) == 0:
        return False
    # largura da boca × largura máxima do bolso, no eixo dominante da boca
    horizontal = (xs.max() - xs.min()) >= (ys.max() - ys.min())
    largura_boca = (xs.max() - xs.min() + 1) if horizontal else (ys.max() - ys.min() + 1)
    py, px_ = np.nonzero(P)
    largura_bolso = (px_.max() - px_.min() + 1) if horizontal else (py.max() - py.min() + 1)
    return largura_bolso >= 1.30 * largura_boca


def classificar_bolso(b: dict, solid: np.ndarray) -> tuple[str, str]:
    """('olhal' | 'escovinha' | 'indeterminado', justificativa).

    CANDIDATO, nunca confirmação: a função final é arbitrada pelo Bruno sobre
    o painel de ground truth.
    """
    f = b["forma"]
    circular = f["circularidade"] >= 0.62 and f["alongamento"] <= 1.6
    retangular = f["retangularidade"] >= 0.80 and f["circularidade"] < 0.70
    if circular and not retangular:
        return ("olhal",
                f"câmara arredondada dominante (circularidade "
                f"{f['circularidade']}, alongamento {f['alongamento']}) — "
                f"formato de alojamento de parafuso")
    if retangular and b.get("labios"):
        return ("escovinha",
                f"bolso longitudinal (retangularidade {f['retangularidade']}, "
                f"alongamento {f['alongamento']}) atrás de boca estreita, com "
                f"lábios de retenção")
    if retangular and not b.get("labios"):
        return ("indeterminado",
                f"bolso retangular sem lábios de retenção detectados: não "
                f"confirma escovinha (regra do diagrama do Bruno)")
    return ("indeterminado",
            f"forma não decisiva (circularidade {f['circularidade']}, "
            f"retangularidade {f['retangularidade']}, alongamento "
            f"{f['alongamento']})")


def candidatos_de_motivo(solid: np.ndarray, px_mm: float,
                         largura_mm: float, altura_mm: float,
                         alvo_px_mm: float = 24.0,
                         area_min_mm2: float = 0.8) -> list[dict]:
    """TODOS os bolsos do perfil, numerados, com forma e classificação
    CANDIDATA. Não filtra por tipo: quem decide a função é o Bruno."""
    solid, px_mm = padronizar(solid, px_mm, alvo_px_mm)
    achados = []
    for b in bolsos(solid, px_mm, boca_max_mm=6.0):
        if b["area_mm2"] < area_min_mm2:
            continue
        P = b["mascara"]
        b["forma"] = _features_forma(P, px_mm)
        viz = np.ones((3, 3), np.uint8)
        ext = _exterior(solid)
        regs = {n: R for n, R in regioes_de_fundo(solid)}
        aberto = np.zeros_like(P)
        for R in regs.values():
            aberto |= (R & ~P)
        b["labios"] = _tem_labios(
            P, solid, P & cv2.dilate(aberto.astype(np.uint8), viz).astype(bool))
        b["classe_candidata"], b["justificativa"] = classificar_bolso(b, solid)
        achados.append(b)
    achados.sort(key=lambda x: (-x["area_mm2"], x["posicao_rel"][1]))
    for i, b in enumerate(achados, 1):
        b["candidato"] = i
        b["zona"] = zona_da_ocorrencia(b, largura_mm, altura_mm)
    return achados
