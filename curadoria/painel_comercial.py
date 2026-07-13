"""
EsquadriaCore — curadoria/painel_comercial
===========================================
Prova viva do Contrato Mínimo de Consumo (ADR-009): carrega as geometrias
renderizáveis DIRETAMENTE do JSON oficial pela fronteira `contrato.consumo`
(zero hardcode de coordenadas) e desenha um painel único.

Cada célula mostra: código, nº de vazios e largura×altura do bounding-box.
Os vazios aparecem como furos (regra par-ímpar), comprovando visualmente sua
preservação. A orientação (externo CCW / vazios CW) é comprovada pelos testes
automatizados, não pela imagem.

Uso:  python3 curadoria/painel_comercial.py
Saída oficial: curadoria/contornos/painel_10_comerciais.png
(o teste automatizado gera em tmp_path e não sobrescreve a oficial)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch

from contrato import carregar_biblioteca

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "contornos", "painel_10_comerciais.png")


def _caminho(externo, vazios):
    verts, codigos = [], []
    for anel in [externo, *vazios]:
        pts = list(anel) + [anel[0]]
        verts += pts
        codigos += [Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY]
    return Path(verts, codigos)


def gerar(saida: str = SAIDA):
    """Fluxo obrigatório: JSON oficial -> contrato.consumo -> DTO -> painel.
    O painel NUNCA abre os JSONs diretamente."""
    bib = carregar_biblioteca()
    geoms = bib.renderizaveis()
    n = len(geoms)
    cols = 5
    linhas = (n + cols - 1) // cols

    # janela de dados uniforme => espessura visual consistente entre células
    jan_x, jan_y = 130.0, 78.0
    fig, axs = plt.subplots(linhas, cols, figsize=(4 * cols, 3.4 * linhas), dpi=130)
    axs = axs.flatten()

    for ax, g in zip(axs, geoms):
        patch = PathPatch(_caminho(g.contorno_externo, g.vazios_internos),
                          facecolor="0.25", edgecolor="black", linewidth=0.8)
        ax.add_patch(patch)
        bb = g.bounding_box
        cx = (bb.min_x + bb.max_x) / 2
        cy = (bb.min_y + bb.max_y) / 2
        ax.set_xlim(cx - jan_x / 2, cx + jan_x / 2)
        ax.set_ylim(cy - jan_y / 2, cy + jan_y / 2)
        ax.set_aspect("equal")
        ax.grid(True, color="0.88", linewidth=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=6)
        nv = len(g.vazios_internos)
        ax.set_title(
            f"{g.codigo}   ({nv} {'vazio' if nv == 1 else 'vazios'})\n"
            f"{g.largura_mm:.1f} × {g.altura_mm:.1f} mm",
            fontsize=8)

    for ax in axs[n:]:
        ax.axis("off")

    fig.suptitle(
        "EsquadriaCore — Contrato de Consumo v1.0 — 10 geometrias "
        "renderizáveis (carregadas do JSON oficial via contrato.consumo)",
        fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(saida, facecolor="white")
    plt.close(fig)
    print(f"painel gerado: {saida}  ({n} geometrias)")
    return saida


if __name__ == "__main__":
    gerar()
