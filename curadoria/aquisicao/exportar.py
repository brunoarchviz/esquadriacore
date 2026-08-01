"""
Camada de SAÍDA da curadoria. Só serializa resultado já aprovado.

Não limpa contorno, não recalibra dimensão, não altera topologia, não escolhe
componente, não corrige contaminação, não deriva assinatura e não aplica regra
de domínio. A procedência tem de estar fechada antes de chegar aqui.

Existe porque o writer de SVG e a gravação dos artefatos viviam num runner
temporário no scratchpad: quando o scratchpad era limpo entre rodadas, a
gravação deixava de ser reproduzível. Agora são módulo permanente.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

ARTEFATOS = ("contorno_bruto.json", "contorno_comercial.json",
             "assinatura_topologica.json", "metricas.json",
             "operacoes_limpeza.json", "contorno_comercial.svg")

OFICIAIS_PROIBIDOS = ("dados", "domain", "contrato", "docs")


def _anel(pts, altura_mm, escala):
    return " ".join(f"{x*escala:.3f},{(altura_mm-y)*escala:.3f}" for x, y in pts)


def exportar_contorno_svg(contorno_externo, vazios_internos, caminho_saida, *,
                          largura_mm, altura_mm, escala=10.0, margem_mm=0.0,
                          metadados=None) -> Path:
    """SVG determinístico do contorno JÁ calculado. Não altera ponto algum."""
    m = margem_mm * escala
    w = largura_mm * escala + 2 * m
    h = altura_mm * escala + 2 * m
    d = f"M {_anel(contorno_externo, altura_mm, escala)} Z"
    for v in vazios_internos:
        d += f" M {_anel(v, altura_mm, escala)} Z"
    meta = ""
    if metadados:
        itens = "".join(f"\n    <{k}>{v}</{k}>" for k, v in
                        sorted(metadados.items()))
        meta = f"\n  <metadata>{itens}\n  </metadata>"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" '
           f'height="{h:.1f}" viewBox="{-m:.1f} {-m:.1f} {w:.1f} {h:.1f}">'
           f'{meta}\n  <path d="{d}" fill="#333" fill-rule="evenodd"/>\n</svg>\n')
    caminho = Path(caminho_saida)
    caminho.write_text(svg)
    return caminho


def gravar_artefatos_curadoria(perfil: str, resultado: dict,
                               diretorio_saida) -> dict:
    """Serializa o conjunto de artefatos de forma TRANSACIONAL.

    Escreve num diretório temporário e só move para o destino quando todos os
    arquivos existirem — falha parcial não deixa metade novo e metade antigo.
    """
    destino = Path(diretorio_saida)
    for proibido in OFICIAIS_PROIBIDOS:
        if proibido in destino.resolve().parts:
            raise ValueError(
                f"gravação em caminho oficial proibida: {destino} "
                f"(componente {proibido!r})")
    obrigatorios = ("contorno_bruto", "contorno_comercial", "assinatura",
                    "metricas", "operacoes", "dimensoes_mm")
    faltando = [k for k in obrigatorios if k not in resultado]
    if faltando:
        raise KeyError(f"resultado incompleto para gravar: {faltando}")

    L = resultado["dimensoes_mm"]["largura"]
    A = resultado["dimensoes_mm"]["altura"]
    tmp = Path(tempfile.mkdtemp(prefix=f"{perfil}_", dir=destino.parent))
    try:
        (tmp / "contorno_bruto.json").write_text(json.dumps(
            resultado["contorno_bruto"], ensure_ascii=False, indent=1))
        (tmp / "contorno_comercial.json").write_text(json.dumps(
            resultado["contorno_comercial"], ensure_ascii=False, indent=1))
        (tmp / "assinatura_topologica.json").write_text(json.dumps(
            resultado["assinatura"], ensure_ascii=False, indent=1))
        (tmp / "metricas.json").write_text(json.dumps(
            resultado["metricas"], ensure_ascii=False, indent=1))
        (tmp / "operacoes_limpeza.json").write_text(json.dumps(
            resultado["operacoes"], ensure_ascii=False, indent=1))
        exportar_contorno_svg(
            resultado["contorno_comercial"]["contorno_externo"],
            resultado["contorno_comercial"]["vazios_internos"],
            tmp / "contorno_comercial.svg", largura_mm=L, altura_mm=A,
            metadados={"perfil": perfil})
        gerados = sorted(p.name for p in tmp.iterdir())
        if set(ARTEFATOS) - set(gerados):
            raise RuntimeError(f"conjunto incompleto: falta "
                               f"{sorted(set(ARTEFATOS) - set(gerados))}")
        destino.mkdir(parents=True, exist_ok=True)
        for nome in ARTEFATOS:
            shutil.move(str(tmp / nome), str(destino / nome))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"perfil": perfil, "destino": str(destino),
            "artefatos": list(ARTEFATOS)}
