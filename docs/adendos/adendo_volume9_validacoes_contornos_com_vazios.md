# Adendo ao Volume 9 — Validações de contornos com vazios internos

Este adendo complementa o Volume 9 da documentação v1.0 (congelada) sem alterá-lo.
Origem: ADR-008.

## Validações do formato novo

Implementadas em `domain/entidades.py` (`validar_contornos`), sem dependências
externas (domínio puro):

1. Pelo menos um formato deve existir: `contorno_mm` OU `contorno_externo`.
2. Se `contorno_externo` existir:
   - polígono fechado (fechamento implícito: último ponto ≠ primeiro);
   - pelo menos 3 pontos;
   - área não nula;
   - sem auto-interseção.
3. Cada item de `vazios_internos`:
   - polígono fechado, com pelo menos 3 pontos e área não nula;
   - contido dentro de `contorno_externo`;
   - sem auto-interseção.
4. Vazios internos não se cruzam entre si; podem ser lista vazia.
5. Quando `contorno_mm` e `contorno_externo` coexistem, o novo é preferencial e
   o legado é tratado apenas como compatibilidade.

Falhas de validação levantam `ErroDominio` explícito — coerente com a filosofia
do Volume 9 (falha explícita, nunca silenciosa).
