"""Promoção de candidatos da curadoria para a biblioteca oficial (`dados/`).

Este pacote NÃO conhece regra de montagem de janela nem de engenharia: ele
apenas transfere geometrias já aprovadas na curadoria para a biblioteca
oficial, de forma validada, transacional e idempotente (ADR-005).

O caminho inverso — `curadoria/aquisicao/` — é proibido de escrever em
`dados/` (`exportar.OFICIAIS_PROIBIDOS`). Este pacote é o único ponto do
repositório autorizado a fazê-lo, e só sob `--apply` explícito.
"""
