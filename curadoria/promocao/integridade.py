"""Verificador da promoção E.4B — duas perguntas distintas.

**Evento histórico** (`verificar_evento_historico_e4c`): o manifesto descreve
fielmente o que aconteceu — `46 → 54`, `245 → 253`, os hashes daquele instante,
os oito IDs criados, os commits de procedência. Fatos imutáveis.

**Permanência atual** (`verificar_permanencia_atual_e4b`): os oito registros
promovidos continuam lá, íntegros, hoje.

A separação existe porque as duas perguntas envelhecem de formas opostas. O
hash de `dados/geometrias.json` no fim do E.4C é fato histórico; exigir que o
arquivo vivo continue tendo esse hash transformaria a próxima promoção legítima
em "corrupção". A integridade de hoje se verifica pelos registros do lote, não
pelo hash global nem pela contagem total do arquivo.
"""
from __future__ import annotations

import re

from . import evento
from .carregar import perfil_id_oficial
from .construir import comparar_contornos_exatamente
from .modelos import PERFIS_E4B, ResultadoValidacao

VERSAO_MANIFESTO_ESPERADA = "1.2"

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




CFG = "curadoria/aquisicao/configs/e4b_suprema.json"
DADOS_G = "dados/geometrias.json"
DADOS_A = "dados/perfil_geometria.json"
MAN = "curadoria/promocoes/e4c/manifesto_promocao_e4b.json"


def verificar_evento_historico_e4c(manifesto: dict) -> ResultadoValidacao:
    """O manifesto contra os fatos canônicos do EVENTO.

    Fatos, não estado: `46 → 54`, `245 → 253`, os hashes daquele instante, os
    oito IDs criados, os commits de procedência. Nada aqui olha para o disco.

    É deliberado que esta função **não** compare `hash_depois` com o arquivo
    vivo. Uma promoção futura legítima acrescentará registros e mudará o hash
    global de `dados/geometrias.json` — e isso não torna falso o que aconteceu
    no E.4C. Amarrar a auditoria histórica ao hash do arquivo de hoje
    transformaria a próxima promoção em "corrupção" aos olhos do verificador."""
    r = ResultadoValidacao.aprovado()

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
    if manifesto.get("versao_manifesto") != VERSAO_MANIFESTO_ESPERADA:
        r = r.somar(_r("versao_manifesto divergente",
                       manifesto.get("versao_manifesto"),
                       VERSAO_MANIFESTO_ESPERADA, MAN))
    if manifesto.get("data_utc") != evento.DATA_UTC_EVENTO:
        r = r.somar(_r("data_utc divergente do evento canônico",
                       manifesto.get("data_utc"), evento.DATA_UTC_EVENTO, MAN))

    for campo in ("commit_base_main", "commit_pre_promocao", "commit_curadoria_fonte"):
        v = manifesto.get(campo)
        if not (isinstance(v, str) and re.fullmatch(r"[0-9a-f]{40}", v)):
            r = r.somar(_r(f"{campo} não é hash de 40 hex", v, "40 hex", MAN))

    # Não podem ser inferidos do disco já promovido: uma reconstrução que os
    # derivasse produziria 54 -> 54 com zero criados.
    for campo, esperado in (
            ("commit_base_main", evento.COMMIT_BASE_MAIN),
            ("commit_pre_promocao", evento.COMMIT_PRE_PROMOCAO),
            ("commit_curadoria_fonte", evento.COMMIT_CURADORIA_FONTE)):
        if manifesto.get(campo) != esperado:
            r = r.somar(_r(f"{campo} divergente do evento canônico",
                           manifesto.get(campo), esperado, MAN))
    for campo, esperado in (
            ("hash_antes", dict(evento.HASH_ANTES)),
            ("hash_depois", dict(evento.HASH_DEPOIS)),
            ("quantidade_antes", dict(evento.QUANTIDADE_ANTES)),
            ("quantidade_depois", dict(evento.QUANTIDADE_DEPOIS)),
            ("ids_criados", list(evento.IDS_CRIADOS)),
            ("associacoes_criadas", list(evento.ASSOCIACOES_CRIADAS)),
            ("ids_reutilizados", []),
            ("associacoes_reutilizadas", [])):
        atual = manifesto.get(campo)
        if isinstance(esperado, list):
            atual = list(atual or [])
        if atual != esperado:
            r = r.somar(_r(f"{campo} divergente do evento canônico",
                           manifesto.get(campo), esperado, MAN))
    if manifesto.get("hash_antes") == manifesto.get("hash_depois"):
        r = r.somar(_r("hash_antes igual a hash_depois — não descreve promoção",
                       manifesto.get("hash_antes"), "diferentes", MAN))
    if manifesto.get("quantidade_antes") == manifesto.get("quantidade_depois"):
        r = r.somar(_r("quantidade_antes igual a quantidade_depois",
                       manifesto.get("quantidade_antes"), "diferentes", MAN))
    if manifesto.get("reconstruido_apos_gravacao") is not False:
        r = r.somar(_r("manifesto marcado como reconstruído",
                       manifesto.get("reconstruido_apos_gravacao"), False, MAN))
    return r


def verificar_permanencia_atual_e4b(config: dict, geometrias: dict,
                                    associacoes: dict,
                                    candidatos=()) -> ResultadoValidacao:
    """O que foi promovido no E.4B continua lá, íntegro, HOJE.

    Verifica os oito registros do lote — presença, contorno ponto a ponto,
    dimensão, vazios, associação, declaração no config, ausência de
    `GEO-TMS-102`. Não verifica contagens totais nem hash global: geometrias e
    associações **novas**, de outros lotes, são evolução legítima da
    biblioteca, não corrupção do E.4B."""
    r = ResultadoValidacao.aprovado()

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
    return r


def verificar_integridade_promocao_e4b(config: dict, geometrias: dict,
                                       associacoes: dict, manifesto: dict,
                                       candidatos=()) -> ResultadoValidacao:
    """As quatro camadas juntas: evento histórico + permanência atual.

    Verificar cada camada isoladamente deixaria passar o caso perigoso — o
    config afirmando um estado que `dados/` não sustenta, ou o manifesto
    descrevendo uma promoção que nunca aconteceu."""
    historico = verificar_evento_historico_e4c(manifesto)
    atual = verificar_permanencia_atual_e4b(config, geometrias, associacoes,
                                            candidatos)
    return historico.somar(atual)
