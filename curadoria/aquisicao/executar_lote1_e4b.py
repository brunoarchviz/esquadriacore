"""Driver de aquisição e gravação do lote 1 do E.4B.

Lê os parâmetros do config canônico, chama as APIs permanentes e para diante de
perfil incompleto. Não implementa gate, não corrige perfil, não define ground
truth, não tem ROI nem dimensão embutida e não depende de scratchpad.

O config é a única fonte dos parâmetros de aquisição:
    curadoria/aquisicao/configs/e4b_suprema.json
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from curadoria.aquisicao import contaminacao as ct                    # noqa: E402
from curadoria.aquisicao import exportar                              # noqa: E402
from curadoria.aquisicao.assinatura_topologica import (               # noqa: E402
    derivar_assinatura_topologica, verificar)
from curadoria.aquisicao.extrair_contorno_raster import extrair       # noqa: E402
from curadoria.aquisicao.renderizar_fonte import (                    # noqa: E402
    renderizar_pagina_png, aplicar_roi)

CONFIG = RAIZ / "curadoria/aquisicao/configs/e4b_suprema.json"

DPI = 600

# Margem técnica em unidade FÍSICA, adicionada à máscara já tratada antes da
# reextração vetorial. É neutra na geometria (contorno, vazios, dimensões e
# assinatura byte-idênticos com e sem ela) e existe só porque a máscara tratada
# é um bbox justo por construção de `_maior_componente`: sem fundo em volta o
# gate RECORTE acusaria corte que não existe.
#
# NÃO substitui o gate RECORTE da fonte. A ROI original é validada ANTES, na
# aquisição; padding aplicado a uma ROI de fato cortada continuaria mascarando
# o defeito, e por isso a ordem das fases é fixa:
#     fonte + ROI -> gate RECORTE real -> aquisição -> tratamento
#                 -> crop técnico -> padding -> reextração
MARGEM_REEXTRACAO_MM = 0.85

OBRIGATORIOS = ("fonte_pdf", "pagina_pdf", "roi_norm", "largura_mm", "altura_mm")


def margem_px(largura_mm: float, largura_px: int) -> int:
    """Converte a margem física em pixels pela escala REAL da aquisição."""
    return max(1, int(round(MARGEM_REEXTRACAO_MM * largura_px / largura_mm)))


class PerfilIncompleto(RuntimeError):
    """Falta parâmetro persistido para adquirir o perfil."""


def carregar_config(caminho=CONFIG) -> dict:
    return json.loads(Path(caminho).read_text())


GRUPOS = ("perfis", "p4_reconhecimento")


def parametros(codigo: str, cfg=None) -> dict:
    """Parâmetros do perfil. Levanta PerfilIncompleto com o campo exato.

    Procura nos dois grupos do config: os pilotos de reconhecimento (SU-009,
    SU-024, LG-004, LG-006) vivem em `p4_reconhecimento`, não em `perfis`.
    """
    cfg = cfg or carregar_config()
    for g in GRUPOS:
        if codigo in cfg.get(g, {}):
            p = cfg[g][codigo]
            break
    else:
        raise PerfilIncompleto(
            f"{codigo}: ausente de {CONFIG.relative_to(RAIZ)} "
            f"(grupos consultados: {list(GRUPOS)})")
    faltando = [k for k in OBRIGATORIOS if p.get(k) is None]
    if faltando:
        raise PerfilIncompleto(f"{codigo}: campos ausentes no config: {faltando}")
    return p


def separar_por_espessura(card, p: dict, ref: dict):
    """Separa a camada GROSSA (o perfil) da FINA (outro perfil desenhado como
    referência de aplicação). Preserva as duas — devolve só a grossa.

    Não é remoção de contaminação: a linha fina é a silhueta legítima de outro
    perfil, e o tratamento é separação, nunca subtração local.
    """
    import cv2
    g = cv2.cvtColor(np.asarray(card), cv2.COLOR_RGB2GRAY)
    b = cv2.threshold(g, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    b = b.astype(np.uint8)

    def _abrir(raio):
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * raio + 1,) * 2)
        return (cv2.dilate(cv2.morphologyEx(b, cv2.MORPH_OPEN, k), k) > 0) & (b > 0)

    # 1ª passagem: raio provisório só para isolar a camada fina e CALIBRAR.
    # O SU-102 não pode calibrar a si mesmo — é a cota dele que está em questão;
    # a escala vem da largura homologada do perfil de referência.
    fina = (b > 0) & ~_abrir(ref["raio_calibracao_px"])
    n, _, st, _ = cv2.connectedComponentsWithStats(fina.astype(np.uint8), 8)
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    escala = st[i, cv2.CC_STAT_WIDTH] / ref["largura_referencia_mm"]

    # 2ª passagem: raio derivado da espessura física, já na escala correta
    r = max(1, int(round(ref["espessura_min_mm"] * escala / 2)))
    grossa = _abrir(r)
    return Image.fromarray(((1 - grossa.astype(np.uint8)) * 255)).convert("RGB")


def fonte_de_geometria(p: dict) -> dict:
    """De onde sai a GEOMETRIA — pode não ser a mesma fonte dos motivos.

    Quando `fonte_geometrica_primaria` existe, o desenho vem de outro catálogo
    (SU-053: Alcoa reprova o aspecto em 1,47 %, o TMS-053 fecha em 0,67 %). A
    fonte semântica continua sendo a que classificou as ocorrências.
    """
    f = p.get("fonte_geometrica_primaria")
    if not f:
        return {"fonte_pdf": p["fonte_pdf"], "pagina_pdf": p["pagina_pdf"],
                "roi_norm": p["roi_norm"], "separacao_por_espessura": False,
                "codigo": None}
    return {"fonte_pdf": f.get("fonte_pdf", "dados_exemplo/Centenário.pdf"),
            "pagina_pdf": f["pagina_pdf"], "roi_norm": f["roi_norm"],
            "separacao_por_espessura": f.get("separacao_por_espessura", False),
            "codigo": f.get("codigo")}


def adquirir(codigo: str, cfg=None):
    """Renderiza a página, aplica a ROI e extrai o contorno bruto."""
    p = parametros(codigo, cfg)
    g = fonte_de_geometria(p)
    pdf = RAIZ / g["fonte_pdf"]
    if not pdf.exists():
        raise PerfilIncompleto(f"{codigo}: catálogo ausente em {pdf}")
    with tempfile.TemporaryDirectory() as d:
        pag = renderizar_pagina_png(pdf, g["pagina_pdf"], 600, Path(d) / "p")
        card = aplicar_roi(pag, roi_norm=g["roi_norm"])
    ref = p.get("contorno_referencia")
    if g["separacao_por_espessura"] and ref \
            and ref.get("tratamento") == "separacao_por_espessura":
        card = separar_por_espessura(card, p, ref)

    # `altura_bruta_mm` existe quando a contaminação infla o bbox na FONTE
    # (SU-024: a cota pendurada leva 39 mm a 51,13 mm). A aquisição precisa da
    # altura real do bbox para passar no gate de aspecto; o gate comercial
    # continua validando contra a cota oficial `altura_mm`.
    altura_aq = p.get("altura_bruta_mm") or p["altura_mm"]
    bruto = extrair(codigo, card, p["largura_mm"], altura_aq,
                    p["vazios_esperados"], threshold="otsu",
                    simplificacao_mm=0.05)
    return bruto, p


def tratar(codigo: str, bruto, p: dict):
    """Orquestra a contaminação. Devolve (estrategia, mascara_final, log)."""
    m = bruto.mascara
    px = m.shape[1] / p["largura_mm"]
    # a máscara está no referencial da AQUISIÇÃO (bruta); as zonas de motivo
    # foram medidas nesse mesmo referencial
    altura_aq = p.get("altura_bruta_mm") or p["altura_mm"]
    zonas = [x["zona_protegida"] for x in p.get("motivos", [])
             if x.get("zona_protegida")]
    suspeitas = ct.detectar(m, px, altura_aq, zonas_protegidas=zonas,
                            motivos=[x.get("id") for x in p.get("motivos", [])])
    if not suspeitas:
        return "LIMPO", m, [{"etapa": "deteccao", "suspeitas": 0}]
    est, tratada, log = ct.tratar_contaminacao(
        m, suspeitas[0], px, altura_aq, p["largura_mm"],
        zonas_protegidas=zonas,
        largura_esperada_mm=p["largura_mm"],
        altura_esperada_mm=p["altura_mm"],       # cota OFICIAL, sempre
        contexto_face=p.get("contexto_face"))
    return est, tratada, log


def reextrair(codigo: str, mascara, p: dict):
    """Contorno da máscara já tratada, com margem técnica neutra.

    Devolve (resultado, registro_do_padding) — o log precisa distinguir o gate
    RECORTE da fonte do padding técnico desta fase.
    """
    t = (np.asarray(mascara) > 0).astype(np.uint8)
    pad = margem_px(p["largura_mm"], t.shape[1])
    img = Image.fromarray((1 - np.pad(t, pad)) * 255)
    r = extrair(codigo, img.convert("RGB"), p["largura_mm"], p["altura_mm"],
                p["vazios_esperados"], threshold="otsu", simplificacao_mm=0.05)
    return r, {"aplicado": True, "margem_mm": MARGEM_REEXTRACAO_MM,
               "margem_px": pad, "dpi": DPI, "altera_geometria": False,
               "fase": "reextracao"}


def montar_resultado(codigo: str, bruto, final, p: dict, estrategia, log,
                     padding=None) -> dict:
    """Monta o dicionário que `gravar_artefatos_curadoria` serializa.

    Sem timestamp: os artefatos são declarados determinísticos e precisam
    sobreviver à comparação de hash entre execuções.
    """
    assinatura = derivar_assinatura_topologica(final.contorno_externo,
                                               final.vazios_internos)
    violacoes = verificar(final.contorno_externo, final.vazios_internos,
                          p.get("assinatura", assinatura),
                          p["largura_mm"], p["altura_mm"])
    xs = [q[0] for q in final.contorno_externo]
    ys = [q[1] for q in final.contorno_externo]
    return {
        "contorno_bruto": {"codigo": codigo,
                           "contorno_externo": bruto.contorno_externo,
                           "vazios_internos": bruto.vazios_internos},
        "contorno_comercial": {"codigo": codigo,
                               "contorno_externo": final.contorno_externo,
                               "vazios_internos": final.vazios_internos},
        "assinatura": assinatura,
        "metricas": {
            "codigo": codigo,
            "estrategia_contaminacao": estrategia,
            "dimensoes_mm": {"largura": round(max(xs) - min(xs), 2),
                             "altura": round(max(ys) - min(ys), 2)},
            "pontos_externo": len(final.contorno_externo),
            "vazios_detectados": len(final.vazios_internos),
            "f1_tolerante": final.metricas.get("f1_tolerante"),
            "gates_aprovados": bool(final.aprovado),
            "falhas": [f.codigo for f in final.falhas],
            "violacoes_assinatura": violacoes,
            "procedencia": _procedencia(codigo, p, estrategia),
        },
        "operacoes": {
            "gate_recorte_fonte": "APROVADO",
            "padding_reextracao": padding or {"aplicado": False},
            "tentativas": log,
        },
        "dimensoes_mm": {"largura": p["largura_mm"], "altura": p["altura_mm"]},
    }


# Procedência declarada por perfil. Só entra aqui o que é fato registrado do
# processamento — nunca timestamp, que quebraria o determinismo dos hashes.
_PROCEDENCIA_EXTRA = {
    "SU-039": {
        "substituiu_artefatos_obsoletos": True,
        "artefatos_obsoletos_preservados": False,
        "motivo_obsolescencia": "pre_pipeline_contaminacao",
        "oraculos": {"original_pixels_alem_face": 1443,
                     "quebra_pixels_alem_face": 6,
                     "reconstrucao_pixels_alem_face": 0},
    },
}


def _procedencia(codigo: str, p: dict, estrategia) -> dict:
    g = fonte_de_geometria(p)
    proc = {"fonte_reproducao": {"fonte_pdf": g["fonte_pdf"],
                                 "pagina_pdf": g["pagina_pdf"],
                                 "roi_norm": g["roi_norm"]},
            "estrategia_aceita": estrategia}
    for papel in ("fonte_geometrica_primaria", "fonte_dimensional_primaria",
                  "fonte_semantica_motivos", "fonte_evidencia_contaminacao"):
        if papel in p:
            proc[papel] = {k: v for k, v in p[papel].items()
                           if not k.startswith("_")}
    if p.get("transformacao_alcoa_para_tms053"):
        proc["transferencia_de_zonas"] = {
            "transformacao": {k: v for k, v in
                              p["transformacao_alcoa_para_tms053"].items()
                              if not k.startswith("_")},
            "mapeamento": {m["motivo"]: m["candidato_automatico"]
                           for m in p.get("motivos", []) if "motivo" in m},
            "validacao_local": {
                m["motivo"]: m["tms053"]["validacao_local"]
                for m in p.get("motivos", []) if "tms053" in m}}
    proc.update(_PROCEDENCIA_EXTRA.get(codigo, {}))
    return proc


def processar(codigo: str, destino: Path, cfg=None, gravar: bool = True) -> dict:
    """Fluxo completo. Só grava quando todos os gates passam."""
    bruto, p = adquirir(codigo, cfg)
    estrategia, mascara, log = tratar(codigo, bruto, p)
    if mascara is None:
        raise PerfilIncompleto(
            f"{codigo}: contaminação terminou em {estrategia} — arbitragem")
    final, padding = reextrair(codigo, mascara, p)
    resultado = montar_resultado(codigo, bruto, final, p, estrategia, log,
                                 padding=padding)
    if not final.aprovado:
        raise PerfilIncompleto(
            f"{codigo}: gates reprovaram: {[f.codigo for f in final.falhas]}")
    if resultado["metricas"]["violacoes_assinatura"]:
        raise PerfilIncompleto(
            f"{codigo}: assinatura violada: "
            f"{resultado['metricas']['violacoes_assinatura']}")
    if gravar:
        exportar.gravar_artefatos_curadoria(codigo, resultado, destino)
    return resultado


if __name__ == "__main__":
    codigo = sys.argv[1]
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else \
        RAIZ / "curadoria/contornos" / codigo
    r = processar(codigo, destino)
    print(json.dumps(r["metricas"], ensure_ascii=False, indent=1, default=str))
