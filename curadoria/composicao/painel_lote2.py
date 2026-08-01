"""Painel consolidado do lote 2 do E.4B — quadro da janela.

Só apresenta: lê os artefatos já gravados e desenha. Não adquire, não trata,
não decide gate e não grava artefato de curadoria.
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

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from curadoria.aquisicao.executar_lote1_e4b import (                 # noqa: E402
    adquirir, carregar_config, margem_px, tratar)
from curadoria.aquisicao.extrair_contorno_raster import (            # noqa: E402
    rasterizar_vetor)
from curadoria.aquisicao.renderizar_fonte import (                   # noqa: E402
    aplicar_roi, renderizar_pagina_png)

PERFIS = ("SU-001", "SU-002", "SU-003")

# cotas internas a destacar por perfil: (valor, função)
DESTAQUES = {
    "SU-001": [("71 mm", "envelope"), ("33 mm", "envelope"),
               ("35 mm", "vão entre trilhos")],
    "SU-002": [("71 mm", "envelope — derivado"), ("47 mm", "envelope — cotado"),
               ("35 mm", "vão entre trilhos")],
    "SU-003": [("71 mm", "envelope"), ("26 mm", "envelope")],
}


def _card(p, cfg):
    g = p.get("fonte_geometrica_primaria", p)
    with tempfile.TemporaryDirectory() as d:
        pag = renderizar_pagina_png(RAIZ / p["fonte_pdf"], p["pagina_pdf"],
                                    600, Path(d) / "p")
        return aplicar_roi(pag, roi_norm=p["roi_norm"])


def _linha(axes, codigo, cfg):
    dest = RAIZ / "curadoria/contornos" / codigo
    met = json.loads((dest / "metricas.json").read_text())
    com = json.loads((dest / "contorno_comercial.json").read_text())
    p = cfg["perfis"][codigo]
    bruto, _ = adquirir(codigo, cfg)
    _, tratada, _ = tratar(codigo, bruto, p)

    m = (np.asarray(bruto.mascara) > 0).astype(np.uint8)
    t = (np.asarray(tratada) > 0).astype(np.uint8)
    tp = np.pad(t, margem_px(p["largura_mm"], t.shape[1]))
    vet = rasterizar_vetor(com["contorno_externo"], com["vazios_internos"],
                           p["largura_mm"], p["altura_mm"],
                           tp.shape[1], tp.shape[0])
    dif = np.full((*tp.shape, 3), 255, np.uint8)
    dif[(tp > 0) & (vet == 0)] = (220, 40, 40)
    dif[(tp == 0) & (vet > 0)] = (40, 90, 220)
    dif[(tp > 0) & (vet > 0)] = (215, 215, 215)

    for ax, img, cmap, tit in (
            (axes[0], _card(p, cfg), None, f"card p.{p['pagina_pdf']}"),
            (axes[1], m, "gray_r", f"máscara {m.shape[1]}×{m.shape[0]} px"),
            (axes[2], t, "gray_r", "bruto"),
            (axes[3], vet, "gray_r", "comercial (vetor)"),
            (axes[4], dif, None, "diferença")):
        ax.imshow(img, cmap=cmap) if cmap else ax.imshow(img)
        ax.set_title(tit, fontsize=8)
        ax.axis("off")

    axes[0].text(-0.10, 0.5, codigo, transform=axes[0].transAxes, rotation=90,
                 va="center", ha="center", fontsize=13, weight="bold")

    d = met["dimensoes_mm"]
    asp = d["largura"] / d["altura"]
    ops = met["estrategia_contaminacao"]
    dest_txt = "  ·  ".join(f"{v} {f}" for v, f in DESTAQUES[codigo])
    obs = (f"{d['largura']} × {d['altura']} mm   aspecto {asp:.4f}   "
           f"F1={met['f1_tolerante']['f1']}   pontos={met['pontos_externo']}   "
           f"componentes={met['metricas_extra']['componentes'] if 'metricas_extra' in met else 1}   "
           f"vazios={met['vazios_detectados']}   gates="
           f"{'OK' if met['gates_aprovados'] else 'FALHOU'}\n"
           f"operações: {ops}   ·   {dest_txt}")
    axes[2].text(0.5, -0.14, obs, transform=axes[2].transAxes, ha="center",
                 va="top", fontsize=8, family="monospace")


def gerar(saida: Path) -> Path:
    cfg = carregar_config()
    fig, ax = plt.subplots(len(PERFIS), 5, figsize=(19, 4.4 * len(PERFIS)))
    for i, cod in enumerate(PERFIS):
        _linha(ax[i], cod, cfg)
    fig.suptitle("E.4B — lote 2 · quadro da janela · "
                 "card → máscara → bruto → comercial → diferença", fontsize=13)
    plt.tight_layout(rect=[0.015, 0, 1, 0.98])
    plt.savefig(saida, dpi=100)
    plt.close(fig)
    return saida


if __name__ == "__main__":
    print(gerar(RAIZ / "curadoria/composicao/painel_lote2_su001_su002_su003.png"))
