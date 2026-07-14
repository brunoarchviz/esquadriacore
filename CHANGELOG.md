# Changelog — EsquadriaCore

Formato baseado em Keep a Changelog. Versionamento semântico.

## [0.5.0-alpha] — 2026-07-13 — "Consumption Contract Release"

### Adicionado
- **ADR-009 aceito** — Contrato Mínimo de Consumo da Biblioteca (contrato v1.0):
  fronteira de leitura estável para os dados já homologados, sem entidade de
  domínio nova e sem alterar a fonte de verdade.
- `contrato/consumo.py`: carregador/adaptador puro (sem dependências externas,
  sem frontend). DTOs imutáveis `BoundingBoxDTO`, `GeometriaConsumivel`,
  `AssociacaoConsumivel`, `BibliotecaConsumivel` — `frozen`, coordenadas em
  tuplas e índice interno `MappingProxyType` (somente leitura). Normaliza só na
  saída: orientação (externo CCW, vazios CW), fechamento implícito, nível por
  enumeração fechada; `contorno_mm` como fallback de entrada, forma única de
  saída indicada por `fonte_contorno`; bounding-box como objeto nomeado.
  Validação geométrica delegada a `domain.validar_contornos` (ADR-008).
- `contrato/schemas/biblioteca_consumo.schema.json`: face de máquina do
  contrato (saída serializada — geometrias + associações).
- `docs/adendos/adendo_contrato_consumo.md`: especificação operacional do
  contrato (a v1.0 permanece congelada).
- `tests/test_contrato_consumo.py`: testes do contrato (carregamento das 46
  geometrias e 245 associações, 10 renderizáveis / 36 brutas, orientação,
  coordenadas intactas, legado, imutabilidade, integridade referencial e
  compatibilidade estrutural limitada com o schema).
- `curadoria/painel_comercial.py` → `curadoria/contornos/painel_10_comerciais.png`:
  evidência das 10 geometrias renderizáveis, carregadas pelo próprio contrato
  (fluxo `JSON oficial → contrato.consumo → DTO → painel`).

### Convenção de consumo (ADR-009)
- `unidade = "mm"`; `referencial = "local_do_perfil"`;
  `eixo_x = "positivo_para_direita"`; `eixo_y = "positivo_para_cima"`.
- referencial local por geometria (sem origem canônica compartilhada);
  bounding-box calculado sem transladar coordenadas.
- `versao_schema = "1.0"` vive no contrato, não é gravado nos JSONs.
- `fabricante_derivado` inferido do prefixo de `perfil_id` (None se
  desconhecido); não é dado armazenado e não implica intercambiabilidade.
- schema publicado ainda não validado por implementação oficial de JSON Schema
  (`jsonschema` não adotado); testes usam validação estrutural limitada.

### Validado
- 46 geometrias e 245 associações carregadas pelo contrato; 10 renderizáveis,
  36 brutas.
- Fonte de verdade preservada: `dados/geometrias.json` e
  `dados/perfil_geometria.json` byte a byte inalterados (SHA-256 antes = depois).
- Nenhuma geometria homologada, entidade de domínio ou volume congelado alterado.
- Evidência de fechamento do sprint: suíte completa verde (62 testes, dos quais
  37 do contrato).

## [0.4.0-alpha] — 2026-07-13 — "Sample Contours Release"

### Adicionado
- 9 novas geometrias em `2_renderizavel_comercial` (amostra Sprint E.2):
  GEO-SU-024, SU-025, SU-009, SU-056, SU-280, SU-228, SU-230, LG-003 e LG-006.
  Contorno `contorno_externo` + `vazios_internos` (ADR-008), curadoria fina
  por marcação colorida do Bruno, aprovados visualmente em 2026-07-12.
- Terminais em "J" transplantados do GEO-SU-005 (mesmo template validado),
  substituindo a interpretação errada em "U invertido".
- Evidências de catálogo lado a lado das 9 geometrias em
  `curadoria/comparacao/` (Alcoa Suprema, Vitral Sul e Alcoa Gold 3/4).
- Scripts de curadoria da amostra em `curadoria/`:
  `secoes_amostra_e2.py`, `render_secoes_e2.py`,
  `gerar_evidencias_lado_a_lado.py`.

### Corrigido
- Funções de GEO-SU-228 (Marco Inferior Porta de Correr) e GEO-SU-230
  (Marco Inferior Portas) gravadas na descrição, confirmadas pelo Bruno.
- Página real do card Alcoa de 4 perfis (SU-024/025/056/280) corrigida nas
  notas de auditoria em `dados/perfil_geometria.json`.

