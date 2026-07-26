"""
Extração do contorno bruto a partir do raster (núcleo do método oficial).
Base: script de referência v1.1 (GPT) + correções aprovadas:
 - gate de aspecto BLOQUEANTE (≤0,75%) antes da escala anisotrópica;
 - dois gates F1 (bruto ≥0,99; comercial ≥0,98 — este no validador);
 - F1 protegido contra caso degenerado;
 - quebra de ponte de cota como FALLBACK (erosão→seleção→dilatação local→
   interseção com a máscara original), nunca operação padrão;
 - determinismo: hash SHA-256 da máscara e do contorno.

Uso programático (pilotos) ou CLI. NÃO escreve em dados/.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class FalhaGate:
    codigo: str
    mensagem: str


@dataclass
class ResultadoAquisicao:
    codigo: str
    contorno_externo: list          # [[x,y] mm] CCW (artefato de curadoria)
    vazios_internos: list           # [[[x,y] mm] CW]
    mascara: np.ndarray             # binária 0/1 (recorte do componente)
    bbox_px: tuple                  # (w,h) do componente
    escala: dict                    # px/mm x e y, anisotropia
    metricas: dict
    falhas: list = field(default_factory=list)

    @property
    def aprovado(self) -> bool:
        return not self.falhas


def _area_sinal(pts) -> float:
    return 0.5 * sum(
        pts[i][0] * pts[(i + 1) % len(pts)][1]
        - pts[(i + 1) % len(pts)][0] * pts[i][1]
        for i in range(len(pts)))


def _normalizar_orientacao(ext, vazios):
    # Artefato de curadoria: externo CCW, vazios CW. A gravação oficial e o
    # contrato ADR-009 continuam donos da normalização de consumo.
    if _area_sinal(ext) < 0:
        ext.reverse()
    for v in vazios:
        if _area_sinal(v) > 0:
            v.reverse()
    return ext, vazios


def f1_tolerante_seguro(origem: np.ndarray, predito: np.ndarray,
                        tolerancia_px: float) -> dict:
    origem = (origem > 0).astype(np.uint8)
    predito = (predito > 0).astype(np.uint8)
    if origem.sum() == 0 and predito.sum() == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if origem.sum() == 0 or predito.sum() == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    d_origem = cv2.distanceTransform(1 - origem, cv2.DIST_L2, 5)
    d_pred = cv2.distanceTransform(1 - predito, cv2.DIST_L2, 5)
    precision = float(np.mean(d_origem[predito.astype(bool)] <= tolerancia_px))
    recall = float(np.mean(d_pred[origem.astype(bool)] <= tolerancia_px))
    den = precision + recall
    return {"precision": precision, "recall": recall,
            "f1": 0.0 if den == 0 else 2 * precision * recall / den}


def rasterizar_vetor(ext, vazios, largura_mm, altura_mm, w_px, h_px):
    tela = np.zeros((h_px, w_px), dtype=np.uint8)

    def conv(anel):
        pts = []
        for x, y in anel:
            px = int(round(x / largura_mm * (w_px - 1)))
            py = int(round((altura_mm - y) / altura_mm * (h_px - 1)))
            pts.append([px, py])
        return np.asarray(pts, dtype=np.int32)

    cv2.fillPoly(tela, [conv(ext)], 1)
    for v in vazios:
        cv2.fillPoly(tela, [conv(v)], 0)
    return tela


def _binarizar(gray: np.ndarray, threshold) -> np.ndarray:
    if threshold in (None, "otsu", "auto"):
        _, binario = cv2.threshold(gray, 0, 255,
                                   cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, binario = cv2.threshold(gray, int(threshold), 255,
                                   cv2.THRESH_BINARY_INV)
    return binario


def _maior_componente(binario: np.ndarray):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binario, 8)
    if n <= 1:
        raise RuntimeError("nenhum componente escuro encontrado")
    rotulo = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = (int(v) for v in stats[rotulo, :4])
    isolado = (labels[y:y + h, x:x + w] == rotulo).astype(np.uint8)
    return isolado, (x, y, w, h)


def quebrar_ponte_cota(binario: np.ndarray, raio_px: int = 1):
    """FALLBACK aprovado: erosão mínima → seleção do componente do perfil →
    dilatação local pelo MESMO raio → interseção com a máscara original.
    (Não usa reconstrução geodésica plena, que regeneraria a cota.)"""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                       (2 * raio_px + 1, 2 * raio_px + 1))
    erodido = cv2.erode(binario, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(erodido, 8)
    if n <= 1:
        return binario
    rotulo = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    selecionado = (labels == rotulo).astype(np.uint8) * 255
    dilatado = cv2.dilate(selecionado, kernel)
    return cv2.bitwise_and(dilatado, binario)


def extrair(codigo: str, imagem, largura_mm: float, altura_mm: float,
            vazios_esperados: int, threshold="otsu",
            simplificacao_mm: float = 0.05, tolerancia_mm: float = 0.15,
            erro_aspecto_max: float = 0.0075, f1_min_bruto: float = 0.99,
            usar_quebra_ponte: bool = False) -> ResultadoAquisicao:
    """Extrai o contorno bruto de uma imagem (PIL.Image ou caminho)."""
    if not isinstance(imagem, Image.Image):
        imagem = Image.open(imagem).convert("RGB")
    gray = cv2.cvtColor(np.asarray(imagem), cv2.COLOR_RGB2GRAY)
    binario = _binarizar(gray, threshold)
    if usar_quebra_ponte:
        binario = quebrar_ponte_cota(binario)
    isolado, (x, y, w_px, h_px) = _maior_componente(binario)

    aspecto_medido = w_px / h_px
    aspecto_esperado = largura_mm / altura_mm
    erro_aspecto = abs(aspecto_medido - aspecto_esperado) / aspecto_esperado

    contornos, hierarquia = cv2.findContours(
        isolado * 255, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarquia is None:
        raise RuntimeError("nenhum contorno encontrado")
    hierarquia = hierarquia[0]
    candidatos = [i for i, n in enumerate(hierarquia) if n[3] == -1]
    idx_ext = max(candidatos, key=lambda i: cv2.contourArea(contornos[i]))
    idx_vazios = []
    filho = hierarquia[idx_ext][2]
    while filho != -1:
        idx_vazios.append(filho)
        filho = hierarquia[filho][0]

    # escala anisotrópica: cotas autoritativas em cada eixo (aplicada
    # SOMENTE se o gate de aspecto passar — verificado nas falhas abaixo)
    esc_x = (w_px - 1) / largura_mm
    esc_y = (h_px - 1) / altura_mm
    px_mm_medio = (esc_x + esc_y) / 2
    eps = simplificacao_mm * px_mm_medio

    def converter(c):
        aprox = cv2.approxPolyDP(c, eps, True)
        out = []
        for px, py in aprox.reshape(-1, 2):
            out.append([round(px / (w_px - 1) * largura_mm, 4),
                        round((h_px - 1 - py) / (h_px - 1) * altura_mm, 4)])
        return out

    ext = converter(contornos[idx_ext])
    vazios = [converter(contornos[i]) for i in idx_vazios]
    ext, vazios = _normalizar_orientacao(ext, vazios)

    vetor = rasterizar_vetor(ext, vazios, largura_mm, altura_mm, w_px, h_px)
    inter = int(np.logical_and(isolado, vetor).sum())
    uni = int(np.logical_or(isolado, vetor).sum())
    f1 = f1_tolerante_seguro(isolado, vetor, tolerancia_mm * px_mm_medio)

    falhas = []
    # RECORTE: se o componente encosta na borda do recorte, a ROI cortou o
    # perfil. Foi assim que a aba externa do SU-009 perdeu 6,58 mm — o gate
    # existe para que esse defeito nunca mais passe silencioso.
    alt_img, larg_img = binario.shape
    bordas = [n for n, tocou in (("esquerda", x <= 0), ("topo", y <= 0),
                                 ("direita", x + w_px >= larg_img),
                                 ("base", y + h_px >= alt_img)) if tocou]
    if bordas:
        falhas.append(FalhaGate(
            "RECORTE", f"o componente toca a borda do recorte "
                       f"({', '.join(bordas)}) — a ROI está cortando o perfil"))
    if len(vazios) != vazios_esperados:
        falhas.append(FalhaGate("TOPOLOGIA",
                                f"esperados {vazios_esperados} vazios, "
                                f"detectados {len(vazios)}"))
    if erro_aspecto > erro_aspecto_max:
        falhas.append(FalhaGate("ASPECTO",
                                f"erro {erro_aspecto:.4%} > "
                                f"{erro_aspecto_max:.4%}"))
    if f1["f1"] < f1_min_bruto:
        falhas.append(FalhaGate("F1_BRUTO",
                                f"F1 {f1['f1']:.6f} < {f1_min_bruto}"))

    hash_mascara = hashlib.sha256(isolado.tobytes()).hexdigest()[:16]
    hash_contorno = hashlib.sha256(
        json.dumps([ext, vazios]).encode()).hexdigest()[:16]

    metricas = {
        "codigo": codigo,
        "dimensoes_mm": {"largura": largura_mm, "altura": altura_mm},
        "bbox_pixels": {"largura": w_px, "altura": h_px},
        "erro_relativo_aspecto": erro_aspecto,
        "escala_px_mm": {"x": esc_x, "y": esc_y,
                         "anisotropia": esc_x / esc_y},
        "pontos_externo": len(ext),
        "pontos_vazios": [len(v) for v in vazios],
        "vazios_esperados": vazios_esperados,
        "vazios_detectados": len(vazios),
        "iou_exato_informativo": inter / uni,
        "diferenca_area_relativa":
            abs(int(vetor.sum()) - int(isolado.sum())) / int(isolado.sum()),
        "tolerancia_mm": tolerancia_mm,
        "f1_tolerante": f1,
        "hash_mascara": hash_mascara,
        "hash_contorno": hash_contorno,
        "estado": "AQUISICAO_BRUTA_OK" if not falhas else
                  "BLOQUEADO_" + falhas[0].codigo,
    }
    return ResultadoAquisicao(
        codigo=codigo, contorno_externo=ext, vazios_internos=vazios,
        mascara=isolado, bbox_px=(w_px, h_px),
        escala={"x": esc_x, "y": esc_y}, metricas=metricas,
        falhas=falhas)


def salvar_artefatos(res: ResultadoAquisicao, pasta: Path):
    pasta.mkdir(parents=True, exist_ok=True)
    Image.fromarray(res.mascara * 255).save(
        pasta / "10_mascara_origem.png")
    (pasta / "20_contorno_bruto.json").write_text(json.dumps({
        "codigo": res.codigo,
        "metodo": "raster_componente_conectado_findContours",
        "contorno_externo": res.contorno_externo,
        "vazios_internos": res.vazios_internos,
        "metricas": res.metricas}, ensure_ascii=False, indent=2))
    (pasta / "40_metricas_bruto.json").write_text(
        json.dumps(res.metricas, ensure_ascii=False, indent=2))
