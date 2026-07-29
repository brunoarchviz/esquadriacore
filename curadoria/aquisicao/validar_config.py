"""Validação de schema do config canônico do E.4B.

Específico deste config — não é framework genérico. Existe porque renomear
chave já quebrou testes três vezes nesta sprint: `fonte_dimensional` virou
`fonte_dimensional_primaria`, `zona_protegida_tms053` migrou para dentro de
`tms053`, e `estado` foi dividido em `estado_geometrico` + `estado_dimensional`.
Nas três o erro só apareceu quando um teste distante tentou ler a chave antiga.

Aqui a incoerência é apontada de uma vez, dizendo perfil, chave e motivo.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "curadoria/aquisicao/configs/e4b_suprema.json"

GRUPOS = ("perfis", "p4_reconhecimento")

# Todo perfil precisa localizar a própria fonte.
OBRIGATORIAS = ("fonte_pdf", "pagina_pdf", "roi_norm")

# Chaves que existiram e foram substituídas. Manter aqui é o que impede um
# perfil novo de nascer com o nome velho.
DEPRECIADAS = {
    "fonte_dimensional": "fonte_dimensional_primaria",
    "zona_protegida_tms053": "motivos[].tms053.roi_efetiva_recortada_ao_envelope",
    "validacao_local_tms053": "motivos[].tms053.validacao_local",
}


def _erro(perfil, chave, motivo):
    return f"{perfil}: {chave} — {motivo}"


def _valida_estados(cod, p) -> list[str]:
    """`estado` e o par dividido não podem coexistir."""
    e = []
    tem_par = "estado_geometrico" in p or "estado_dimensional" in p
    if tem_par and "estado" in p:
        e.append(_erro(cod, "estado",
                       "chave antiga convive com estado_geometrico/"
                       "estado_dimensional — remover a antiga"))
    if "estado_dimensional" in p:
        if "estado_geometrico" not in p:
            e.append(_erro(cod, "estado_geometrico",
                           "ausente, mas estado_dimensional existe"))
        if not isinstance(p["estado_dimensional"], dict) or \
                "status" not in p["estado_dimensional"]:
            e.append(_erro(cod, "estado_dimensional.status", "ausente"))
    return e


def _valida_dimensoes(cod, p) -> list[str]:
    """Estado e dimensão têm de contar a mesma história."""
    e = []
    tem_cota = p.get("largura_mm") is not None and p.get("altura_mm") is not None
    dim = (p.get("estado_dimensional") or {}).get("status", "")
    if dim.startswith("AGUARDANDO_") and tem_cota:
        e.append(_erro(cod, "largura_mm/altura_mm",
                       f"preenchidas, mas estado_dimensional é {dim!r}"))
    if not dim and not tem_cota and p.get("estado", "").startswith("CANDIDATO_GEOMETRICO_APROVADO"):
        e.append(_erro(cod, "largura_mm/altura_mm",
                       "ausentes num candidato aprovado"))
    # cota interna nunca pode ser o envelope
    for c in p.get("cotas_internas", []):
        if c.get("usar_como_envelope") is not False:
            e.append(_erro(cod, f"cotas_internas[{c.get('valor_mm')}]",
                           "usar_como_envelope tem de ser explicitamente false"))
        if c.get("valor_mm") in (p.get("largura_mm"), p.get("altura_mm")):
            e.append(_erro(cod, f"cotas_internas[{c.get('valor_mm')}]",
                           "coincide com a dimensão externa — cota interna "
                           "virou envelope"))
    return e


def _valida_fontes(cod, p) -> list[str]:
    """Fonte geométrica e dimensional precisam existir por inteiro."""
    e = []
    g = p.get("fonte_geometrica_primaria")
    if g is not None:
        for k in ("pagina_pdf", "roi_norm"):
            if k not in g:
                e.append(_erro(cod, f"fonte_geometrica_primaria.{k}", "ausente"))
    d = p.get("fonte_dimensional_primaria") or p.get("fonte_dimensional")
    if d is not None and d.get("tipo") == "evidencia_composta":
        for eixo in ("largura", "altura"):
            if eixo not in d:
                e.append(_erro(cod, f"fonte_dimensional.{eixo}", "ausente"))
            elif "origem" not in d[eixo]:
                e.append(_erro(cod, f"fonte_dimensional.{eixo}.origem", "ausente"))
    return e


def _valida_motivos(cod, p) -> list[str]:
    """Lista vazia exige declaração; zona exige arbitragem."""
    e = []
    motivos = p.get("motivos", [])
    pend = p.get("_motivos_pendentes")
    if motivos and pend:
        e.append(_erro(cod, "_motivos_pendentes",
                       "convive com motivos confirmados"))
    if not motivos:
        if not pend:
            e.append(_erro(cod, "motivos",
                           "lista vazia sem _motivos_pendentes"))
        elif pend.get("levantamento") != "nao_realizado" or \
                not pend.get("justificativa"):
            e.append(_erro(cod, "_motivos_pendentes",
                           "declaração incompleta"))
    for m in motivos:
        if m.get("zona_protegida") is None:
            continue
        # Três idiomas de procedência convivem: `roi_status` é o selo novo
        # (SU-053); `atribuicao_geometrica` em 'medida' ou 'zona_curada' é o
        # legado dos perfis homologados antes dele. Os dois valem — o que não
        # vale é zona existir com atribuição declarada PENDENTE.
        selo = str(m.get("roi_status", "")).lower() == "confirmado_bruno"
        legado = m.get("atribuicao_geometrica") in ("medida", "zona_curada")
        if not (selo or legado):
            e.append(_erro(cod, f"motivos[{m.get('id')}]",
                           f"tem zona_protegida com procedência "
                           f"{m.get('atribuicao_geometrica')!r} — nem selo novo "
                           f"nem idioma legado"))
    return e


def validar(cfg=None) -> list[str]:
    """Devolve a lista de incoerências. Vazia = config íntegro."""
    cfg = cfg or json.loads(CONFIG.read_text())
    erros = []
    for grupo in GRUPOS:
        for cod, p in cfg.get(grupo, {}).items():
            if cod.startswith("_"):
                continue
            for k in OBRIGATORIAS:
                if k not in p:
                    erros.append(_erro(cod, k, "chave obrigatória ausente"))
            for velha, nova in DEPRECIADAS.items():
                if velha in p:
                    erros.append(_erro(cod, velha,
                                       f"chave depreciada — usar {nova}"))
            erros += _valida_estados(cod, p)
            erros += _valida_dimensoes(cod, p)
            erros += _valida_fontes(cod, p)
            erros += _valida_motivos(cod, p)
    return erros


if __name__ == "__main__":
    e = validar()
    print("\n".join(e) if e else "config íntegro")
