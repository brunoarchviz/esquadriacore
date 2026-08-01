"""Painel dos gabaritos — um perfil pode ter VÁRIOS motivos e várias ocorrências.

Nunca rotular o perfil com um gabarito só: o título lista TODOS os motivos
confirmados, com a contagem de ocorrências quando houver mais de uma.
Uso: python3 curadoria/composicao/gerar_painel_motivos.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/bruno/Documentos/esquadriacore")
from PIL import Image, ImageDraw

from curadoria.aquisicao import renderizar_diferenca as rd

BASE = Path(__file__).resolve().parent.parent.parent
CFG = json.loads((BASE / "curadoria/aquisicao/configs/e4b_suprema.json").read_text())
SAIDA = BASE / "curadoria/composicao/painel_e4b_gabaritos.png"
ARQ = ["30_contorno_comercial.json", "30_contorno_recon.json",
       "20_contorno_bruto.json"]

PAPEL = {
    "SU-040": "comercial (homologável)", "SU-041": "comercial (homologável)",
    "SU-056": "regressão — já homologado", "SU-024": "reconhecimento",
    "LG-004": "reconhecimento", "LG-006": "reconhecimento",
    "SU-009": "reconhecimento (aba corrigida)",
}
ORDEM = ["SU-040", "SU-041", "SU-056", "SU-024", "LG-004", "LG-006", "SU-009"]


def rotulos(perfil: dict) -> list[str]:
    """Um rótulo por motivo, com × N quando há mais de uma ocorrência."""
    contagem: dict[str, int] = {}
    for m in perfil.get("motivos", []):
        contagem[m["id"]] = contagem.get(m["id"], 0) + 1
    return [f"[{g}]" + (f" × {n}" if n > 1 else "")
            for g, n in sorted(contagem.items())]


def main() -> None:
    cols, cell = 4, 470
    linhas = (len(ORDEM) + cols - 1) // cols
    img = Image.new("RGB", (cols * cell + 40, linhas * (cell + 155) + 130),
                    "white")
    dr = ImageDraw.Draw(img)
    dr.text((30, 22), "EsquadriaCore — E.4B — motivos geométricos por perfil",
            fill="black", font=rd._fonte(34))
    dr.text((30, 66),
            "Um gabarito é um motivo LOCAL, não uma categoria do perfil: o "
            "mesmo perfil pode ter vários motivos e várias ocorrências do "
            "mesmo motivo.",
            fill=(90, 90, 90), font=rd._fonte(19))
    dr.text((30, 92),
            "Orientação e posição são atributos de cada ocorrência, medidos no "
            "referencial local normalizado — não valem como regra de família.",
            fill=(90, 90, 90), font=rd._fonte(19))

    for i, cod in enumerate(ORDEM):
        p = CFG["perfis"].get(cod) or CFG["p4_reconhecimento"][cod]
        pasta = BASE / "curadoria/contornos" / cod
        src = next((pasta / a for a in ARQ if (pasta / a).exists()), None)
        if src is None:
            continue
        d = json.loads(src.read_text())
        L = d["dimensoes_mm"]["largura"]
        A = d["dimensoes_mm"]["altura"]
        im = rd._render_vetor(d["contorno_externo"], d["vazios_internos"],
                              L, A, escala_px_mm=9)
        im.thumbnail((cell - 50, cell - 50), Image.Resampling.LANCZOS)
        cx = 20 + (i % cols) * cell
        cy = 130 + (i // cols) * (cell + 155)
        dr.rectangle((cx, cy, cx + cell - 30, cy + cell - 30),
                     outline=(205, 205, 205), width=1)
        img.paste(im, (cx + (cell - 30 - im.width) // 2,
                       cy + (cell - 30 - im.height) // 2))
        y = cy + cell - 24
        dr.text((cx + 4, y), f"{cod}  ·  {L:.1f} × {A:.1f} mm",
                fill="black", font=rd._fonte(20))
        y += 21
        dr.text((cx + 4, y), PAPEL.get(cod, ""),
                fill=(110, 110, 110), font=rd._fonte(17))
        for rot in rotulos(p):
            y += 23
            dr.text((cx + 4, y), rot, fill=(20, 20, 20), font=rd._fonte(18))
        pend = [m for m in p.get("motivos", [])
                if m.get("atribuicao_geometrica") == "pendente"]
        if pend:
            y += 23
            dr.text((cx + 4, y), "atribuição do bolso medido: pendente",
                    fill=(150, 90, 0), font=rd._fonte(16))
    img.save(SAIDA)
    print("painel salvo:", SAIDA, img.size)
    for cod in ORDEM:
        p = CFG["perfis"].get(cod) or CFG["p4_reconhecimento"][cod]
        print(f"  {cod}: {' '.join(rotulos(p))}")


if __name__ == "__main__":
    main()
