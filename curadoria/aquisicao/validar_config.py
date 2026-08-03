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

# Selos que atestam procedência HUMANA de uma zona. Fonte única — os testes
# importam daqui em vez de repetir a lista, que foi o que fez o mesmo remendo
# aparecer quatro vezes nesta sprint.
#
#   roi_status: o selo explícito. `confirmado_bruno` nasceu no SU-053,
#              `confirmado` na arbitragem do SU-041.
#   atribuicao_geometrica: idiomas legados dos perfis homologados antes deles.
ROI_STATUS_HUMANO = ("confirmado_bruno", "confirmado")
ATRIBUICAO_HUMANA = ("medida", "zona_curada", "confirmada_por_arbitragem_visual")
ATRIBUICAO_PENDENTE = ("pendente", "pendente_arbitragem")


def zona_tem_procedencia_humana(m: dict) -> bool:
    """Uma zona só é legítima com procedência humana declarada."""
    return (str(m.get("roi_status", "")).lower() in ROI_STATUS_HUMANO
            or m.get("atribuicao_geometrica") in ATRIBUICAO_HUMANA)


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
        if not zona_tem_procedencia_humana(m):
            e.append(_erro(cod, f"motivos[{m.get('id')}]",
                           f"tem zona_protegida com procedência "
                           f"{m.get('atribuicao_geometrica')!r} — nem selo novo "
                           f"nem idioma legado"))
    return e


def _valida_su041(cfg) -> list[str]:
    """Travas específicas da arbitragem do SU-041 (2026-07-28).

    Existem porque as três decisões são fáceis de desfazer por engano: o C6 é
    visualmente parecido com escovinha (foi confundido antes), o C1 encosta na
    zona do M2, e a zona do M2 não corresponde a bolso nenhum — o que convida a
    "consertar" substituindo por um candidato.
    """
    e = []
    su = cfg.get("perfis", {}).get("SU-041")
    if su is None:
        return e
    arb = su.get("arbitragem_zonas")
    if not arb:
        return [_erro("SU-041", "arbitragem_zonas", "ausente")]

    por_id = {m["id"]: m for m in su.get("motivos", [])}
    esc = por_id.get("GAB-ESCOVINHA-SU-01")
    diag = por_id.get("GAB-MA-DIAG-ESC-01")

    if esc is None or diag is None:
        return [_erro("SU-041", "motivos", "os dois motivos confirmados têm de existir")]

    if esc.get("candidato") != "C5":
        e.append(_erro("SU-041", "GAB-ESCOVINHA-SU-01.candidato",
                       f"deve ser C5, está {esc.get('candidato')!r}"))
    if esc.get("candidato") == "C6":
        e.append(_erro("SU-041", "GAB-ESCOVINHA-SU-01",
                       "C6 é olhal (formato C com serrilhas internas) e não pode "
                       "ser atribuído à escovinha"))
    if diag.get("metodo_delimitacao") != "zona_manual":
        e.append(_erro("SU-041", "GAB-MA-DIAG-ESC-01.metodo_delimitacao",
                       "a zona do M2 é manual — região estrutural, não bolso"))
    if diag.get("candidato") is not None:
        e.append(_erro("SU-041", "GAB-MA-DIAG-ESC-01.candidato",
                       f"deve ser null; C1 não delimita o M2 "
                       f"(está {diag.get('candidato')!r})"))
    for m in (esc, diag):
        if m.get("atribuicao_geometrica") in ATRIBUICAO_PENDENTE:
            e.append(_erro("SU-041", f"motivos[{m['id']}]",
                           "atribuição voltou a pendente após a arbitragem"))
        if m.get("zona_protegida") is None:
            e.append(_erro("SU-041", f"motivos[{m['id']}]",
                           "zona sumiu após a arbitragem"))
    c1 = arb.get("candidatos_descartados", {}).get("C1", {})
    if c1.get("usar_como_delimitacao_m2") is not False:
        e.append(_erro("SU-041", "arbitragem_zonas.C1",
                       "usar_como_delimitacao_m2 tem de ser explicitamente false"))
    return e


def _erro_ml(chave, motivo):
    return f"microlote_janela: {chave} — {motivo}"


