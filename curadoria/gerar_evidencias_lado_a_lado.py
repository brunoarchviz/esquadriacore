"""
Gera as evidências *_lado_a_lado.png da amostra Sprint E.2 (9 geometrias).
Recorte automático do card de cada perfil: separadores horizontais/verticais
+ posição do rótulo do código (texto nativo via pdftotext -bbox; Alcoa
Suprema via tesseract TSV). Gold 4 (layout livre) usa janelas fixas
verificadas visualmente.
"""
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = "/home/bruno/Documentos/esquadriacore"
SCRATCH = os.path.dirname(os.path.abspath(__file__))
DPI = 300
ALCOA_SU = f"{BASE}/dados_exemplo/catalago-alcoa (1).pdf"
VITRALSUL = f"{BASE}/dados_exemplo/PERFIS-DE-ALUMINIO-02-07-2026.pdf"
GOLD3 = f"{BASE}/dados_exemplo/alcoa_gold3.pdf"
GOLD4 = f"{BASE}/dados_exemplo/alcoa_gold-4.pdf"

# geo -> (código, [(pdf, pág, rótulo_no_pdf, header_prefixo, metodo)])
# metodo: "ocr" (Alcoa Suprema), "nativo" (bbox), "fixo:x0,y0,x1,y1" (px@100dpi)
AMOSTRA = {
    "GEO-SU-024": ("SU-024", [(ALCOA_SU, 178, "SU-024", "ALCOA — Suprema", "ocr"),
                              (VITRALSUL, 76, "SU-024", "VITRAL SUL — Nobile 2.5", "nativo")]),
    "GEO-SU-025": ("SU-025", [(ALCOA_SU, 178, "SU-025", "ALCOA — Suprema", "ocr"),
                              (VITRALSUL, 76, "SU-025", "VITRAL SUL — Nobile 2.5", "nativo")]),
    "GEO-SU-009": ("SU-009", [(ALCOA_SU, 172, "SU-009", "ALCOA — Suprema", "ocr"),
                              (VITRALSUL, 74, "SU-009", "VITRAL SUL — Nobile 2.5", "nativo")]),
    "GEO-SU-056": ("SU-056", [(ALCOA_SU, 188, "SU-056", "ALCOA — Suprema", "ocr"),
                              (VITRALSUL, 84, "SU-056", "VITRAL SUL — Nobile 2.5", "nativo")]),
    "GEO-SU-280": ("SU-280", [(ALCOA_SU, 182, "SU-280", "ALCOA — Suprema", "ocr"),
                              (VITRALSUL, 86, "SU-280", "VITRAL SUL — Nobile 2.5", "nativo")]),
    "GEO-SU-228": ("SU-228", [(ALCOA_SU, 175, "SU-228", "ALCOA — Suprema", "ocr"),
                              (VITRALSUL, 77, "SU-228", "VITRAL SUL — Nobile 2.5", "nativo")]),
    "GEO-SU-230": ("SU-230", [(ALCOA_SU, 175, "SU-230", "ALCOA — Suprema", "ocr"),
                              (VITRALSUL, 77, "SU-230", "VITRAL SUL — Nobile 2.5", "nativo")]),
    "GEO-LG-003": ("LG-003", [(GOLD3, 45, "LG-003", "ALCOA — Gold 3", "nativo"),
                              (GOLD4, 29, "LG003", "ALCOA — IV Gold (Gold 4)", "fixo:80,125,590,310")]),
    "GEO-LG-006": ("LG-006", [(GOLD3, 51, "LG-006", "ALCOA — Gold 3", "nativo"),
                              (GOLD4, 39, "LG006", "ALCOA — IV Gold (Gold 4)", "fixo:90,120,330,400")]),
}

_cache_pag = {}


