"""Painel de delimitação dos motivos do SU-041, para arbitragem humana.

Só apresenta. Não atribui motivo, não altera zona, não toca no contorno, nas
dimensões nem nos artefatos, e não promove o perfil.

A pendência do SU-041 era diferente da do SU-053. Lá faltavam as cinco ROIs.
Aqui existia **uma zona já medida** — `[23.0, 28.0, 38.5, 33.0]` — anexada ao
`GAB-MA-DIAG-ESC-01` com atribuição pendente, e não se sabia a qual dos dois
motivos ela pertencia.

Resolvida pela arbitragem visual de 2026-07-28:

    M1 -> C5                     escovinha: boca estreita e lábios de retenção
    M2 -> zona manual            região estrutural (aba diagonal), não um bolso
    C6 -> olhal, descartado      formato C com serrilhas internas
    C1 -> incidental, descartado cobre só 13 % da zona do M2

Numeração: candidatos automáticos são **C1..Cn**; motivos confirmados são
**M1** e **M2**. Os dois conjuntos não se correspondem por posição.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import Rectangle                             # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from curadoria.aquisicao import motivos as mo                        # noqa: E402
from curadoria.aquisicao.assinatura_topologica import (              # noqa: E402
    maior_componente)
from curadoria.aquisicao.extrair_contorno_raster import extrair      # noqa: E402
from curadoria.aquisicao.renderizar_fonte import (                   # noqa: E402
    aplicar_roi, renderizar_pagina_png)

CONFIG = RAIZ / "curadoria/aquisicao/configs/e4b_suprema.json"
SAIDA = RAIZ / "curadoria/composicao/painel_delimitacao_motivos_su041.png"

# Resultado da arbitragem visual de 2026-07-28.
ARBITRAGEM = {"M1": "C5", "M2": "ZONA_MANUAL"}
DESCARTADOS = {
    "C6": ("olhal", "formato C com serrilhas internas — descartado para M1"),
    "C1": ("incidental", "cobre 13 % da zona do M2 — descartado para M2"),
}

MOTIVOS_A_LOCALIZAR = [
    ("M1", "GAB-ESCOVINHA-SU-01", "escovinha SU"),
    ("M2", "GAB-MA-DIAG-ESC-01", "mão de amigo diagonal"),
]

CORES = ["#1f77b4", "#7b3fbf", "#2ca02c", "#ff7f0e", "#d62728",
         "#17becf", "#bcbd22", "#e377c2", "#8c564b", "#000000",
         "#5b8c5a", "#a05195"]

# Zona já medida, hoje anexada ao M2 com atribuição pendente.
ZONA_MEDIDA = [23.0, 28.0, 38.5, 33.0]


def _perfil(cfg=None) -> dict:
    cfg = cfg or json.loads(CONFIG.read_text())
    return cfg["perfis"]["SU-041"]


def contorno(p: dict):
    """Máscara do maior componente, no referencial do card."""
    with tempfile.TemporaryDirectory() as d:
        pag = renderizar_pagina_png(RAIZ / p["fonte_pdf"], p["pagina_pdf"],
                                    600, Path(d) / "p")
        card = aplicar_roi(pag, roi_norm=p["roi_norm"])
    bruto = extrair("SU-041", card, p["largura_mm"], p["altura_mm"],
                    p["vazios_esperados"], threshold="otsu",
                    simplificacao_mm=0.05)
    m = (np.asarray(bruto.mascara) > 0).astype(np.uint8)
    _, prin = maior_componente(m)
    px = prin.shape[1] / p["largura_mm"]
    ys, _ = np.nonzero(prin)
    return card, prin, px, (ys.max() - ys.min() + 1) / px


def candidatos(mask, px, largura_mm, altura_mm) -> list:
    achados = mo.candidatos_de_motivo(mask, px, largura_mm, altura_mm)
    for b in achados:
        rot = f"C{b['candidato']}"
        b["papel"] = ("M1" if ARBITRAGEM["M1"] == rot else
                      DESCARTADOS[rot][0] if rot in DESCARTADOS else None)
        b["contem_zona_medida"] = _sobrepoe(b["zona"], ZONA_MEDIDA)
    return achados


def _sobrepoe(a, b) -> float:
    """Fração da zona medida coberta pela zona do candidato."""
    x0 = max(a[0], b[0]); y0 = max(a[1], b[1])
    x1 = min(a[2], b[2]); y1 = min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return round(inter / max(area_b, 1e-9), 3)


def _zoom(ax, mask, px, altura_mm, b, cor):
    # a cor do retângulo tem de contar a mesma história do título: verde para o
    # eleito, vermelho para descartado. Deixar a cor da paleta aqui fazia o C5
    # aparecer em vermelho, que nesta legenda quer dizer "descartado".
    rot_ = f"C{b['candidato']}"
    if b["papel"] == "M1":
        cor = "#0a7"
    elif rot_ in DESCARTADOS:
        cor = "#c00"
    x0, y0, x1, y1 = b["zona"]
    mg = 1.5
    c0 = max(0, int((x0 - mg) * px)); c1 = min(mask.shape[1], int((x1 + mg) * px))
    r0 = max(0, int((altura_mm - y1 - mg) * px))
    r1 = min(mask.shape[0], int((altura_mm - y0 + mg) * px))
    ax.imshow(np.dstack([255 - mask[r0:r1, c0:c1] * 255] * 3).astype(np.uint8))
    ax.add_patch(Rectangle((x0 * px - c0, (altura_mm - y1) * px - r0),
                           (x1 - x0) * px, (y1 - y0) * px,
                           fill=False, ec=cor, lw=2.5))
    if b["contem_zona_medida"]:
        z = ZONA_MEDIDA
        ax.add_patch(Rectangle((z[0] * px - c0, (altura_mm - z[3]) * px - r0),
                               (z[2] - z[0]) * px, (z[3] - z[1]) * px,
                               fill=False, ec="#000000", lw=1.6, ls="--"))
    f = b["forma"]
    rot = f"C{b['candidato']}"
    if b["papel"] == "M1":
        selo, cor_selo, peso = "  →  M1  escovinha SU", "#0a7", "bold"
    elif rot in DESCARTADOS:
        selo, cor_selo, peso = f"  ×  {DESCARTADOS[rot][0]}", "#c00", "bold"
    else:
        selo, cor_selo, peso = "", cor, "normal"
    ax.set_title(f"{rot}{selo}\n{b['area_mm2']:.2f} mm²  boca {b['boca_mm']:.2f}  "
                 f"circ {f.get('circularidade', 0):.2f}  ret "
                 f"{f.get('retangularidade', 0):.2f}  lábios "
                 f"{'sim' if b['labios'] else 'não'}",
                 fontsize=8, color=cor_selo if selo else cor, weight=peso)
    if rot in DESCARTADOS:
        ax.text(0.5, -0.06, DESCARTADOS[rot][1], transform=ax.transAxes,
                ha="center", va="top", fontsize=7.5, color="#c00")
    ax.axis("off")


def gerar(saida: Path = SAIDA) -> Path:
    p = _perfil()
    card, mask, px, altura_mm = contorno(p)
    cand = candidatos(mask, px, p["largura_mm"], altura_mm)
    n = len(cand)
    linhas_zoom = (n + 4) // 5

    fig = plt.figure(figsize=(21, 6 + 3.2 * linhas_zoom))
    gs = fig.add_gridspec(1 + linhas_zoom + 1, 5,
                          height_ratios=[2.4] + [1] * linhas_zoom + [1.1])

    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(card)
    ax.set_title(f"A — card SU-041, Alcoa p.{p['pagina_pdf']}", fontsize=10)
    ax.axis("off")

    ax = fig.add_subplot(gs[0, 1])
    ax.imshow(255 - mask * 255, cmap="gray")
    for b in cand:
        x0, y0, x1, y1 = b["zona"]
        rot = f"C{b['candidato']}"
        eleito = b["papel"] == "M1"
        cor = "#0a7" if eleito else ("#c00" if rot in DESCARTADOS
                                     else CORES[(b["candidato"] - 1) % len(CORES)])
        ax.add_patch(Rectangle((x0 * px, (altura_mm - y1) * px),
                               (x1 - x0) * px, (y1 - y0) * px, fill=False,
                               ec=cor, lw=3 if eleito else 2))
        ax.annotate(f"{rot} = M1" if eleito else rot,
                    (x0 * px, (altura_mm - y1) * px - 9), color=cor,
                    fontsize=12 if eleito else 11, weight="bold")
    z = ZONA_MEDIDA
    ax.add_patch(Rectangle((z[0] * px, (altura_mm - z[3]) * px),
                           (z[2] - z[0]) * px, (z[3] - z[1]) * px,
                           fill=False, ec="#000000", lw=2.2, ls="--"))
    ax.annotate("M2 = zona manual", (z[0] * px, (altura_mm - z[3]) * px - 24),
                color="#000000", fontsize=11, weight="bold")
    ax.set_title(f"B — arbitragem aplicada · {n} candidatos\n"
                 f"verde = eleito · vermelho = descartado · "
                 f"tracejado = zona manual\n{p['largura_mm']:.2f} × "
                 f"{altura_mm:.2f} mm", fontsize=9)
    ax.axis("off")

    ax = fig.add_subplot(gs[0, 2])
    ax.axis("off")
    ax.text(0, 1.0, "MOTIVOS CONFIRMADOS", fontsize=11, weight="bold", va="top")
    for i, (m, gid, nome) in enumerate(MOTIVOS_A_LOCALIZAR):
        ax.text(0, 0.88 - i * 0.13, f"{m} = {nome}\n     {gid}",
                fontsize=10, va="top")
    ax.text(0, 0.52,
            "ARBITRAGEM APLICADA (2026-07-28)\n\n"
            "  M1  ->  C5\n"
            "  M2  ->  zona manual confirmada\n\n"
            "  C6  x  olhal, descartado p/ M1\n"
            "  C1  x  incidental, descartado p/ M2\n\n"
            "C = candidato automático\nM = motivo confirmado",
            fontsize=9, va="top", family="monospace",
            bbox=dict(boxstyle="round", fc="#eaffea", ec="#080"))

    ax = fig.add_subplot(gs[0, 3:])
    ax.axis("off")
    ax.text(0, 1.0, "A RESOLUÇÃO", fontsize=11, weight="bold", va="top")
    ax.text(0, 0.88,
            "M1 = GAB-ESCOVINHA-SU-01\n"
            "  candidato : C5\n"
            "  zona      : [12.00, 19.55, 17.02, 24.57]\n"
            "  razão     : boca estreita + lábios de\n"
            "              retenção\n\n"
            "M2 = GAB-MA-DIAG-ESC-01\n"
            f"  candidato : nenhum\n"
            f"  zona      : {ZONA_MEDIDA}\n"
            "  método    : zona_manual\n"
            "  razão     : região ESTRUTURAL composta\n"
            "              (aba diagonal), não um bolso —\n"
            "              por isso nenhum candidato\n"
            "              automático corresponde\n\n"
            "eixos: origem no canto inferior esquerdo,\n"
            "x para a direita, y para CIMA, em mm.\n"
            "a zona do M2 atinge y = 33,0, o topo real.",
            fontsize=9, va="top", family="monospace")

    for i, b in enumerate(cand):
        linha, col = divmod(i, 5)
        _zoom(fig.add_subplot(gs[1 + linha, col]), mask, px, altura_mm, b,
              CORES[(b["candidato"] - 1) % len(CORES)])

    ax = fig.add_subplot(gs[-1, :])
    ax.axis("off")
    cab = (f"{'cand':>5} {'área mm²':>9} {'boca':>6} {'circ':>6} {'ret':>6} "
           f"{'lábios':>7}  {'zona [x_min, y_min, x_max, y_max] mm':<32} "
           f"{'cobre M2':>10} {'papel':>14}")
    linhas = [cab, "-" * len(cab)]
    for b in cand:
        f = b["forma"]
        x0, y0, x1, y1 = b["zona"]
        cob = f"{b['contem_zona_medida'] * 100:.0f} %" if b["contem_zona_medida"] else "—"
        papel = ("M1" if b["papel"] == "M1" else
                 f"× {b['papel']}" if b["papel"] else "")
        linhas.append(
            f"{'C' + str(b['candidato']):>5} {b['area_mm2']:9.2f} "
            f"{b['boca_mm']:6.2f} {f.get('circularidade', 0):6.2f} "
            f"{f.get('retangularidade', 0):6.2f} "
            f"{'sim' if b['labios'] else 'não':>7}  "
            f"[{x0:6.2f}, {y0:6.2f}, {x1:6.2f}, {y1:6.2f}]{'':<4} "
            f"{cob:>10} {papel:>14}")
    linhas += ["",
               "ARBITRAGEM:   M1 = C5   ·   M2 = zona manual "
               f"{ZONA_MEDIDA}   ·   C6 descartado (olhal)   ·   "
               "C1 descartado (incidental)"]
    ax.text(0, 1.0, "\n".join(linhas), fontsize=8.5, va="top", family="monospace")

    fig.suptitle("SU-041 — arbitragem das zonas, aplicada em 2026-07-28",
                 fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.975])
    plt.savefig(saida, dpi=110)
    plt.close(fig)
    return saida


if __name__ == "__main__":
    print(gerar())
