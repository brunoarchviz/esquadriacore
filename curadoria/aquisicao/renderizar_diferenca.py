"""
Mapa de diferença e painel de aquisição (7 itens):
card · máscara isolada · bruto · limpo · mapa de diferença · métricas · vazios.
Mapa: cinza=coincide · vermelho=vetor acrescentou material · azul=vetor removeu.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from curadoria.aquisicao.extrair_contorno_raster import rasterizar_vetor


def _fonte(tam):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", tam)
    except OSError:
        return ImageFont.load_default()


def mapa_diferenca(mascara: np.ndarray, ext, vazios, largura_mm, altura_mm):
    h, w = mascara.shape
    vetor = rasterizar_vetor(ext, vazios, largura_mm, altura_mm, w, h)
    rgb = np.full((h, w, 3), 255, dtype=np.uint8)
    ambos = (mascara > 0) & (vetor > 0)
    so_vetor = (vetor > 0) & ~(mascara > 0)
    so_origem = (mascara > 0) & ~(vetor > 0)
    rgb[ambos] = (110, 110, 110)
    rgb[so_vetor] = (220, 40, 40)      # vetor acrescentou
    rgb[so_origem] = (40, 70, 230)     # vetor removeu
    return Image.fromarray(rgb)


def _render_vetor(ext, vazios, largura_mm, altura_mm, escala_px_mm=14):
    w = int(largura_mm * escala_px_mm) + 20
    h = int(altura_mm * escala_px_mm) + 20

    def conv(anel):
        return [(10 + x * escala_px_mm,
                 10 + (altura_mm - y) * escala_px_mm) for x, y in anel]
    img = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(img)
    dr.polygon(conv(ext), fill=(60, 60, 60))
    for v in vazios:
        dr.polygon(conv(v), fill="white")
    return img


def painel(pasta: Path, codigo: str, card: Image.Image, mascara: np.ndarray,
           bruto: tuple, limpo: tuple, largura_mm, altura_mm,
           metricas: dict, log_ops=None):
    """bruto/limpo = (ext, vazios). Salva 50_diferenca.png e
    59_painel_aquisicao.png."""
    dif = mapa_diferenca(mascara, limpo[0], limpo[1], largura_mm, altura_mm)
    dif.save(pasta / "50_diferenca.png")

    imgs = [
        ("Card aprovado", card.convert("RGB")),
        ("Máscara isolada", Image.fromarray(255 - mascara * 255).convert("RGB")),
        ("Contorno bruto", _render_vetor(*bruto, largura_mm, altura_mm)),
        ("Contorno comercial", _render_vetor(*limpo, largura_mm, altura_mm)),
        ("Diferença (verm=+ / azul=-)", dif),
    ]
    painel_img = Image.new("RGB", (2600, 1250), "white")
    dr = ImageDraw.Draw(painel_img)
    dr.text((40, 20), f"{codigo} — pipeline oficial de aquisição raster",
            fill="black", font=_fonte(38))
    x = 40
    for titulo, im in imgs:
        im = im.copy()
        im.thumbnail((470, 800), Image.Resampling.LANCZOS)
        painel_img.paste(im, (x, 120))
        dr.rectangle((x - 4, 116, x + 474, 924), outline="black", width=2)
        dr.text((x, 935), titulo, fill="black", font=_fonte(22))
        x += 510
    linhas = [
        f"Vazios: {metricas.get('vazios_detectados')} "
        f"(esperados {metricas.get('vazios_esperados', '—')})",
        f"F1 tolerante: {metricas['f1_tolerante']['f1']:.4f}"
        if 'f1_tolerante' in metricas else "",
        f"Diferença de área: "
        f"{metricas.get('diferenca_area_relativa', 0):.2%}",
        f"Dimensões: {metricas.get('dimensoes_obtidas_mm', metricas.get('dimensoes_mm'))}",
        f"Estado: {metricas.get('estado')}",
    ]
    if log_ops:
        aceitas = [r.operacao for r in log_ops if r.aceita]
        revertidas = [r.operacao for r in log_ops if not r.aceita]
        linhas.append(f"Operações aceitas: {', '.join(aceitas) or '—'}")
        linhas.append(f"Operações revertidas: {', '.join(revertidas) or '—'}")
    for i, ln in enumerate(x for x in linhas if x):
        dr.text((40, 990 + i * 34), ln, fill="black", font=_fonte(24))
    saida = pasta / "59_painel_aquisicao.png"
    painel_img.save(saida)
    return saida