def render(pdf, pag):
    """Retorna (imagem PIL, caminho do jpg original do pdftoppm)."""
    chave = (pdf, pag)
    if chave in _cache_pag:
        return _cache_pag[chave]
    stem = os.path.join(
        SCRATCH, f"pg_{re.sub(r'[^a-z0-9]', '', os.path.basename(pdf).lower())[:10]}_{pag}")
    subprocess.run(["pdftoppm", "-f", str(pag), "-l", str(pag), "-jpeg",
                    "-r", str(DPI), pdf, stem], check=True)
    arq = [f for f in os.listdir(SCRATCH)
           if f.startswith(os.path.basename(stem) + "-") and f.endswith(".jpg")][0]
    caminho = os.path.join(SCRATCH, arq)
    img = Image.open(caminho).convert("RGB")
    _cache_pag[chave] = (img, caminho)
    return img, caminho


def rotulo_nativo(pdf, pag, rotulo):
    """Posição (px @DPI) do rótulo via pdftotext -bbox."""
    xml = subprocess.run(["pdftotext", "-bbox", "-f", str(pag), "-l", str(pag),
                          pdf, "-"], capture_output=True, text=True).stdout
    esc = DPI / 72.0
    for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" '
                         r'xMax="([\d.]+)" yMax="([\d.]+)">([^<]+)</word>', xml):
        if m.group(5).strip() == rotulo:
            x0, y0, x1, y1 = (float(m.group(i)) * esc for i in range(1, 5))
            return (x0 + x1) / 2, (y0 + y1) / 2
    raise RuntimeError(f"rótulo {rotulo} não achado em {pdf} pág {pag}")


_cache_tsv = {}


def rotulo_ocr(pdf, pag, rotulo, caminho_jpg):
    """Posição (px @DPI) do rótulo via tesseract TSV na página inteira.
    Usa o jpg original do pdftoppm — re-salvar via PIL degrada o OCR."""
    chave = (pdf, pag)
    if chave not in _cache_tsv:
        tsv = subprocess.run(["tesseract", caminho_jpg, "stdout", "-l",
                              "por+eng", "--psm", "6", "tsv"],
                             capture_output=True, text=True).stdout
        _cache_tsv[chave] = tsv
    limpo = lambda s: re.sub(r"[^A-Z0-9-]", "", s.upper())
    for linha in _cache_tsv[chave].splitlines()[1:]:
        c = linha.split("\t")
        if len(c) >= 12 and limpo(c[11]) == rotulo:
            x, y, w, h = int(c[6]), int(c[7]), int(c[8]), int(c[9])
            return x + w / 2, y + h / 2
    raise RuntimeError(f"OCR não achou {rotulo} em {pdf} pág {pag}")


def recortar_card(img, cx, cy):
    """Card = célula entre separadores horizontais/verticais contendo o rótulo,
    aparada ao bounding box da tinta."""
    g = np.array(img.convert("L"))
    dark = g < 140
    alt, larg = dark.shape

    # 0.75: separadores reais medem 0.838-0.905 (Alcoa/VS/Gold3); ruído máximo
    # medido foi 0.655 (linha de piso do SU-228) — margem dos dois lados
    frac_linha = dark.mean(axis=1)
    seps_h = [0] + [y for y in range(alt) if frac_linha[y] > 0.75] + [alt - 1]
    topo = max(y for y in seps_h if y < cy)
    fundo = min(y for y in seps_h if y > cy)

    # 0.93: só molduras/divisórias reais atravessam a banda inteira; paredes
    # bold de desenho chegam a ~0.76 (SU-009) e não podem cortar o card
    faixa = dark[topo + 10:fundo - 10, :]
    frac_col = faixa.mean(axis=0)
    seps_v = [0] + [x for x in range(larg) if frac_col[x] > 0.93] + [larg - 1]
    esq = max(x for x in seps_v if x < cx)
    dire = min(x for x in seps_v if x > cx)

    celula = dark[topo + 10:fundo - 10, esq + 10:dire - 10]
    linhas = np.where(celula.any(axis=1))[0]
    cols = np.where(celula.any(axis=0))[0]
    if len(linhas) == 0:
        raise RuntimeError("célula vazia")
    pad = 25
    y0 = max(0, topo + 10 + linhas[0] - pad)
    y1 = min(alt, topo + 10 + linhas[-1] + pad)
    x0 = max(0, esq + 10 + cols[0] - pad)
    x1 = min(larg, esq + 10 + cols[-1] + pad)
    return img.crop((x0, y0, x1, y1))


