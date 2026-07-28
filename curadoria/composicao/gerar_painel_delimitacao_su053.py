"""Painel de delimitação dos motivos do SU-053, para arbitragem humana.

Só apresenta. Não confirma ROI, não altera o config, não grava artefato de
curadoria e não promove candidato.

Lê exclusivamente `curadoria/aquisicao/configs/e4b_suprema.json` e usa os
módulos permanentes de `curadoria/aquisicao/`.

Numeração: os candidatos vêm do detector de bolsos e são **C1..C10**. Os motivos
confirmados pelo Bruno são **M1..M5**. Os dois conjuntos não se correspondem por
posição — o mapeamento é justamente o que esta arbitragem produz.
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

from curadoria.aquisicao import contaminacao as ct                   # noqa: E402
from curadoria.aquisicao import motivos as mo                        # noqa: E402
from curadoria.aquisicao.assinatura_topologica import (              # noqa: E402
    maior_componente)
from curadoria.aquisicao.extrair_contorno_raster import extrair      # noqa: E402
from curadoria.aquisicao.renderizar_fonte import (                   # noqa: E402
    aplicar_roi, renderizar_pagina_png)

CONFIG = RAIZ / "curadoria/aquisicao/configs/e4b_suprema.json"
SAIDA = RAIZ / "curadoria/composicao/painel_delimitacao_motivos_su053.png"

STATUS_CANDIDATO = "CANDIDATA_PARA_ARBITRAGEM_BRUNO"

MOTIVOS_A_LOCALIZAR = [
    ("M1", "escovinha SU"),
    ("M2", "encaixe interno do baguete"),
    ("M3", "olhal"),
    ("M4", "encaixe externo do baguete"),
    ("M5", "escovinha SU"),
]

# 10 cores distinguíveis; nenhuma delas codifica classe — só identidade do
# candidato, para o Bruno conseguir apontar "M3 = C2".
CORES = ["#1f77b4", "#7b3fbf", "#2ca02c", "#ff7f0e", "#d62728",
         "#17becf", "#bcbd22", "#e377c2", "#8c564b", "#000000"]


def _perfil(cfg=None) -> dict:
    cfg = cfg or json.loads(CONFIG.read_text())
    return cfg["perfis"]["SU-053"]


def contorno_limpo(p: dict):
    """Máscara do SU-053 sem a cota 5.5, no referencial da fonte semântica.

    A aquisição usa a altura do bbox CONTAMINADO — é a altura real do recorte na
    fonte, necessária para o gate de aspecto. A altura limpa emerge depois da
    remoção e é devolvida junto.
    """
    altura_aq = p["dimensao_altura"]["valor_bbox_contaminado_mm"]
    with tempfile.TemporaryDirectory() as d:
        pag = renderizar_pagina_png(RAIZ / p["fonte_pdf"], p["pagina_pdf"],
                                    600, Path(d) / "p")
        card = aplicar_roi(pag, roi_norm=p["roi_norm"])
    bruto = extrair("SU-053", card, p["largura_mm"], altura_aq,
                    p["vazios_esperados"] or None, threshold="otsu",
                    simplificacao_mm=0.05)
    m = (np.asarray(bruto.mascara) > 0).astype(np.uint8)
    px = m.shape[1] / p["largura_mm"]
    cota = np.zeros_like(m, bool)
    for s in ct.detectar(m, px, altura_aq):
        cota |= (s.mascara > 0)
    _, limpo = maior_componente(((m > 0) & ~cota).astype(np.uint8))
    ys, _ = np.nonzero(limpo)
    return card, limpo, px, (ys.max() - ys.min() + 1) / px


def candidatos(limpo, px, largura_mm, altura_mm) -> list:
    """Todos os bolsos, numerados. Nenhum é promovido a motivo confirmado."""
    achados = mo.candidatos_de_motivo(limpo, px, largura_mm, altura_mm)
    for b in achados:
        b["status"] = STATUS_CANDIDATO
    return achados


def _zoom(ax, limpo, px, altura_mm, b, cor):
    x0, y0, x1, y1 = b["zona"]
    mg = 1.5
    c0 = max(0, int((x0 - mg) * px)); c1 = min(limpo.shape[1], int((x1 + mg) * px))
    r0 = max(0, int((altura_mm - y1 - mg) * px))
    r1 = min(limpo.shape[0], int((altura_mm - y0 + mg) * px))
    ax.imshow(np.dstack([255 - limpo[r0:r1, c0:c1] * 255] * 3).astype(np.uint8))
    ax.add_patch(Rectangle((x0 * px - c0, (altura_mm - y1) * px - r0),
                           (x1 - x0) * px, (y1 - y0) * px,
                           fill=False, ec=cor, lw=2.5))
    f = b["forma"]
    ax.set_title(f"C{b['candidato']}   {b['area_mm2']:.2f} mm²  boca {b['boca_mm']:.2f}\n"
                 f"circ {f.get('circularidade', 0):.2f} · ret "
                 f"{f.get('retangularidade', 0):.2f} · lábios "
                 f"{'sim' if b['labios'] else 'não'}",
                 fontsize=8, color=cor)
    ax.axis("off")


def gerar(saida: Path = SAIDA) -> Path:
    p = _perfil()
    card, limpo, px, altura_mm = contorno_limpo(p)
    cand = candidatos(limpo, px, p["largura_mm"], altura_mm)

    fig = plt.figure(figsize=(21, 15))
    gs = fig.add_gridspec(4, 5, height_ratios=[2.4, 1, 1, 1.15])

    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(card)
    ax.set_title(f"A — fonte semântica\ncard SU-053 Alcoa p.{p['pagina_pdf']}",
                 fontsize=10)
    ax.axis("off")

    ax = fig.add_subplot(gs[0, 1])
    ax.imshow(255 - limpo * 255, cmap="gray")
    for b in cand:
        x0, y0, x1, y1 = b["zona"]
        cor = CORES[(b["candidato"] - 1) % len(CORES)]
        ax.add_patch(Rectangle((x0 * px, (altura_mm - y1) * px),
                               (x1 - x0) * px, (y1 - y0) * px,
                               fill=False, ec=cor, lw=2))
        ax.annotate(f"C{b['candidato']}", (x0 * px, (altura_mm - y1) * px - 9),
                    color=cor, fontsize=12, weight="bold")
    ax.set_title(f"B — {len(cand)} candidatos numerados\n"
                 f"contorno limpo {p['largura_mm']:.2f} × {altura_mm:.2f} mm",
                 fontsize=10)
    ax.axis("off")

    ax = fig.add_subplot(gs[0, 2])
    ax.axis("off")
    ax.text(0, 1.0, "MOTIVOS A LOCALIZAR", fontsize=11, weight="bold", va="top")
    for i, (m, nome) in enumerate(MOTIVOS_A_LOCALIZAR):
        ax.text(0, 0.88 - i * 0.10, f"{m} = {nome}", fontsize=10, va="top")
    ax.text(0, 0.32,
            "C = candidato automático\nM = motivo confirmado\n\n"
            "Os números NÃO se correspondem.\n"
            "Ex.: M1 pode ser o C7.\n\n"
            "Nenhum candidato está confirmado:\n"
            f"todos em {STATUS_CANDIDATO}.",
            fontsize=9, va="top", family="monospace",
            bbox=dict(boxstyle="round", fc="#fff6e5", ec="#c80"))

    ax = fig.add_subplot(gs[0, 3:])
    ax.axis("off")
    ax.text(0, 1.0, "EIXOS E ORIENTAÇÃO", fontsize=11, weight="bold", va="top")
    ax.text(0, 0.86,
            "origem  : canto inferior esquerdo do contorno limpo\n"
            "x cresce: para a direita\n"
            "y cresce: para CIMA\n"
            "unidade : milímetro\n\n"
            f"largura : {p['largura_mm']:.2f} mm  (cota confirmada)\n"
            f"altura  : {altura_mm:.2f} mm  (medição limpa)\n"
            f"          {p['altura_mm']:.2f} mm  (cota nominal TMS-053)\n\n"
            "zona = [x_min, y_min, x_max, y_max]",
            fontsize=9, va="top", family="monospace")

    # ampliações de TODOS os candidatos
    for i, b in enumerate(cand[:10]):
        linha, col = divmod(i, 5)
        _zoom(fig.add_subplot(gs[1 + linha, col]), limpo, px, altura_mm, b,
              CORES[(b["candidato"] - 1) % len(CORES)])

    ax = fig.add_subplot(gs[3, :])
    ax.axis("off")
    cab = (f"{'cand':>5} {'área mm²':>9} {'boca':>6} {'circ':>6} {'ret':>6} "
           f"{'lábios':>7}   zona [x_min, y_min, x_max, y_max] mm      "
           f"{'larg':>6} {'alt':>6}")
    linhas = [cab, "-" * len(cab)]
    for b in cand:
        f = b["forma"]
        x0, y0, x1, y1 = b["zona"]
        linhas.append(
            f"{'C' + str(b['candidato']):>5} {b['area_mm2']:9.2f} "
            f"{b['boca_mm']:6.2f} {f.get('circularidade', 0):6.2f} "
            f"{f.get('retangularidade', 0):6.2f} "
            f"{'sim' if b['labios'] else 'não':>7}   "
            f"[{x0:6.2f}, {y0:6.2f}, {x1:6.2f}, {y1:6.2f}]      "
            f"{x1 - x0:6.2f} {y1 - y0:6.2f}")
    linhas.append("")
    linhas.append("RESPOSTA ESPERADA:   M1 = C?    M2 = C?    M3 = C?    "
                  "M4 = C?    M5 = C?")
    ax.text(0, 1.0, "\n".join(linhas), fontsize=8.5, va="top",
            family="monospace")

    fig.suptitle("SU-053 — delimitação dos motivos para arbitragem "
                 "(nenhum candidato confirmado)", fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.975])
    plt.savefig(saida, dpi=110)
    plt.close(fig)
    return saida


if __name__ == "__main__":
    print(gerar())
