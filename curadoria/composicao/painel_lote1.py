"""Painel consolidado do lote 1 do E.4B.

Só apresenta: lê os artefatos já gravados pela API permanente e desenha.
Não adquire, não trata, não decide gate e não grava artefato de curadoria.
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

COMPLETOS = ("SU-039", "SU-024")
BLOQUEADOS = {
    "SU-053": ("BLOQUEADO — arbitragem\n3 suspeitas (cota 5.5) encostam nos\n"
               "encaixes do baguete (motivos #2 e #4).\nROIs dos 5 motivos: "
               "pendente_delimitacao.\nNao removido, nao gravado."),
    "SU-102": ("BLOQUEADO — cota nao reconcilia\narbitrado 21 x 12 mm; medido "
               "17,46 x 15,36 mm\nna escala do SU-053 (23,83 px/mm).\n"
               "Separacao por espessura OK.\nNao gravado."),
}


def _card(p):
    with tempfile.TemporaryDirectory() as d:
        pag = renderizar_pagina_png(RAIZ / p["fonte_pdf"], p["pagina_pdf"],
                                    600, Path(d) / "p")
        return aplicar_roi(pag, roi_norm=p["roi_norm"])


def _linha(axes, codigo, cfg):
    dest = RAIZ / "curadoria/contornos" / codigo
    met = json.loads((dest / "metricas.json").read_text())
    com = json.loads((dest / "contorno_comercial.json").read_text())
    bruto, p = adquirir(codigo, cfg)
    _, tratada, _ = tratar(codigo, bruto, p)

    m = (np.asarray(bruto.mascara) > 0).astype(np.uint8)
    t = (np.asarray(tratada) > 0).astype(np.uint8)
    pad = margem_px(p["largura_mm"], t.shape[1])
    tp = np.pad(t, pad)
    vet = rasterizar_vetor(com["contorno_externo"], com["vazios_internos"],
                           p["largura_mm"], p["altura_mm"],
                           tp.shape[1], tp.shape[0])
    dif = np.zeros((*tp.shape, 3), np.uint8) + 255
    dif[(tp > 0) & (vet == 0)] = (220, 40, 40)
    dif[(tp == 0) & (vet > 0)] = (40, 90, 220)
    dif[(tp > 0) & (vet > 0)] = (215, 215, 215)

    d = met["dimensoes_mm"]
    f1 = (met.get("f1_tolerante") or {}).get("f1")
    for ax, img, cmap, tit in (
            (axes[0], _card(p), None, f"card p.{p['pagina_pdf']}"),
            (axes[1], m, "gray_r", f"mascara bruta {m.shape[1]}x{m.shape[0]}px"),
            (axes[2], t, "gray_r", "bruto tratado"),
            (axes[3], vet, "gray_r", "comercial (vetor)"),
            (axes[4], dif, None, "diferenca")):
        ax.imshow(img, cmap=cmap) if cmap else ax.imshow(img)
        ax.set_title(tit, fontsize=8)
        ax.axis("off")
    axes[0].set_ylabel(codigo)
    axes[0].text(-0.08, 0.5, codigo, transform=axes[0].transAxes, rotation=90,
                 va="center", ha="center", fontsize=13, weight="bold")
    obs = (f"{d['largura']} x {d['altura']} mm | F1={f1} | "
           f"pontos={met['pontos_externo']} | vazios={met['vazios_detectados']} | "
           f"gates={'OK' if met['gates_aprovados'] else 'FALHOU'}\n"
           f"estrategia aceita: {met['estrategia_contaminacao']}")
    axes[2].text(0.5, -0.16, obs, transform=axes[2].transAxes, ha="center",
                 va="top", fontsize=8, family="monospace")


def gerar(saida: Path):
    cfg = carregar_config()
    n = len(COMPLETOS) + len(BLOQUEADOS)
    fig, ax = plt.subplots(n, 5, figsize=(19, 4.6 * n))
    for i, cod in enumerate(COMPLETOS):
        _linha(ax[i], cod, cfg)
    for j, (cod, txt) in enumerate(BLOQUEADOS.items(), start=len(COMPLETOS)):
        for a in ax[j]:
            a.axis("off")
        ax[j][0].text(-0.08, 0.5, cod, transform=ax[j][0].transAxes, rotation=90,
                      va="center", ha="center", fontsize=13, weight="bold")
        ax[j][2].text(0.5, 0.5, txt, transform=ax[j][2].transAxes, ha="center",
                      va="center", fontsize=10, family="monospace",
                      bbox=dict(boxstyle="round", fc="#ffecec", ec="#c00"))
    fig.suptitle("E.4B — lote 1 · card -> mascara -> bruto -> comercial -> diferenca",
                 fontsize=13, y=0.995)
    plt.tight_layout(rect=[0.015, 0, 1, 0.985])
    plt.savefig(saida, dpi=100)
    return saida


if __name__ == "__main__":
    print(gerar(RAIZ / "curadoria/composicao/painel_lote1_su039_su053_su102.png"))
