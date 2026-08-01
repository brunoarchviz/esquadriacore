"""Registro por transformação de SIMILARIDADE entre duas máscaras raster.

Uma escala única, uma rotação, translação. Nunca escala anisotrópica, nunca
cisalhamento, nunca deformação local.

Existe porque bounding box não serve para calibrar: ele é decidido por quatro
pixels extremos e é sensível a espessura de traço, antialiasing, caco isolado e
corte pequeno. O registro usa o contorno inteiro, então um pixel extremo não
manda no resultado.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Registro:
    """Resultado do alinhamento. `escala` é única por construção."""
    escala: float
    rotacao_graus: float
    translacao: tuple
    erro_medio_px: float
    erro_p95_px: float
    erro_max_px: float
    iou: float

    def resumo(self) -> dict:
        return {"escala": round(self.escala, 6),
                "rotacao_graus": round(self.rotacao_graus, 3),
                "translacao": [round(v, 2) for v in self.translacao],
                "erro_medio_px": round(self.erro_medio_px, 3),
                "erro_p95_px": round(self.erro_p95_px, 3),
                "erro_max_px": round(self.erro_max_px, 3),
                "iou": round(self.iou, 4)}


def _pontos_de_borda(mascara) -> np.ndarray:
    m = (np.asarray(mascara) > 0).astype(np.uint8)
    cont, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    if not cont:
        return np.empty((0, 2), np.float64)
    return np.vstack([c.reshape(-1, 2) for c in cont]).astype(np.float64)


def _procrustes_isotropico(origem: np.ndarray, destino: np.ndarray):
    """Similaridade que leva `origem` em `destino`: UMA escala, rotação, translação."""
    co, cd = origem.mean(0), destino.mean(0)
    o, d = origem - co, destino - cd
    no = np.sqrt((o ** 2).sum())
    if no == 0:
        return 1.0, 0.0, (0.0, 0.0)
    u, s, vt = np.linalg.svd(o.T @ d)
    r = (u @ vt).T
    if np.linalg.det(r) < 0:                 # reflexão não é permitida
        vt[-1] *= -1
        s[-1] *= -1
        r = (u @ vt).T
    escala = s.sum() / (o ** 2).sum()
    ang = float(np.degrees(np.arctan2(r[1, 0], r[0, 0])))
    t = cd - escala * (r @ co)
    return float(escala), ang, (float(t[0]), float(t[1]))


def _aplicar(pontos, escala, ang, t):
    a = np.radians(ang)
    r = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    return escala * (pontos @ r.T) + np.asarray(t)


def registrar(origem_mascara, destino_mascara, iteracoes: int = 30) -> Registro:
    """ICP com escala ÚNICA. Devolve a similaridade e os resíduos."""
    O = _pontos_de_borda(origem_mascara)
    D = _pontos_de_borda(destino_mascara)
    if O.size == 0 or D.size == 0:
        raise ValueError("máscara sem borda: nada a registrar")

    # inicialização grosseira por centróide e raio médio — sem usar bbox
    co, cd = O.mean(0), D.mean(0)
    ro = np.linalg.norm(O - co, axis=1).mean()
    rd = np.linalg.norm(D - cd, axis=1).mean()
    escala, ang, t = (rd / max(ro, 1e-9)), 0.0, tuple(cd - (rd / max(ro, 1e-9)) * co)

    arvore = cv2.flann_Index(D.astype(np.float32),
                             {"algorithm": 1, "trees": 4})
    for _ in range(iteracoes):
        P = _aplicar(O, escala, ang, t)
        idx, _ = arvore.knnSearch(P.astype(np.float32), 1)
        emparelhado = D[idx.ravel()]
        escala, ang, t = _procrustes_isotropico(O, emparelhado)

    P = _aplicar(O, escala, ang, t)
    idx, dist2 = arvore.knnSearch(P.astype(np.float32), 1)
    res = np.sqrt(dist2.ravel())

    mo = (np.asarray(origem_mascara) > 0).astype(np.uint8)
    md = (np.asarray(destino_mascara) > 0).astype(np.uint8)
    a = np.radians(ang)
    M = np.array([[escala * np.cos(a), -escala * np.sin(a), t[0]],
                  [escala * np.sin(a), escala * np.cos(a), t[1]]], np.float64)
    alinhada = cv2.warpAffine(mo, M, (md.shape[1], md.shape[0]), flags=cv2.INTER_NEAREST)
    inter = int((alinhada.astype(bool) & md.astype(bool)).sum())
    uni = int((alinhada.astype(bool) | md.astype(bool)).sum())

    return Registro(escala=escala, rotacao_graus=ang, translacao=t,
                    erro_medio_px=float(res.mean()),
                    erro_p95_px=float(np.percentile(res, 95)),
                    erro_max_px=float(res.max()),
                    iou=inter / max(1, uni))


def transferir_zona(zona_mm, escala_px_mm_origem, registro: Registro,
                    escala_px_mm_destino, altura_origem_mm, altura_destino_mm):
    """Leva uma zona de motivo do referencial da origem para o do destino.

    Só similaridade: a zona é convertida em px, transformada e reconvertida.
    """
    x0, y0, x1, y1 = zona_mm
    cantos = np.array([
        [x0 * escala_px_mm_origem, (altura_origem_mm - y1) * escala_px_mm_origem],
        [x1 * escala_px_mm_origem, (altura_origem_mm - y1) * escala_px_mm_origem],
        [x1 * escala_px_mm_origem, (altura_origem_mm - y0) * escala_px_mm_origem],
        [x0 * escala_px_mm_origem, (altura_origem_mm - y0) * escala_px_mm_origem]],
        np.float64)
    p = _aplicar(cantos, registro.escala, registro.rotacao_graus,
                 registro.translacao)
    xs, ys = p[:, 0] / escala_px_mm_destino, p[:, 1] / escala_px_mm_destino
    return (round(float(xs.min()), 2),
            round(float(altura_destino_mm - ys.max()), 2),
            round(float(xs.max()), 2),
            round(float(altura_destino_mm - ys.min()), 2))
