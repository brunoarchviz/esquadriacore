"""
EsquadriaCore — curadoria/comparar_gold_geracoes
=================================================
Compara pesos dos códigos LG- entre Gold 3 (alcoa_gold3.pdf) e Gold 4
(CATALOGO_IVGOLD.pdf) para priorizar a curadoria visual da família Gold.

Heurística de peso: âncora no token "kg/m" (número imediatamente à esquerda,
mesma linha), associada ao código LG mais próximo — a heurística padrão do
PdfTextoProvider (decimal abaixo do código) captura cotas dimensionais nesses
layouts. Descartada âncora a mais de 200pt de qualquer código.

ATENÇÃO (regra de curadoria da Gold, docs/plano_de_curadoria.md): código igual
entre gerações da MESMA marca é hipótese fraca — confirmação visual é
obrigatória em TODOS os casos, não só nos de peso divergente.

Uso:  python3 curadoria/comparar_gold_geracoes.py
"""
import re
import sys

sys.path.insert(0, ".")
from providers.pdf_texto import PdfTextoProvider

PADRAO_LG = re.compile(r"^LG-?\d{2,4}$")
PADRAO_NUM = re.compile(r"^\d+[,\.]\d+$")
TOLERANCIA = 6.0  # %, mesma da Suprema


def extrair_com_ancora(pdf, paginas, fabricante):
    prov = PdfTextoProvider(pdf, 1, paginas, fabricante=fabricante)
    pesos = {}
    for pagina in range(1, paginas + 1):
        palavras = prov._palavras_da_pagina(pagina)
        codigos = [p for p in palavras if PADRAO_LG.match(p.texto)]
        if not codigos:
            continue
        for w in palavras:
            m = re.match(r"^(\d+[,\.]\d+)?\s*[Kk][Gg]/[Mm][Tt]?$", w.texto)
            if not m:
                continue
            if m.group(1):
                peso = float(m.group(1).replace(",", "."))
            else:
                cand = [q for q in palavras if PADRAO_NUM.match(q.texto)
                        and abs(q.ymin - w.ymin) < 5 and q.xmax <= w.xmin + 2
                        and w.xmin - q.xmax < 30]
                if not cand:
                    continue
                cand.sort(key=lambda q: w.xmin - q.xmax)
                peso = float(cand[0].texto.replace(",", "."))
            cod = min(codigos, key=lambda c: ((c.xmin - w.xmin) ** 2 +
                                              (c.ymin - w.ymin) ** 2))
            dist = ((cod.xmin - w.xmin) ** 2 + (cod.ymin - w.ymin) ** 2) ** 0.5
            if dist > 200:
                continue
            chave = cod.texto if "-" in cod.texto else \
                cod.texto[:2] + "-" + cod.texto[2:]
            if chave not in pesos or dist < pesos[chave][1]:
                pesos[chave] = (peso, dist)
    return {k: v[0] for k, v in pesos.items()}


def main():
    g3 = extrair_com_ancora("dados_exemplo/alcoa_gold3.pdf", 168, "AlcoaGold3")
    g4 = extrair_com_ancora("dados_exemplo/CATALOGO_IVGOLD.pdf", 232, "IVGold")
    comuns = sorted(set(g3) | set(g4))
    resultados = []
    for c in comuns:
        pa, pb = g3.get(c), g4.get(c)
        delta = abs(pa - pb) / max(pa, pb) * 100 if pa and pb else None
        resultados.append((delta, c, pa, pb))
    print(f"{'Código':<9}{'G3 (kg/m)':<11}{'G4 (kg/m)':<11}{'Δ%':<7}{'Sinal'}")
    print("-" * 50)
    for delta, c, pa, pb in sorted(resultados,
                                   key=lambda x: (x[0] is None, x[0])):
        if delta is None:
            sinal = "sem par"
            d = "—"
        else:
            sinal = "✓ bate" if delta < TOLERANCIA else "⚠ olhar desenho"
            d = f"{delta:.1f}"
        print(f"{c:<9}{str(pa):<11}{str(pb):<11}{d:<7}{sinal}")


if __name__ == "__main__":
    main()
