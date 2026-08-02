"""Verificador unificado da promoção E.4B.

Confere as QUATRO camadas juntas — config, dados, associações e manifesto.
Verificar cada uma isoladamente deixaria passar exatamente o caso perigoso: o
config afirmando um estado que `dados/` não sustenta, ou o manifesto descrevendo
uma gravação que não é a que está no disco.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import evento
from .carregar import RAIZ, hash_arquivo, perfil_id_oficial
from .construir import comparar_contornos_exatamente
from .modelos import PERFIS_E4B, ResultadoValidacao

# Expressões que, num campo de ESTADO ATUAL, contradizem a promoção. Campos
# `_historico*` e `historico_pre_promocao` ficam de fora: o fato de que antes da
# promoção não existia geometria oficial é verdadeiro e deve ser preservado.
FRASES_CONTRADITORIAS = (
    r"n[ãa]o existe geometria oficial",
    r"n[ãa]o existe GEO",
    r"nenhum GEO[- ]?\*? foi criado",
    r"nenhum perfil promovido",
    r"aguarda(ndo)? promo[çc][ãa]o",
    r"ainda[_ ]n[ãa]o[_ ]autorizada",
    r"aprovado S[ÓO] na",
    r"APROVADO SO NA CURADORIA",
)

CHAVES_HISTORICAS = ("historico", "_historico", "historico_pre_promocao",
                     "_conflito_historico", "_arbitragem_dimensional",
                     "origem_legado")


def _e_historico(caminho: str) -> bool:
    return any(h in caminho for h in CHAVES_HISTORICAS)


def _varrer_estado_atual(no, caminho: str, achados: list) -> None:
    if isinstance(no, dict):
        for k, v in no.items():
            _varrer_estado_atual(v, f"{caminho}.{k}", achados)
    elif isinstance(no, list):
        for i, v in enumerate(no):
            _varrer_estado_atual(v, f"{caminho}[{i}]", achados)
    elif isinstance(no, str) and not _e_historico(caminho):
        for p in FRASES_CONTRADITORIAS:
            if re.search(p, no, re.I):
                achados.append((caminho, no[:120]))
                break


def _r(regra, encontrado, esperado, arquivo, perfil="-"):
    return ResultadoValidacao.reprovado(perfil, regra, encontrado, esperado, arquivo)


def verificar_integridade_promocao_e4b(config: dict, geometrias: dict,
                                       associacoes: dict, manifesto: dict,
                                       candidatos=(),
                                       raiz: Path | None = None) -> ResultadoValidacao:
    """`raiz` permite verificar uma árvore isolada em vez do repositório vivo.

    Sem isso, um teste integral em `tmp_path` compararia o manifesto da árvore
    isolada com os arquivos do repositório — e passaria por acidente."""
    raiz = Path(raiz) if raiz else RAIZ
    r = ResultadoValidacao.aprovado()
    CFG, DADOS_G = "curadoria/aquisicao/configs/e4b_suprema.json", "dados/geometrias.json"
    DADOS_A = "dados/perfil_geometria.json"
    MAN = "curadoria/promocoes/e4c/manifesto_promocao_e4b.json"

    # ---------------------------------------------------------------- config
    ml = config.get("microlote_janela", {})
    if ml.get("promocao_oficial_realizada") is not True:
        r = r.somar(_r("promocao_oficial_realizada não é true",
                       ml.get("promocao_oficial_realizada"), True, CFG))
    for c in PERFIS_E4B:
        # No config pré-promoção `promocao_oficial` é a STRING
        # "ainda_nao_autorizada". Isso tem de virar reprovação descrita, não
        # AttributeError: o verificador precisa funcionar nos dois estados.
        po = config.get("perfis", {}).get(c, {}).get("promocao_oficial")
        if not isinstance(po, dict):
            po = {"_valor_nao_estruturado": po} if po else {}
        if po.get("status") != "PROMOVIDO":
            r = r.somar(_r("perfil sem status PROMOVIDO", po.get("status"),
                           "PROMOVIDO", CFG, c))
        if po.get("id_geometria") != f"GEO-{c}":
            r = r.somar(_r("id_geometria incorreto no config",
                           po.get("id_geometria"), f"GEO-{c}", CFG, c))
        if po.get("perfil_id_oficial") != perfil_id_oficial(c):
            r = r.somar(_r("perfil_id_oficial incorreto",
                           po.get("perfil_id_oficial"), perfil_id_oficial(c), CFG, c))

    achados = []
    _varrer_estado_atual(ml, "microlote_janela", achados)
    for c in PERFIS_E4B:
        _varrer_estado_atual(config.get("perfis", {}).get(c, {}), f"perfis.{c}", achados)
    for caminho, texto in achados:
        r = r.somar(_r("nota de estado atual contradiz a promoção",
                       f"{caminho}: {texto}", "sem contradição", CFG))

    # ----------------------------------------------------------------- dados
    por_id = {g["id"]: g for g in geometrias.get("geometrias", [])}
    for c in PERFIS_E4B:
        gid = f"GEO-{c}"
        g = por_id.get(gid)
        if g is None:
            r = r.somar(_r("geometria ausente da biblioteca", None, gid, DADOS_G, c))
            continue
        esperado_vazios = config["perfis"][c].get("vazios_esperados")
        if len(g.get("vazios_internos") or []) != esperado_vazios:
            r = r.somar(_r("quantidade de vazios divergente",
                           len(g.get("vazios_internos") or []), esperado_vazios,
                           DADOS_G, c))
        xs = [p[0] for p in g["contorno_externo"]]
        ys = [p[1] for p in g["contorno_externo"]]
        larg, alt = round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)
        esp = (round(config["perfis"][c]["largura_mm"], 2),
               round(config["perfis"][c]["altura_mm"], 2))
        if abs(larg - esp[0]) > 0.05 or abs(alt - esp[1]) > 0.05:
            r = r.somar(_r("bounding box divergente da cota", (larg, alt), esp,
                           DADOS_G, c))
    if "GEO-TMS-102" in por_id:
        r = r.somar(_r("GEO-TMS-102 existe", "GEO-TMS-102",
                       "ausente (duplicaria o SU-102)", DADOS_G))

    for cand in candidatos:
        g = por_id.get(cand.id_geometria)
        if g is not None:
            cmp_ = comparar_contornos_exatamente(cand.contorno_externo,
                                                 g["contorno_externo"])
            if not cmp_.ok:
                r = r.somar(_r("contorno promovido difere do artefato curado",
                               cmp_.falhas[0]["encontrado"],
                               cmp_.falhas[0]["esperado"], DADOS_G,
                               cand.codigo_perfil))

    # ------------------------------------------------------------ associações
    assoc = {a["perfil_id"]: a["geometria_padrao_id"]
             for a in associacoes.get("associacoes", [])}
    for c in PERFIS_E4B:
        pid = perfil_id_oficial(c)
        if pid not in assoc:
            r = r.somar(_r("associação ausente", None, pid, DADOS_A, c))
        elif assoc[pid] != f"GEO-{c}":
            r = r.somar(_r("associação aponta para GEO errado", assoc[pid],
                           f"GEO-{c}", DADOS_A, c))
    orfas = [p for p, g in assoc.items() if g not in por_id]
    if orfas:
        r = r.somar(_r("associações órfãs", orfas, [], DADOS_A))

    # -------------------------------------------------------------- manifesto
    if manifesto.get("estado") != "PROMOVIDO":
        r = r.somar(_r("manifesto não está PROMOVIDO", manifesto.get("estado"),
                       "PROMOVIDO", MAN))
    if list(manifesto.get("perfis") or []) != list(PERFIS_E4B):
        r = r.somar(_r("manifesto com lista de perfis divergente",
                       manifesto.get("perfis"), list(PERFIS_E4B), MAN))
    if len(manifesto.get("geometrias") or []) != 8:
        r = r.somar(_r("manifesto sem as 8 geometrias",
                       len(manifesto.get("geometrias") or []), 8, MAN))
    if manifesto.get("resultado_idempotencia") != "APROVADA":
        r = r.somar(_r("manifesto sem idempotência aprovada",
                       manifesto.get("resultado_idempotencia"), "APROVADA", MAN))

    for campo in ("commit_base_main", "commit_pre_promocao", "commit_curadoria_fonte"):
        v = manifesto.get(campo)
        if not (isinstance(v, str) and re.fullmatch(r"[0-9a-f]{40}", v)):
            r = r.somar(_r(f"{campo} não é hash de 40 hex", v, "40 hex", MAN))

    # ---- fatos canônicos do EVENTO ---------------------------------------
    # Não podem ser inferidos do disco já promovido: uma reconstrução que os
    # derivasse produziria 54 -> 54 com zero criados.
    for campo, esperado in (
            ("commit_base_main", evento.COMMIT_BASE_MAIN),
            ("commit_pre_promocao", evento.COMMIT_PRE_PROMOCAO),
            ("commit_curadoria_fonte", evento.COMMIT_CURADORIA_FONTE)):
        if manifesto.get(campo) != esperado:
            r = r.somar(_r(f"{campo} divergente do evento canônico",
                           manifesto.get(campo), esperado, MAN))
    if manifesto.get("hash_antes") != dict(evento.HASH_ANTES):
        r = r.somar(_r("hash_antes divergente do evento canônico",
                       manifesto.get("hash_antes"), dict(evento.HASH_ANTES), MAN))
    if manifesto.get("hash_depois") != dict(evento.HASH_DEPOIS):
        r = r.somar(_r("hash_depois divergente do evento canônico",
                       manifesto.get("hash_depois"), dict(evento.HASH_DEPOIS), MAN))
    if manifesto.get("hash_antes") == manifesto.get("hash_depois"):
        r = r.somar(_r("hash_antes igual a hash_depois — não descreve promoção",
                       manifesto.get("hash_antes"), "diferentes", MAN))
    if manifesto.get("quantidade_antes") != dict(evento.QUANTIDADE_ANTES):
        r = r.somar(_r("quantidade_antes divergente do evento canônico",
                       manifesto.get("quantidade_antes"),
                       dict(evento.QUANTIDADE_ANTES), MAN))
    if list(manifesto.get("ids_criados") or []) != list(evento.IDS_CRIADOS):
        r = r.somar(_r("ids_criados divergente do evento canônico",
                       manifesto.get("ids_criados"), list(evento.IDS_CRIADOS), MAN))
    if list(manifesto.get("associacoes_criadas") or []) != list(evento.ASSOCIACOES_CRIADAS):
        r = r.somar(_r("associacoes_criadas divergente do evento canônico",
                       manifesto.get("associacoes_criadas"),
                       list(evento.ASSOCIACOES_CRIADAS), MAN))
    if list(manifesto.get("ids_reutilizados") or []) != []:
        r = r.somar(_r("ids_reutilizados deveria ser vazio no evento",
                       manifesto.get("ids_reutilizados"), [], MAN))
    if list(manifesto.get("associacoes_reutilizadas") or []) != []:
        r = r.somar(_r("associacoes_reutilizadas deveria ser vazio no evento",
                       manifesto.get("associacoes_reutilizadas"), [], MAN))
    if manifesto.get("reconstruido_apos_gravacao") is not False:
        r = r.somar(_r("manifesto marcado como reconstruído",
                       manifesto.get("reconstruido_apos_gravacao"), False, MAN))

    # hash e contagem do manifesto contra os arquivos que estão no disco AGORA
    # hash_depois TAMBÉM tem de bater com o arquivo que está no disco agora.
    # hash_antes NÃO é comparado com o disco — é fato histórico.
    for rel, real in ((evento.REL_GEOMETRIAS, raiz / evento.REL_GEOMETRIAS),
                      (evento.REL_ASSOCIACOES, raiz / evento.REL_ASSOCIACOES)):
        esperado = (manifesto.get("hash_depois") or {}).get(rel)
        if esperado and Path(real).exists() and esperado != hash_arquivo(real):
            r = r.somar(_r("hash_depois do manifesto não bate com o arquivo atual",
                           hash_arquivo(real)[:16], esperado[:16], MAN))
    qd = manifesto.get("quantidade_depois") or {}
    if qd.get("geometrias") != len(geometrias.get("geometrias", [])):
        r = r.somar(_r("quantidade_depois de geometrias divergente",
                       len(geometrias.get("geometrias", [])), qd.get("geometrias"), MAN))
    if qd.get("associacoes") != len(associacoes.get("associacoes", [])):
        r = r.somar(_r("quantidade_depois de associações divergente",
                       len(associacoes.get("associacoes", [])),
                       qd.get("associacoes"), MAN))
    return r