def _valida_microlote_janela(cfg) -> list[str]:
    """Travas de coerência do fechamento do microlote (2026-08-01).

    Existem porque a auditoria do PR #3 encontrou o config afirmando 8 fechados
    e, ao mesmo tempo, carregando `pendencia_restante` do SU-102 e uma nota
    dizendo "7 de 8". Contagem, lista e pendência precisam contar a mesma
    história — e fechar o SU-102 não fecha a equivalência com o TMS-102.
    """
    e = []
    ml = cfg.get("microlote_janela")
    if not ml:
        return [_erro_ml("microlote_janela", "bloco ausente")]

    fechados = ml.get("perfis_fechados") or []
    total = ml.get("fechados_na_curadoria")

    # 1. contagem bate com a lista
    if total != len(fechados):
        e.append(_erro_ml("fechados_na_curadoria",
                          f"{total} não corresponde a len(perfis_fechados)="
                          f"{len(fechados)}"))
    # 2. sem duplicatas
    if len(fechados) != len(set(fechados)):
        dup = sorted({p for p in fechados if fechados.count(p) > 1})
        e.append(_erro_ml("perfis_fechados", f"duplicatas: {dup}"))
    # 3. com 8, todos os perfis do microlote têm de aparecer
    if total == 8:
        faltam = [p for p in (ml.get("perfis") or []) if p not in fechados]
        if faltam:
            e.append(_erro_ml("perfis_fechados",
                              f"total é 8 mas faltam da lista: {faltam}"))
    # 4. nada aguardando ⇒ nenhuma pendência restante
    pend = ml.get("pendencia_restante")
    if ml.get("aguardando_evidencia_externa") == 0 and pend:
        e.append(_erro_ml("pendencia_restante",
                          "aguardando_evidencia_externa é 0, mas há pendência "
                          f"registrada: {pend}"))
    # 5. um perfil não pode estar fechado e pendente ao mesmo tempo
    if isinstance(pend, dict) and pend.get("perfil") in fechados:
        e.append(_erro_ml("pendencia_restante.perfil",
                          f"{pend['perfil']} está em perfis_fechados e como "
                          "pendência simultaneamente"))
    # 6. notas não podem contradizer a contagem
    notas = " ".join(str(v) for k, v in ml.items() if k.startswith("_"))
    if "SU-102" in fechados:
        for frase in ("7 de 8", "escala_dimensional"):
            if frase in notas:
                e.append(_erro_ml("_nota_contagem",
                                  f"SU-102 está fechado mas a nota ainda diz "
                                  f"{frase!r}"))
    # 7. promoção declarada exige evidência; fechar a curadoria não promove nada
    promovido = ml.get("promocao_oficial_realizada")
    if promovido not in (True, False):
        e.append(_erro_ml("promocao_oficial_realizada",
                          f"tem de ser booleano explícito, está {promovido!r}"))
    elif promovido is True:
        # Marcar promovido sem que cada perfil aponte para o próprio GEO seria
        # afirmar um estado que dados/ não sustenta.
        sem = [c for c in fechados
               if (cfg.get("perfis", {}).get(c, {})
                   .get("promocao_oficial", {}).get("status") != "PROMOVIDO")]
        if sem:
            e.append(_erro_ml("promocao_oficial_realizada",
                              f"declarada true, mas sem promocao_oficial."
                              f"status=PROMOVIDO em: {sem}"))
        for c in fechados:
            po = cfg.get("perfis", {}).get(c, {}).get("promocao_oficial", {})
            if po.get("id_geometria") != f"GEO-{c}":
                e.append(_erro_ml(f"perfis.{c}.promocao_oficial.id_geometria",
                                  f"esperado GEO-{c}, está {po.get('id_geometria')!r}"))
    # 8. equivalência dimensional SU-102 × TMS-102
    e += _valida_equivalencia_su102_tms102(cfg)
    return e


def _valida_equivalencia_su102_tms102(cfg) -> list[str]:
    """A dimensão do TMS-102 pode vir da medição do SU-102 — mas só porque o
    especialista declarou que são o MESMO perfil físico (2026-08-01).

    Sem essa identidade, transferir a cota seria inferência. Com ela, a
    transferência é legítima; o que não pode é o registro alegar que o TMS-102
    foi medido separadamente, nem as duas cotas divergirem.
    """
    e = []
    su102 = cfg.get("perfis", {}).get("SU-102", {})
    if not su102:
        return e
    comp = su102.get("candidato_compartilhamento", {})
    ident = su102.get("identidade_de_perfil", {})

    if comp.get("equivalencia_dimensional") == "APROVADA":
        # a) identidade confirmada é o único fundamento aceito aqui
        if not (ident.get("confirmada") is True
                and ident.get("confirmada_por") == "especialista_de_dominio"):
            e.append(_erro_ml(
                "SU-102.candidato_compartilhamento.equivalencia_dimensional",
                "APROVADA sem identidade_de_perfil confirmada pelo "
                "especialista de domínio"))

        ap = comp.get("aplicacao_dimensional", {})
        # b) o registro não pode alegar medição independente do TMS-102
        if ap.get("tms102_medido_separadamente") is not False:
            e.append(_erro_ml(
                "SU-102.candidato_compartilhamento.aplicacao_dimensional",
                "tms102_medido_separadamente tem de ser explicitamente false: "
                "a medição física foi feita no SU-102"))
        if ap.get("medicao_fisica_origem") != "SU-102":
            e.append(_erro_ml(
                "SU-102.candidato_compartilhamento.aplicacao_dimensional",
                "medicao_fisica_origem tem de ser SU-102"))
        # c) as cotas não podem divergir
        nominal = [su102.get("largura_mm"), su102.get("altura_mm")]
        if ap.get("dimensao_nominal_mm") != nominal:
            e.append(_erro_ml(
                "SU-102.candidato_compartilhamento.aplicacao_dimensional",
                f"dimensao_nominal_mm {ap.get('dimensao_nominal_mm')} diverge "
                f"da cota do SU-102 {nominal}"))
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
    erros += _valida_su041(cfg)
    erros += _valida_microlote_janela(cfg)
    return erros


if __name__ == "__main__":
    e = validar()
    print("\n".join(e) if e else "config íntegro")
