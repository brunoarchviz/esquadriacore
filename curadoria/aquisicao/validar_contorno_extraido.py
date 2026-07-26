"""
Gates de validação do contorno (política do manifest v1.1, aprovada):

BRUTO × máscara:      F1 ≥ 0,99 (tol 0,15 mm) · topologia exata · aspecto ≤0,75%
COMERCIAL × máscara:  F1 ≥ 0,98 (tol 0,15 mm) · área ≤3,5% · topologia exata ·
                      dimensões ±0,10 mm · assinatura topológica · zonas
                      protegidas intactas · aprovação visual do Bruno (humana)
IoU exato é apenas informativo.
"""
from __future__ import annotations

import numpy as np

from curadoria.aquisicao.extrair_contorno_raster import (
    rasterizar_vetor, f1_tolerante_seguro)
from curadoria.aquisicao import assinatura_topologica


def validar_comercial(ext, vazios, mascara: np.ndarray, largura_mm, altura_mm,
                      assinatura: dict, f1_min=0.98, area_max=0.035,
                      dim_tol_mm=0.10, tolerancia_mm=0.15) -> dict:
    h_px, w_px = mascara.shape
    vetor = rasterizar_vetor(ext, vazios, largura_mm, altura_mm, w_px, h_px)
    px_mm = ((w_px - 1) / largura_mm + (h_px - 1) / altura_mm) / 2
    f1 = f1_tolerante_seguro(mascara, vetor, tolerancia_mm * px_mm)
    area_dif = abs(int(vetor.sum()) - int(mascara.sum())) / int(mascara.sum())
    xs = [p[0] for p in ext]; ys = [p[1] for p in ext]
    larg = max(xs) - min(xs); alt = max(ys) - min(ys)
    inter = int(np.logical_and(mascara, vetor).sum())
    uni = int(np.logical_or(mascara, vetor).sum())

    falhas = []
    if f1["f1"] < f1_min:
        falhas.append(f"F1 {f1['f1']:.4f} < {f1_min}")
    if area_dif > area_max:
        falhas.append(f"área {area_dif:.2%} > {area_max:.1%}")
    if abs(larg - largura_mm) > dim_tol_mm:
        falhas.append(f"largura {larg:.2f} ≠ {largura_mm}±{dim_tol_mm}")
    if abs(alt - altura_mm) > dim_tol_mm:
        falhas.append(f"altura {alt:.2f} ≠ {altura_mm}±{dim_tol_mm}")
    falhas += assinatura_topologica.verificar(
        ext, vazios, assinatura, largura_mm, altura_mm)

    return {
        "f1_tolerante": f1,
        "diferenca_area_relativa": area_dif,
        "iou_exato_informativo": inter / uni,
        "dimensoes_obtidas_mm": {"largura": round(larg, 3),
                                 "altura": round(alt, 3)},
        "pontos_externo": len(ext),
        "pontos_vazios": [len(v) for v in vazios],
        "vazios_detectados": len(vazios),
        "falhas": falhas,
        "estado": "LIMPEZA_COMERCIAL_OK" if not falhas else "BLOQUEADO",
    }