def peso_nativo(pdf, pag, rotulo):
    txt = subprocess.run(["pdftotext", "-f", str(pag), "-l", str(pag),
                          "-layout", pdf, "-"], capture_output=True,
                         text=True).stdout
    linhas = txt.splitlines()
    for i, ln in enumerate(linhas):
        if rotulo in ln:
            m = re.search(r"(\d+[.,]\d+)\s*[Kk]g/m", ln)
            for prox in linhas[i:i + 3]:
                m = re.search(r"(\d+[.,]\d+)\s*[Kk]g/m", prox)
                if m:
                    return m.group(1) + " kg/m"
    return None


def peso_ocr(card):
    arq = os.path.join(SCRATCH, "peso_tmp.jpg")
    card.save(arq)
    txt = subprocess.run(["tesseract", arq, "stdout", "-l", "por+eng",
                          "--psm", "6"], capture_output=True, text=True).stdout
    m = re.search(r"(\d+[.,]\d+)\s*[Kk][Gg9]/[Mm]", txt)
    return m.group(1) + " kg/m" if m else None


def gerar(geo, codigo, paineis):
    cards, headers = [], []
    for pdf, pag, rotulo, prefixo, metodo in paineis:
        img, caminho = render(pdf, pag)
        if metodo == "ocr":
            cx, cy = rotulo_ocr(pdf, pag, rotulo, caminho)
            card = recortar_card(img, cx, cy)
            peso = peso_ocr(card)
        elif metodo == "nativo":
            cx, cy = rotulo_nativo(pdf, pag, rotulo)
            card = recortar_card(img, cx, cy)
            peso = peso_nativo(pdf, pag, rotulo) or peso_ocr(card)
        else:  # fixo (px @100dpi -> @DPI)
            x0, y0, x1, y1 = (int(v) * DPI // 100
                              for v in metodo.split(":")[1].split(","))
            card = img.crop((x0, y0, x1, y1))
            peso = peso_nativo(pdf, pag, rotulo)
        h = f"{prefixo}, pág. {pag} — {codigo}"
        if peso:
            h += f" — {peso}"
        cards.append(card)
        headers.append(h)

    alt_alvo = 1000
    cards = [c.resize((int(c.width * alt_alvo / c.height), alt_alvo),
                      Image.LANCZOS) for c in cards]
    larg_total = sum(c.width for c in cards)
    fig_w, fig_h = larg_total / 100, (alt_alvo + 90) / 100
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    x_off = 0
    for card, header in zip(cards, headers):
        fr = card.width / larg_total
        ax = fig.add_axes([x_off, 0, fr, alt_alvo / (alt_alvo + 90)])
        ax.imshow(card)
        ax.axis("off")
        fig.text(x_off + 0.005, 1 - 0.4 * 90 / (alt_alvo + 90), header,
                 fontsize=15, fontweight="bold", va="center", ha="left")
        x_off += fr
    saida = f"{BASE}/curadoria/comparacao/{codigo}_lado_a_lado.png"
    fig.savefig(saida, facecolor="white")
    plt.close(fig)
    print(f"{geo}: {saida}")
    for h in headers:
        print(f"   {h}")


if __name__ == "__main__":
    alvos = sys.argv[1:] or list(AMOSTRA)
    for geo in alvos:
        codigo, paineis = AMOSTRA[geo]
        try:
            gerar(geo, codigo, paineis)
        except Exception as e:
            print(f"{geo}: FALHOU — {e}")
