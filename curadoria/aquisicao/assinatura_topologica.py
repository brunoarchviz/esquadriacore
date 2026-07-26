"""
Assinatura topológica de curadoria (aprovada no pacote de aprovação, §5).
Coordenadas em MILÍMETROS no referencial calibrado do perfil (orientação do
card Alcoa, y para cima). Não é entidade de domínio.

Campos:
  vazios: int                        — nº exato de câmaras fechadas
  probes_material: [[x,y], ...]      — devem cair DENTRO do alumínio
  probes_vazio: [[x,y], ...]         — 1+ por câmara fechada (dentro do furo)
  probes_exterior_conectado: [...]   — devem estar FORA do polígono E
                                       conectados à borda externa (frestas
                                       abertas que não podem ser seladas)
"""
from __future__ import annotations

import cv2
import numpy as np
from shapely.geometry import Point, Polygon

from curadoria.aquisicao.extrair_contorno_raster import rasterizar_vetor


def _poligono(ext, vazios) -> Polygon:
    return Polygon([tuple(p) for p in ext],
                   [[tuple(p) for p in v] for v in vazios])


def verificar(ext, vazios, assinatura: dict, largura_mm: float,
              altura_mm: float, resolucao_px_mm: float = 12.0) -> list[str]:
    """Retorna lista de violações (vazia = assinatura preservada)."""
    violacoes = []
    n_esperado = assinatura.get("vazios")
    if n_esperado is not None and len(vazios) != n_esperado:
        violacoes.append(
            f"vazios: esperados {n_esperado}, encontrados {len(vazios)}")

    poly = _poligono(ext, vazios)
    if not poly.is_valid:
        violacoes.append("polígono inválido (shapely)")
        return violacoes

    for x, y in assinatura.get("probes_material", []):
        if not poly.contains(Point(x, y)):
            violacoes.append(f"probe_material ({x},{y}) fora do alumínio")
    for x, y in assinatura.get("probes_vazio", []):
        dentro_de_furo = any(
            Polygon([tuple(p) for p in v]).contains(Point(x, y))
            for v in vazios)
        if not dentro_de_furo:
            violacoes.append(f"probe_vazio ({x},{y}) não está em câmara")

    probes_ext = assinatura.get("probes_exterior_conectado", [])
    if probes_ext:
        # flood-fill raster a partir da borda. O perfil toca as 4 bordas do
        # canvas (bbox justo), fragmentando o fundo — a moldura de 1 px
        # reconecta tudo que é alcançável a partir do exterior real.
        w = max(4, int(largura_mm * resolucao_px_mm))
        h = max(4, int(altura_mm * resolucao_px_mm))
        solido = rasterizar_vetor(ext, vazios, largura_mm, altura_mm, w, h)
        solido_m = np.pad(solido, 1)
        marcado = (1 - solido_m).astype(np.uint8)
        mascara_ff = np.zeros((h + 4, w + 4), np.uint8)
        cv2.floodFill(marcado, mascara_ff, (0, 0), 2)
        exterior = marcado == 2
        for x, y in probes_ext:
            px = int(round(x / largura_mm * (w - 1)))
            py = int(round((altura_mm - y) / altura_mm * (h - 1)))
            px = min(max(px, 0), w - 1)
            py = min(max(py, 0), h - 1)
            if solido[py, px]:
                violacoes.append(
                    f"probe_exterior ({x},{y}) foi SOLIDIFICADO")
            elif not exterior[py + 1, px + 1]:
                violacoes.append(
                    f"probe_exterior ({x},{y}) ficou ISOLADO do exterior "
                    f"(fresta selada)")
    return violacoes
