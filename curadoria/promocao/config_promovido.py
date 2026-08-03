"""Transformação determinística do config de curadoria para o estado promovido.

Até aqui a CLI recebia um config JÁ promovido e apenas marcava
`CONFIG_FINALIZADO` no journal, sem escrever nada. Isso passava na branch viva
porque o config já estava correto — e falharia em silêncio partindo do estado
pré-promoção, que é exatamente o estado real de uma promoção.

A função é PURA: recebe o config anterior, devolve um documento novo. Nunca
muta o objeto recebido, nunca lê o disco e é idempotente — aplicá-la sobre um
config já promovido devolve o mesmo documento.

Nada é removido. As notas que descreviam o estado ANTERIOR não são apagadas:
são movidas para blocos `historico_pre_promocao` datados, porque "antes da
promoção não existia GEO-SU-053" continua sendo verdade histórica. O que não
pode sobreviver é a mesma frase apresentada como estado ATUAL.
"""
from __future__ import annotations

import copy

from .carregar import PromocaoErro, perfil_id_oficial
from .modelos import PERFIS_E4B

LOTE_PROMOCAO = "E4C"

ORIGEM_DIMENSIONAL_PADRAO = "COTA_DE_CATALOGO"
ORIGEM_DIMENSIONAL_SU102 = "MEDICAO_FISICA_COM_NOMINALIZACAO_POR_DOMINIO"

# Notas de ESTADO ATUAL que a promoção torna falsas. Cada entrada declara o
# texto anterior aceito e o texto novo; qualquer outro valor faz a
# transformação recusar, em vez de sobrescrever uma edição que ninguém revisou.
NOTAS_ESTADO_ATUAL: dict[tuple[str, ...], tuple[str, str]] = {
    ("perfis", "SU-053", "_nota_estado"): (
        "APROVADO SO NA CURADORIA. Nao existe GEO-SU-053 nos dados oficiais e "
        "nao ha associacao oficial entre fabricantes: a gravacao oficial "
        "aguarda o fechamento das oito geometrias do microlote.",
        "Aprovado na curadoria (E.4B) e promovido oficialmente no E.4C: "
        "GEO-SU-053 existe em dados/ com associacao ALCOA-SU-053. O historico "
        "anterior a promocao esta em historico_pre_promocao.",
    ),
    ("microlote_janela", "_nota_contagem"): (
        "8 de 8 fechados na curadoria. Nenhum perfil promovido oficialmente.",
        "8 de 8 perfis fechados na curadoria (E.4B) e 8 de 8 promovidos "
        "oficialmente para dados/ na Sprint E.4C.",
    ),
    ("microlote_janela", "_nota_fechamento"): (
        "fechamento da CURADORIA do microlote E.4B. NAO e promocao oficial "
        "para dados/: nenhum GEO-* foi criado.",
        "A curadoria foi encerrada no E.4B. A promocao oficial foi realizada "
        "depois, no E.4C, sem reabrir nem reprocessar os contornos: os "
        "artefatos aprovados foram copiados ponto a ponto.",
    ),
}

_NOTA_VISUAL_ANTES = ("aprovado SO na camada de curadoria; nao existe "
                      "geometria oficial em dados/")
_NOTA_VISUAL_DEPOIS = ("aprovado na camada de curadoria; a diferenca bruto x "
                       "comercial foi conferida visualmente no painel do lote 2")

for _p in ("SU-001", "SU-002", "SU-003"):
    NOTAS_ESTADO_ATUAL[("perfis", _p, "aprovacao_visual", "_nota")] = (
        _NOTA_VISUAL_ANTES, _NOTA_VISUAL_DEPOIS)

# Blocos históricos criados pela promoção. Preservam, datado, o que a nota de
# estado atual deixou de afirmar.
HISTORICO_APROVACAO_VISUAL = {
    "estado_na_data_da_aprovacao_visual": "APROVADO_APENAS_NA_CURADORIA",
    "data": "2026-07-28",
    "observacao": ("Na data da aprovacao visual ainda nao existia geometria "
                   "oficial em dados/. Isso e HISTORICO: a promocao ocorreu "
                   "depois, na Sprint E.4C."),
}

HISTORICOS: dict[tuple[str, ...], dict] = {
    ("perfis", "SU-053", "historico_pre_promocao"): {
        "estado": "APROVADO_APENAS_NA_CURADORIA",
        "observacao": ("Ate o fechamento das oito geometrias do microlote nao "
                       "existia GEO-SU-053 nos dados oficiais nem associacao "
                       "oficial. Isso e HISTORICO: a gravacao ocorreu na "
                       "Sprint E.4C."),
    },
}
for _p in ("SU-001", "SU-002", "SU-003"):
    HISTORICOS[("perfis", _p, "aprovacao_visual", "historico_pre_promocao")] = \
        HISTORICO_APROVACAO_VISUAL

