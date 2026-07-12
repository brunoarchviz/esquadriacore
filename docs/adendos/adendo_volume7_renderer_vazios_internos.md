# Adendo ao Volume 7 — Renderer com extrusão de vazios internos

Este adendo complementa o Volume 7 da documentação v1.0 (congelada) sem alterá-lo.
Origem: ADR-008.

## Extrusão com furos

O Renderer passa a tratar o formato novo como polígono composto com furos.
Implementação atual (`core_engine/renderer.py`):

- `extrudar_com_furos(contorno_externo, vazios_internos, comprimento_mm,
  rotacao_graus, posicao_mm)`: gera paredes do contorno externo e de cada vazio
  interno, mais tampas em grade que respeitam os furos (célula entra na tampa se
  o centro está dentro do externo e fora de todos os vazios).
- A função usa a MESMA convenção de eixos do `extrudar_perfil` legado
  (mapeamento por `rotacao_graus`/`posicao_mm`), preservando a correção do bug
  de achatamento da Fase 0.
- `renderizar` escolhe o extrusor pela presença de `contorno_externo`; o caminho
  legado (`contorno_mm` → `extrudar_perfil`) permanece intacto.

Implementações equivalentes em outros backends (futuro): SVG com
`fill-rule: evenodd`; Three.js com shape + holes.

O Renderer continua sem decidir equivalência, função, família ou
compatibilidade (ADR-002): apenas consome a GeometriaPadrao já curada.
