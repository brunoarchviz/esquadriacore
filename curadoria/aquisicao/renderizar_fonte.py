"""
Renderização da fonte para aquisição: PDF → PNG lossless (pdftocairo) + ROI.
ROI aceito em pixels (reprodução exata) ou normalizado 0-1 (estável entre DPIs).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image


def renderizar_pagina_png(pdf: str, pagina: int, dpi: int, destino: Path) -> Path:
    """Renderiza UMA página em PNG lossless. Retorna o caminho do PNG."""
    destino.mkdir(parents=True, exist_ok=True)
    stem = destino / f"pag{pagina}_{dpi}dpi"
    subprocess.run(
        ["pdftocairo", "-png", "-r", str(dpi), "-f", str(pagina),
         "-l", str(pagina), pdf, str(stem)],
        check=True, capture_output=True)
    candidatos = sorted(destino.glob(f"pag{pagina}_{dpi}dpi*.png"))
    if not candidatos:
        raise RuntimeError(f"pdftocairo não produziu PNG para pág {pagina}")
    return candidatos[0]


def aplicar_roi(imagem: Path, roi_pixels=None, roi_norm=None) -> Image.Image:
    """Recorta a ROI. `roi_pixels`=[x0,y0,x1,y1] absoluto; `roi_norm` em 0-1."""
    img = Image.open(imagem).convert("RGB")
    if roi_pixels:
        return img.crop(tuple(int(v) for v in roi_pixels))
    if roi_norm:
        w, h = img.size
        x0, y0, x1, y1 = roi_norm
        return img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    return img