### Validado
- 25/25 testes passando; os 9 contornos passam em `validar_contornos()`.
- GEO-SU-005 preservado sem alteração.
- Sinal de peso (área × 2,71): 8 das 9 dentro de ±13% do catálogo; GEO-SU-056
  fica +31% com parede padrão 1,6mm — registrado como alerta de curadoria
  (suspeita de parede mais fina no perfil real), não bloqueia a homologação
  de contorno (equivalência já validada no Sprint E).

## [0.3.0-alpha] — 2026-07-12 — "Hollow Profile Release"

### Adicionado
- ADR-008 aceito: GeometriaPadrao suporta `contorno_externo` + `vazios_internos`
  (perfil oco), com `contorno_mm` preservado como legado. Salvaguarda: a
  validação do modelo não homologa automaticamente geometrias individuais.
- `core_engine.extrudar_com_furos`: extrusão com paredes internas e tampas
  que respeitam os vazios.
- `domain.validar_contornos` + `ContornoInvalido`: validações do novo formato
  (domínio puro, falha explícita).
- `tests/test_perfil_oco.py`: 14 testes (validações, extrusão com furos e
  regressão de DADOS do GEO-SU-005 — nunca comparação de imagem).
- `docs/adendos/`: adendos aos Volumes 3, 7, 9 e 10 (v1.0 permanece congelada).
- Método de curadoria fina registrado no plano de curadoria (feedback do Bruno
  por marcação colorida, iterações versionadas, aprovação explícita).

### Validado
- GEO-SU-005: primeiro contorno `2_renderizavel_comercial` da biblioteca —
  11 iterações de curadoria fina, aprovado visualmente pelo Bruno
  (evidência: curadoria/contornos/SU-005_lado_a_lado_iter11.png).
- 25/25 testes passando (11 da base + 14 do perfil oco).

## [0.2.0-alpha] — 2026-07-09 — "Multi Provider Release"

### Adicionado
- `providers/ocr.py`: OcrProvider via pdftoppm + Tesseract, para PDFs sem
  texto extraível (caso real: Alcoa, seção Suprema, págs 170-183).
- Suporte a `kg/mt` no PADRAO_PESO (variante real encontrada no Vitral Sul).

### Corrigido
- Premissa do CLAUDE.md sobre Vitral Sul: não é OCR puro, é caso híbrido
  (códigos via PdfTextoProvider, pesos embutidos em JPEG aceitos como
  peso_suspeito — comportamento correto conforme Volume 9).

### Validado
- 11/11 testes passando, zero xfail — os dois casos antes bloqueados
  (Alcoa e Vitral Sul) agora têm Provider real e testado.
- OcrProvider extraiu 38 perfis reais da Alcoa (19 SU-, 17 com peso válido).

## [0.1.0-alpha] — 2026-07-09 — "Foundation Release"

Primeira fundação sólida do EsquadriaCore. Marca a transição de projeto
experimental para produto de engenharia com arquitetura validada.

### Adicionado
- Documentação v1.0 congelada: Constituição + Volumes 1, 2, 3, 4, 6, 7, 9, 10, 11
  + backlog editorial (ver `docs/`).
- `domain/`: entidades do Modelo de Domínio (Volume 3) e modelo de erros (Volume 9).
- `providers/`: contrato `Provider` (ADR-003) isolado em `base.py` +
  `PdfTextoProvider` (unificação dos parsers Linha 25/30, antes duplicados).
- `pipeline/`: orquestração da aquisição de dados (Volume 6).
- `core_engine/`: Renderer matplotlib + resolução de geometria
  Perfil→PerfilGeometria→GeometriaPadrao (Volume 7, ADR-005).
- `tests/`: suíte básica (Volume 10) — unitários, integração, regressão contra o
  catálogo Centenário real, e 2 casos `xfail` aguardando o Provider de OCR.

### Validado
- 10/10 testes passando, incluindo regressão real (Linha 25 = 73 perfis,
  Linha 30 = 55 perfis).
- Auditoria arquitetural: nenhuma questão Crítica; separação de camadas resistiu
  à implementação (código corresponde à arquitetura documentada).

### Corrigido
- Auditoria I-1: contrato `Provider` movido de dentro de `pdf_texto.py` para
  `providers/base.py` — o Pipeline e as implementações agora importam o contrato
  do lugar correto.

### Conhecido / pendente
- Provider de OCR ainda não existe (Sprint D) — casos Alcoa (vetor sem texto) e
  Vitral Sul (raster embutido) estão marcados `xfail` e viram verdes quando o OCR
  for implementado.
- Renderer Three.js pendente de ambiente com rede (Volume 7).
