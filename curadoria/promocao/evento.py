"""Fatos canônicos do evento de promoção E.4B → E.4C.

Estes valores descrevem o que ACONTECEU, não o que está no disco agora. São
verificados contra o histórico do git (`e356ba2` antes, `ad58b47` depois).

Por que ficam fixos aqui: `hash_antes`, `quantidade_antes`, `ids_criados`,
`associacoes_criadas` e `commit_pre_promocao` **não podem ser inferidos**
observando o estado já promovido. Uma reconstrução que os derivasse do disco
produziria `54 → 54` com `ids_criados: []` — descrevendo a própria reconstrução
em vez da promoção. Foi exatamente esse o erro que apagou o registro do evento.
"""
from __future__ import annotations

from .modelos import PERFIS_E4B

# Merge do PR #4 na main: base da sprint e fonte da curadoria.
COMMIT_BASE_MAIN = "e356ba2c34b3c04711d97cbf576f3737be974af3"

# HEAD imediatamente ANTES da gravação em dados/ — o commit dos testes, quando
# o motor estava pronto e nada havia sido promovido. NÃO é o HEAD atual: este
# muda a cada commit novo e não representa o instante da promoção.
COMMIT_PRE_PROMOCAO = "53fcfaca7ba89ccc1c7a0fc8c52a7e6efc18dc76"

COMMIT_CURADORIA_FONTE = COMMIT_BASE_MAIN

DESCRICAO_CURADORIA_FONTE = ("E.4B concluído e correção de identidade "
                             "SU-102 × TMS-102 integrada.")

DATA_UTC_EVENTO = "2026-08-02T14:10:14Z"

REL_GEOMETRIAS = "dados/geometrias.json"
REL_ASSOCIACOES = "dados/perfil_geometria.json"

HASH_ANTES = {
    REL_GEOMETRIAS: "35f956799b492909f9b362493804d27b8a9abe8df067b9c9c5a071c3121bc769",
    REL_ASSOCIACOES: "5961bb42a90d8a5f52bf5bea6f6548fc3cf16d761907227f09d24724f24e3f4e",
}
HASH_DEPOIS = {
    REL_GEOMETRIAS: "30bf2b7865d0aaae8e488beb048feac5da9ada932abd5c0e748b9f68254f5fa0",
    REL_ASSOCIACOES: "26f09d8d3bfe3b202aa46c500a4ba60ad1eef274927e8cc4f3d954de6d94a532",
}

QUANTIDADE_ANTES = {"geometrias": 46, "associacoes": 245}
QUANTIDADE_DEPOIS = {"geometrias": 54, "associacoes": 253}

IDS_CRIADOS = tuple(f"GEO-{p}" for p in PERFIS_E4B)
ASSOCIACOES_CRIADAS = tuple(f"ALCOA-{p}" for p in PERFIS_E4B)
IDS_REUTILIZADOS: tuple[str, ...] = ()
ASSOCIACOES_REUTILIZADAS: tuple[str, ...] = ()


def recibo_evento() -> dict:
    """Recibo persistido no journal — suficiente para recriar o manifesto
    canônico mesmo que o processo morra depois de gravar `dados/`."""
    return {
        "commit_base_main": COMMIT_BASE_MAIN,
        "commit_pre_promocao": COMMIT_PRE_PROMOCAO,
        "commit_curadoria_fonte": COMMIT_CURADORIA_FONTE,
        "data_utc": DATA_UTC_EVENTO,
        "hash_antes": dict(HASH_ANTES),
        "hash_esperado_depois": dict(HASH_DEPOIS),
        "quantidade_antes": dict(QUANTIDADE_ANTES),
        "quantidade_depois": dict(QUANTIDADE_DEPOIS),
        "ids_criados": list(IDS_CRIADOS),
        "associacoes_criadas": list(ASSOCIACOES_CRIADAS),
        "ids_reutilizados": list(IDS_REUTILIZADOS),
        "associacoes_reutilizadas": list(ASSOCIACOES_REUTILIZADAS),
    }
