# Adendo ao Volume 10 — Testes do modelo de perfil oco

Este adendo complementa o Volume 10 da documentação v1.0 (congelada) sem alterá-lo.
Origem: ADR-008.

## Testes adicionados (tests/test_perfil_oco.py)

1. Geometria com `contorno_externo` e `vazios_internos` — validação passa.
2. Geometria com `vazios_internos` vazio — válida.
3. Geometria legada com apenas `contorno_mm` — continua válida (compatibilidade).
4. Geometria sem `contorno_mm` e sem `contorno_externo` — falha explícita.
5. Vazio fora do contorno externo — falha explícita.
6. Vazio intersectando outro vazio — falha explícita.
7. Renderer preserva vazios internos (nenhuma célula de tampa dentro do vazio).
8. Regressão de DADOS do GEO-SU-005 iteração 11: número de vazios internos,
   contagem mínima de pontos do contorno, área de material e contenção dos
   vazios — verificados contra `dados/geometrias.json`.

Nota metodológica: a regressão do item 8 é deliberadamente de DADOS, não de
imagem. Comparação pixel a pixel é frágil (quebra com versão do matplotlib,
fontes e DPI) e não protege o que importa: a geometria registrada.
