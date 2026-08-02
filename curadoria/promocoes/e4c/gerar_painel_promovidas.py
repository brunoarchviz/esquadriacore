#!/usr/bin/env python3
"""Evidência das oito geometrias promovidas, carregadas PELO CONTRATO a partir
de dados/ — não da pasta de curadoria. Prova que a biblioteca oficial consegue
carregar e renderizar os perfis.

Rodar da raiz do repositório:
    PYTHONPATH=. .venv/bin/python curadoria/promocoes/e4c/gerar_painel_promovidas.py

O painel é EVIDÊNCIA, não fonte de verdade: a verdade é dados/."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

from contrato.consumo import carregar_biblioteca
from curadoria.promocao.modelos import PERFIS_E4B

RAIZ = Path(__file__).resolve().parents[0]
SAIDA_PNG = Path("curadoria/promocoes/e4c/painel_geometrias_promovidas.png")
SAIDA_JSON = Path("curadoria/promocoes/e4c/resumo_geometrias_promovidas.json")

bib = carregar_biblioteca()
por_id = {g.codigo: g for g in bib.geometrias}
assoc = {a.perfil_id: a for a in bib.associacoes}

fig, axes = plt.subplots(2, 4, figsize=(20, 11), facecolor="#141414")
fig.suptitle("E.4C — oito geometrias promovidas, carregadas de dados/ pelo contrato",
             color="#f0f0f0", fontsize=19, y=0.975)

resumo = {"lote": "E4B", "sprint": "E.4C",
          "fonte": "dados/ via contrato/consumo.carregar_biblioteca",
          "geometrias": []}

for ax, perfil in zip(axes.ravel(), PERFIS_E4B):
    gid = f"GEO-{perfil}"
    g = por_id[gid]
    ax.set_facecolor("#1c1c1c")

    ext = list(g.contorno_externo)
    ax.add_patch(MplPolygon(ext, closed=True, facecolor="#4a90d9",
                            edgecolor="#dfe9f5", linewidth=1.1, alpha=0.92))
    for v in g.vazios_internos:
        ax.add_patch(MplPolygon(list(v), closed=True, facecolor="#1c1c1c",
                                edgecolor="#dfe9f5", linewidth=0.9))

    bb = g.bounding_box
    ax.set_title(f"{gid}\n{bb.largura:.2f} × {bb.altura:.2f} mm",
                 color="#f0f0f0", fontsize=13, pad=8)
    ax.set_xlabel(f"{len(ext)} pts · {len(g.vazios_internos)} vazio(s) · "
                  f"{g.nivel_contorno.split('_',1)[1]}",
                  color="#9fb4c7", fontsize=9)
    ax.set_aspect("equal")
    ax.autoscale_view()
    m = max(bb.largura, bb.altura) * 0.10
    ax.set_xlim(bb.min_x - m, bb.max_x + m)
    ax.set_ylim(bb.min_y - m, bb.max_y + m)
    for s in ax.spines.values():
        s.set_color("#3a3a3a")
    ax.tick_params(colors="#6f6f6f", labelsize=7)

    pid = f"ALCOA-{perfil}"
    resumo["geometrias"].append({
        "id": gid, "perfil_id": pid,
        "largura_mm": round(bb.largura, 4), "altura_mm": round(bb.altura, 4),
        "pontos_externo": len(ext), "vazios": len(g.vazios_internos),
        "nivel_contorno": g.nivel_contorno, "renderizavel": g.renderizavel,
        "associacao_presente": pid in assoc,
        "geometria_da_associacao": assoc[pid].geometria_padrao_id if pid in assoc else None,
    })

fig.text(0.5, 0.015,
         "Renderizado a partir da biblioteca oficial. Nível 2 (renderizável "
         "comercial) — não é CAD e não autoriza fabricação. Este painel é "
         "evidência, não fonte de verdade.",
         ha="center", color="#8a8a8a", fontsize=10)
fig.tight_layout(rect=[0, 0.035, 1, 0.955])
SAIDA_PNG.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(SAIDA_PNG, dpi=115, facecolor=fig.get_facecolor())

resumo["total_geometrias_biblioteca"] = len(bib.geometrias)
resumo["total_associacoes_biblioteca"] = len(bib.associacoes)
SAIDA_JSON.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
print("gerado:", SAIDA_PNG, "e", SAIDA_JSON)
print("geometrias no painel:", len(resumo["geometrias"]))
