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


def camaras_fechadas(mascara) -> tuple[int, np.ndarray]:
    """Câmaras fechadas de uma máscara raster: (quantidade, máscara do interior).

    O flood-fill parte de uma MOLDURA de 1 px. Sem ela o preenchimento pode
    começar sobre o material — a máscara de aquisição é bbox justo e toca as
    quatro bordas —, e então nenhuma região de fundo é alcançada, produzindo
    contagem falsa.
    """
    m = (np.asarray(mascara) > 0).astype(np.uint8)
    mp = np.pad(m, 1)
    fundo = (mp == 0).astype(np.uint8)
    ff = fundo.copy()
    aux = np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, aux, (0, 0), 2)
    interno = (fundo > 0) & (ff != 2)
    n, _ = cv2.connectedComponents(interno.astype(np.uint8), 8)
    return n - 1, interno[1:-1, 1:-1]


def maior_componente(mascara) -> tuple[int, np.ndarray]:
    """(nº de componentes, máscara do maior). cv2 fica confinado a este pacote."""
    m = (np.asarray(mascara) > 0).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return 0, np.zeros_like(m)
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    return n - 1, (lab == i).astype(np.uint8)


def fechar(mascara, raio_px: int) -> np.ndarray:
    """Fechamento morfológico — diagnóstico de falha capilar na parede."""
    m = (np.asarray(mascara) > 0).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * raio_px + 1,) * 2)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)


def mascara_de_imagem(imagem, threshold="otsu") -> np.ndarray:
    """Binariza uma imagem RGB (perfil = 1). `threshold` é 'otsu' ou um inteiro."""
    g = cv2.cvtColor(np.asarray(imagem), cv2.COLOR_RGB2GRAY)
    if threshold == "otsu":
        return cv2.threshold(
            g, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1].astype(np.uint8)
    return (g < int(threshold)).astype(np.uint8)


def derivar_assinatura_topologica(contorno_externo, vazios_internos,
                                  probes_exterior_extra=()) -> dict:
    """Deriva a assinatura a partir da geometria. Pura e determinística.

    Vivia num runner do scratchpad; a assinatura pertence a este módulo, não à
    camada de exportação. Sem escrita em disco e sem dependência de sessão.
    """
    poly = _poligono(contorno_externo, vazios_internos)
    material, vazio = [], []
    for v in vazios_internos:
        anel = Polygon([tuple(p) for p in v])
        c = anel.centroid
        vazio.append([round(c.x, 2), round(c.y, 2)])
        b = anel.bounds
        for cand in ((c.x, b[1] - 0.8), (c.x, b[3] + 0.8), (b[0] - 0.8, c.y)):
            if poly.contains(Point(cand)):
                material.append([round(cand[0], 2), round(cand[1], 2)])
                break
    if not material:                     # perfil sem vazio fechado
        c = poly.representative_point()
        material.append([round(c.x, 2), round(c.y, 2)])
    exterior = [list(p) for p in probes_exterior_extra
                if not poly.contains(Point(p))]
    return {"vazios": len(vazios_internos), "probes_material": material,
            "probes_vazio": vazio, "probes_exterior_conectado": exterior}
