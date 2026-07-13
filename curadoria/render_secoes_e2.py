"""
Renderiza as seções da amostra Sprint E.2 (iteração ITER):
 - curadoria/contornos/GEO-XX-NNN_secao_itN.png (individuais, escala mm)
 - curadoria/contornos/XX-NNN_lado_a_lado_itN.png (comparativo: evidência
   de catálogo + seção traçada)
 - curadoria/contornos/amostra_painel_geral_itN.png (grade 3x3)
Valida cada seção com domain.validar_contornos e imprime o sinal de peso
(área × 2.71 g/cm³ vs peso de catálogo).
"""
import os
import sys

ITER = 8

sys.path.insert(0, "/home/bruno/Documentos/esquadriacore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch

from secoes_amostra_e2 import SECOES, contornos
from domain.entidades import GeometriaPadrao, validar_contornos

SAIDA = "/home/bruno/Documentos/esquadriacore/curadoria/contornos"

PESO_CATALOGO = {   # kg/m impresso no catálogo (referência Alcoa/Gold3)
    "GEO-SU-024": 1.024, "GEO-SU-025": 0.973, "GEO-SU-009": 0.908,
    "GEO-SU-056": 0.539, "GEO-SU-280": 1.006, "GEO-SU-228": 0.688,
    "GEO-SU-230": 0.954, "GEO-LG-003": 0.757, "GEO-LG-006": 0.677,
}


def caminho_poligono(ext, vazios):
    verts, cods = [], []
    for anel in [ext] + vazios:
        pts = list(anel) + [anel[0]]
        verts += pts
        cods += [Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY]
    return Path(verts, cods)


def desenhar(ax, ext, vazios, titulo=None):
    patch = PathPatch(caminho_poligono(ext, vazios), facecolor="0.25",
                      edgecolor="black", linewidth=0.8)
    ax.add_patch(patch)
    xs = [p[0] for p in ext]; ys = [p[1] for p in ext]
    m = 6
    ax.set_xlim(min(xs) - m, max(xs) + m)
    ax.set_ylim(min(ys) - m, max(ys) + m)
    ax.set_aspect("equal")
    ax.grid(True, which="both", color="0.85", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7)
    if titulo:
        ax.set_title(titulo, fontsize=9)


def comparativo(geo_id, it):
    """Evidência de catálogo em cima, seção traçada embaixo."""
    from PIL import Image
    cod = geo_id.replace("GEO-", "")
    evid = f"/home/bruno/Documentos/esquadriacore/curadoria/comparacao/{cod}_lado_a_lado.png"
    secao = f"{SAIDA}/{geo_id}_secao_it{it}.png"
    if not os.path.exists(evid):
        return None
    a, b = Image.open(evid), Image.open(secao)
    larg = 2200
    a = a.resize((larg, int(a.height * larg / a.width)), Image.LANCZOS)
    b = b.resize((larg, int(b.height * larg / b.width)), Image.LANCZOS)
    comp = Image.new("RGB", (larg, a.height + b.height + 20), "white")
    comp.paste(a, (0, 0))
    comp.paste(b, (0, a.height + 20))
    saida = f"{SAIDA}/{cod}_lado_a_lado_it{it}.png"
    comp.save(saida)
    return saida


def render_individual(geo_id, poly, it=1):
    # escala fixa (10 mm por polegada) => paredes com o mesmo peso visual
    # em todos os perfis, padrão SU-005
    ext, vazios = contornos(poly)
    largura = max(p[0] for p in ext) - min(p[0] for p in ext)
    altura = max(p[1] for p in ext) - min(p[1] for p in ext)
    fig, ax = plt.subplots(
        figsize=(max(largura / 10 + 2.2, 5), max(altura / 10 + 2.0, 4)),
        dpi=150)
    desenhar(ax, ext, vazios,
             f"{geo_id} — seção it{it} (em revisão) — {largura:.1f} × {altura:.1f} mm")
    ax.set_xlabel("mm", fontsize=8)
    ax.set_ylabel("mm", fontsize=8)
    fig.tight_layout()
    saida = f"{SAIDA}/{geo_id}_secao_it{it}.png"
    fig.savefig(saida, facecolor="white")
    plt.close(fig)
    return saida


def main():
    resultados = {}
    for geo_id, construir in SECOES.items():
        try:
            poly = construir()
            ext, vazios = contornos(poly)
            validar_contornos(GeometriaPadrao(
                id=geo_id, contorno_mm=[], status="em_revisao", versao="0",
                contorno_externo=ext, vazios_internos=vazios))
            area = poly.area
            peso_est = area * 2.71e-3          # mm² -> kg/m (Al 2.71 g/cm³)
            peso_cat = PESO_CATALOGO[geo_id]
            delta = (peso_est - peso_cat) / peso_cat * 100
            saida = render_individual(geo_id, poly, it=ITER)
            comparativo(geo_id, ITER)
            resultados[geo_id] = (poly, ext, vazios)
            print(f"{geo_id}: OK — {len(ext)} pts ext, {len(vazios)} vazios, "
                  f"área {area:.0f} mm² -> {peso_est:.3f} kg/m "
                  f"(catálogo {peso_cat:.3f}, Δ{delta:+.1f}%) -> {saida}")
        except Exception as e:
            print(f"{geo_id}: FALHOU — {e}")

    # painel geral 3x3 — janela de dados idêntica em todas as células
    # (mesma escala mm->px em todo o painel: espessura visual uniforme)
    fig, axs = plt.subplots(3, 3, figsize=(18, 12), dpi=120)
    JAN_X, JAN_Y = 124.0, 78.0
    for ax, (geo_id, (poly, ext, vazios)) in zip(axs.flat, resultados.items()):
        desenhar(ax, ext, vazios, geo_id)
        xs = [p[0] for p in ext]; ys = [p[1] for p in ext]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        ax.set_xlim(cx - JAN_X / 2, cx + JAN_X / 2)
        ax.set_ylim(cy - JAN_Y / 2, cy + JAN_Y / 2)
    for ax in axs.flat[len(resultados):]:
        ax.axis("off")
    fig.suptitle(f"Sprint E.2 — amostra 9 geometrias — seções it{ITER} (em revisão)",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(f"{SAIDA}/amostra_painel_geral_it{ITER}.png", facecolor="white")
    plt.close(fig)
    print(f"painel: {SAIDA}/amostra_painel_geral_it{ITER}.png")


if __name__ == "__main__":
    main()