# Perfis que ganham o resumo `estado_atual` ao lado do bloco de promoção.
PERFIS_COM_ESTADO_ATUAL = ("SU-001", "SU-002", "SU-003")

NOTA_PROMOCAO_MICROLOTE = ("8 de 8 promovidos para dados/ na sprint E.4C. "
                           "Manifesto em curadoria/promocoes/e4c/"
                           "manifesto_promocao_e4b.json.")


class ConfigInesperado(PromocaoErro):
    """O config de entrada não é nem o pré-promoção nem o já promovido."""


def _descer(doc: dict, caminho: tuple[str, ...]) -> dict:
    no = doc
    for k in caminho:
        if not isinstance(no, dict) or k not in no:
            raise ConfigInesperado(
                f"caminho ausente no config: {'.'.join(caminho)}")
        no = no[k]
    return no


def bloco_promocao_oficial(candidato) -> dict:
    """O que a promoção afirma sobre um perfil. Ordem de chaves estável."""
    c = candidato.codigo_perfil
    bloco = {
        "status": "PROMOVIDO",
        "id_geometria": candidato.id_geometria,
        "lote": LOTE_PROMOCAO,
        "perfil_id_oficial": perfil_id_oficial(c),
    }
    if c == "SU-102":
        # A medição física é do SU-102 e a cota oficial é a nominal; ambas
        # ficam registradas, e a identidade com o TMS-102 é afirmada aqui
        # porque foi ela que dispensou uma geometria duplicada.
        bloco["dimensao_nominal_mm"] = list(candidato.dimensao_nominal_mm)
        bloco["origem_dimensional"] = ORIGEM_DIMENSIONAL_SU102
        bloco["identidade_tms102"] = "CONFIRMADA"
        bloco["geo_tms102_criado"] = False
    else:
        bloco["origem_dimensional"] = ORIGEM_DIMENSIONAL_PADRAO
    return bloco


def construir_config_promovido_e4b(config_antes: dict, candidatos) -> dict:
    """Config promovido a partir do config anterior. Puro e idempotente."""
    candidatos = tuple(candidatos)
    codigos = tuple(c.codigo_perfil for c in candidatos)
    if codigos != tuple(PERFIS_E4B):
        raise ConfigInesperado(
            f"candidatos fora do microlote canônico: {codigos} != {PERFIS_E4B}")

    cfg = copy.deepcopy(config_antes)

    # --- notas de estado atual (o histórico correspondente é preservado abaixo)
    for caminho, (antes, depois) in NOTAS_ESTADO_ATUAL.items():
        pai = _descer(cfg, caminho[:-1])
        atual = pai.get(caminho[-1])
        if atual == depois:
            continue                       # já promovido: idempotente
        if atual != antes:
            raise ConfigInesperado(
                f"{'.'.join(caminho)}: texto inesperado — a promoção não "
                f"sobrescreve nota que ninguém revisou.\n"
                f"  encontrado: {atual!r}\n  esperado  : {antes!r}")
        pai[caminho[-1]] = depois

    # --- promoção oficial por perfil
    for cand in candidatos:
        p = cfg["perfis"].get(cand.codigo_perfil)
        if p is None:
            raise ConfigInesperado(f"{cand.codigo_perfil}: ausente do config")
        p["promocao_oficial"] = bloco_promocao_oficial(cand)
        if cand.codigo_perfil in PERFIS_COM_ESTADO_ATUAL:
            p["estado_atual"] = {
                "promocao_oficial": "PROMOVIDO",
                "lote": LOTE_PROMOCAO,
                "id_geometria": cand.id_geometria,
            }

    # --- blocos históricos datados (depois da promoção: num config novo eles
    # entram DEPOIS do bloco de promoção, mantendo a ordem já publicada)
    for caminho, bloco in HISTORICOS.items():
        pai = _descer(cfg, caminho[:-1])
        atual = pai.get(caminho[-1])
        if atual is None:
            pai[caminho[-1]] = copy.deepcopy(bloco)
        elif atual != bloco:
            raise ConfigInesperado(
                f"{'.'.join(caminho)}: bloco histórico divergente do esperado")

    # --- microlote
    ml = cfg.get("microlote_janela")
    if not isinstance(ml, dict):
        raise ConfigInesperado("config sem bloco microlote_janela")
    ml["promocao_oficial_realizada"] = True
    ml["lote_promocao"] = LOTE_PROMOCAO
    ml["_nota_promocao"] = NOTA_PROMOCAO_MICROLOTE
    ml["fechados_na_curadoria"] = 8
    ml["aguardando_evidencia_externa"] = 0
    ml["pendencia_restante"] = None

    return cfg
