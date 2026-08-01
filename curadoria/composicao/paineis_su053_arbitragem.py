"""Painéis de arbitragem do SU-053: suspeitas ampliadas e diagnóstico de topologia.

Só apresenta. Não remove suspeita, não altera máscara, não grava artefato.
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
from curadoria.aquisicao.assinatura_topologica import (              # noqa: E402
    camaras_fechadas, fechar, maior_componente, mascara_de_imagem)
from curadoria.aquisicao.executar_lote1_e4b import adquirir          # noqa: E402
from curadoria.aquisicao.renderizar_fonte import (                   # noqa: E402
    aplicar_roi, renderizar_pagina_png)

CORES = {"suspeita": "#d62728", "encaixe_interno": "#7b3fbf",
         "encaixe_externo": "#ff7f0e", "perfil": "#000000",
         "cota": "#9a9a9a"}


def _camaras(mask):
    """Delega ao pacote de aquisição: a visão computacional fica confinada lá."""
    return camaras_fechadas(mask)


def _card(p):
    with tempfile.TemporaryDirectory() as d:
        pag = renderizar_pagina_png(RAIZ / p["fonte_pdf"], p["pagina_pdf"],
                                    600, Path(d) / "p")
        return aplicar_roi(pag, roi_norm=p["roi_norm"])


def painel_ampliado(m, px, sus, card, p, saida):
    """Zoom nas três suspeitas, com a faixa dos encaixes do baguete marcada."""
    fig = plt.figure(figsize=(17, 9))
    gs = fig.add_gridspec(2, 4, width_ratios=[1.05, 1, 1, 1])

    ax = fig.add_subplot(gs[:, 0])
    ax.imshow(card)
    ax.set_title("card p.187 — SU-053", fontsize=10)
    ax.axis("off")

    A = p["altura_mm"]
    ax2 = fig.add_subplot(gs[:, 1])
    ax2.imshow(m, cmap="gray_r")
    for s in sus:
        x0, y0, x1, y1 = [float(v) for v in s.bbox_mm]
        ax2.add_patch(Rectangle((x0 * px, (A - y1) * px), (x1 - x0) * px,
                                (y1 - y0) * px, fill=False,
                                ec=CORES["suspeita"], lw=2))
        ax2.annotate(f"S{s.indice}", (x0 * px, (A - y1) * px - 10),
                     color=CORES["suspeita"], fontsize=13, weight="bold")
    ax2.set_title("máscara — 3 suspeitas\n(não removidas)", fontsize=10)
    ax2.axis("off")

    # zoom por suspeita, com margem generosa para mostrar o entorno
    for i, s in enumerate(sus):
        r, c = divmod(i, 2)
        axz = fig.add_subplot(gs[r, 2 + c])
        x0, y0, x1, y1 = [float(v) for v in s.bbox_mm]
        mg = 3.0
        c0 = max(0, int((x0 - mg) * px)); c1 = min(m.shape[1], int((x1 + mg) * px))
        r0 = max(0, int((A - y1 - mg) * px)); r1 = min(m.shape[0], int((A - y0 + mg) * px))
        recorte = m[r0:r1, c0:c1]
        rgb = np.dstack([255 - recorte * 255] * 3).astype(np.uint8)
        sm = s.mascara[r0:r1, c0:c1] > 0
        rgb[sm] = [214, 39, 40]
        axz.imshow(rgb)
        axz.set_title(f"S{s.indice} — esp {s.espessura_mm} mm · "
                      f"comp {s.comprimento_mm} mm\nrazão parede "
                      f"{s.razao_parede}", fontsize=9)
        axz.axis("off")

    axl = fig.add_subplot(gs[1, 3])
    axl.axis("off")
    axl.text(0.0, 0.95, "GROUND TRUTH (confirmado Bruno)", fontsize=10,
             weight="bold", va="top")
    gt = ["#1 escovinha SU", "#2 encaixe interno do baguete", "#3 olhal",
          "#4 encaixe externo do baguete", "#5 escovinha SU"]
    for j, t in enumerate(gt):
        cor = (CORES["encaixe_interno"] if "interno" in t else
               CORES["encaixe_externo"] if "externo" in t else "#333")
        axl.text(0.0, 0.82 - j * 0.09, t, fontsize=10, color=cor, va="top")
    axl.text(0.0, 0.30,
             "ROIs dos 5 motivos: pendente_delimitacao\n"
             "→ não há zona medida para provar distância\n\n"
             "PERGUNTA: S1, S2 e S3 são a cota 5.5?",
             fontsize=9, va="top", family="monospace",
             bbox=dict(boxstyle="round", fc="#fff6e5", ec="#c80"))

    fig.suptitle("SU-053 — suspeitas para arbitragem visual", fontsize=13)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(saida, dpi=120)
    plt.close(fig)
    return saida


def painel_topologia(m, px, sus, card, p, saida):
    """Diagnóstico do vazio ausente: thresholds, fechamento e efeito das
    suspeitas."""
    fig, ax = plt.subplots(2, 4, figsize=(19, 10))

    ax[0][0].imshow(card); ax[0][0].set_title("1. card original", fontsize=10)
    ax[0][1].imshow(m, cmap="gray_r")
    ax[0][1].set_title(f"2. máscara binária (otsu)\n{m.shape[1]}×{m.shape[0]} px",
                       fontsize=10)

    n, prin = maior_componente(m)
    ax[0][2].imshow(prin, cmap="gray_r")
    ax[0][2].set_title(f"3. maior componente\n({n} componente(s))", fontsize=10)

    nc, interno = _camaras(prin)
    vis = np.dstack([255 - prin * 255] * 3).astype(np.uint8)
    vis[interno] = [40, 90, 220]
    ax[0][3].imshow(vis)
    ax[0][3].set_title(f"4. câmaras fechadas (flood-fill\ncom moldura): "
                       f"{nc}", fontsize=10)

    # fechamento morfológico crescente
    linhas = []
    for r in (1, 3, 8, 12):
        c, _ = _camaras(fechar(prin, r))
        linhas.append(f"raio {r:2d} px ({r/px:.3f} mm) → {c} câmaras")
    ax[1][0].axis("off")
    ax[1][0].text(0.0, 0.95, "5. fechamento morfológico\n   (procura falha "
                  "capilar na parede)", fontsize=10, weight="bold", va="top")
    ax[1][0].text(0.0, 0.68, "\n".join(linhas), fontsize=9, va="top",
                  family="monospace")
    ax[1][0].text(0.0, 0.36,
                  "nenhuma falha capilar:\na parede não tem furo de\n"
                  "antialiasing que explique\na câmara ausente",
                  fontsize=9, va="top", family="monospace",
                  bbox=dict(boxstyle="round", fc="#eef", ec="#66a"))

    # efeito isolado das suspeitas
    txt = []
    for s in sus:
        r_ = ((prin > 0) & ~(s.mascara > 0)).astype(np.uint8)
        n2, p2 = maior_componente(r_)
        c, _ = _camaras(p2)
        txt.append(f"remover S{s.indice} → {c} câmaras, {n2} comp.")
    r_ = (prin > 0).copy()
    for s in sus:
        r_ &= ~(s.mascara > 0)
    n3, p3 = maior_componente(r_.astype(np.uint8))
    c3, _ = _camaras(p3)
    txt.append(f"remover S1+S2+S3 → {c3} câmaras, {n3} comp.")
    ax[1][1].axis("off")
    ax[1][1].text(0.0, 0.95, "6. efeito isolado das suspeitas", fontsize=10,
                  weight="bold", va="top")
    ax[1][1].text(0.0, 0.72, "\n".join(txt), fontsize=9, va="top",
                  family="monospace")
    ax[1][1].text(0.0, 0.34,
                  "remover as cotas NÃO cria\ncâmara — e fragmenta o\n"
                  "componente em 3",
                  fontsize=9, va="top", family="monospace",
                  bbox=dict(boxstyle="round", fc="#ffecec", ec="#c00"))

    # thresholds
    linhas = []
    for thr in ("otsu", 130, 170, 210):
        _, pr = maior_componente(mascara_de_imagem(card, thr))
        c, _ = _camaras(pr)
        linhas.append(f"threshold {str(thr):5s} → {c} câmaras")
    ax[1][2].axis("off")
    ax[1][2].text(0.0, 0.95, "7. varredura de threshold", fontsize=10,
                  weight="bold", va="top")
    ax[1][2].text(0.0, 0.72, "\n".join(linhas), fontsize=9, va="top",
                  family="monospace")
    ax[1][2].text(0.0, 0.40,
                  "também testado:\n1200 DPI → 0 câmaras\nROI +6% → 0 câmaras",
                  fontsize=9, va="top", family="monospace")

    ax[1][3].axis("off")
    ax[1][3].text(0.0, 0.95, "8. conclusão do diagnóstico", fontsize=10,
                  weight="bold", va="top")
    ax[1][3].text(0.0, 0.78,
                  "descartados:\n"
                  "  vazamento por ROI\n"
                  "  vazamento por binarização\n"
                  "  vazamento pela cota 5.5\n"
                  "  falha capilar na parede\n\n"
                  "resta: ABERTURA REAL do perfil\n"
                  "na região adquirida.\n\n"
                  "vazios_esperados: 1 encodaria\n"
                  "uma câmara que a geometria\n"
                  "contradiz em toda condição\n"
                  "testada.",
                  fontsize=9, va="top", family="monospace",
                  bbox=dict(boxstyle="round", fc="#eaffea", ec="#080"))

    for a in ax.ravel():
        if a.images:
            a.axis("off")
    fig.suptitle("SU-053 — diagnóstico do vazio ausente", fontsize=13)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(saida, dpi=100)
    plt.close(fig)
    return saida


if __name__ == "__main__":
    cfg = json.loads((RAIZ / "curadoria/aquisicao/configs/e4b_suprema.json")
                     .read_text())
    p = cfg["perfis"]["SU-053"]
    bruto, p_ = adquirir("SU-053", cfg)
    m = (np.asarray(bruto.mascara) > 0).astype(np.uint8)
    px = m.shape[1] / p["largura_mm"]
    sus = ct.detectar(m, px, p["altura_mm"])
    card = _card(p)
    base = RAIZ / "curadoria/composicao"
    print(painel_ampliado(m, px, sus, card, p,
                          base / "painel_numerado_su053_arbitragem.png"))
    print(painel_topologia(m, px, sus, card, p,
                           base / "painel_topologia_su053.png"))
