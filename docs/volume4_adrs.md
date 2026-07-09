# Volume 4 — Architecture Decision Records (ADRs)

---
**Versão:** 1.0.0
**Status:** Estável (histórico cumulativo — novos ADRs são adicionados, os
existentes não são reescritos)
**Sprint de origem:** Sprint A (consolidação); decisões originais tomadas ao longo
de todo o processo de design review
**Última atualização:** 2026-07-08
**ADRs relacionados:** este Volume é o registro de todos
**Implementação correspondente:** Core Engine (Fase 0), Pipeline de Aquisição
(Fases 1-4), Prova de conceito GeometriaPadrao
**Dependências:** nenhuma — este é o registro-fonte
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** todos
---

## Convenção deste Volume

Cada ADR abaixo documenta: o contexto que motivou a decisão, a decisão em si, e a
evidência real que a validou (nunca especulação). Numeração cronológica única,
nunca reiniciada (regra estabelecida na Constituição da Documentação).

---

### ADR-001 — Geometria é a única fonte de verdade

**Estado:** Estável

**Contexto:** definição inicial da arquitetura do Core Engine.
**Decisão:** nenhuma imagem é armazenada como artefato primário; toda imagem
(frontal, isométrica, explodida) é derivada da geometria vetorial do perfil no
momento da renderização.
**Evidência:** confirmado pela Fase 0 (Core Engine), onde a mesma geometria gerou
vistas diferentes sem duplicação de dado.
**Consequências:** nenhum artefato de imagem é fonte de verdade — todos são
descartáveis e regeráveis; qualquer mudança de estilo visual não exige reprocessar
dado de engenharia, só re-renderizar.
**Afeta:** Volumes 3, 7 | Entidades: GeometriaPadrao, Vista, Renderer

---

### ADR-002 — Renderer nunca conhece regras de engenharia

**Estado:** Estável

**Contexto:** definição da separação entre Vista e Cena Técnica.
**Decisão:** o Renderer consome apenas Vistas (parâmetros de apresentação: ângulo,
escala, estilo). Nunca acessa diretamente regras de montagem ou dados físicos do
Perfil sem passar pela Cena.
**Evidência:** implementado e testado na Fase 0 e na prova de conceito de
GeometriaPadrao — o Renderer renderizou perfis de fabricantes diferentes (Alcoa,
Vitral Sul) sem nunca "saber" que eram fabricantes distintos.
**Consequências:** o Renderer pode ser substituído (matplotlib → Three.js) sem
tocar em regra de negócio; qualquer bug de montagem/compatibilidade nunca pode ser
corrigido "no Renderer", sempre na Cena Técnica ou no domínio.
**Afeta:** Volumes 3, 7 | Entidades: Renderer, Vista, Cena Técnica

---

### ADR-003 — Provider abstrai a origem dos dados

**Estado:** Validado (4 casos reais confirmam o princípio; poucos Providers implementados além de PDF-com-texto)

**Contexto:** ao testar o Pipeline de Aquisição em catálogos de fabricantes
diferentes (Centenário, Euroshow, Alcoa, Vitral Sul), identificou-se que cada PDF
tem uma combinação diferente de (texto disponível?) × (vetor ou raster?).
**Decisão:** o Pipeline nunca depende exclusivamente do formato PDF. PDF-com-texto é
apenas um Provider entre vários possíveis (futuros: OCR, DXF, DWG, API de
fabricante, cadastro manual).
**Evidência:** 4 casos reais e distintos de extração documentados: (1) Centenário/
Tamboré — vetor + texto real; (2) Euroshow — vetor + texto real, com defeito pontual
de dado (dígito corrompido "0" → "O"); (3) Alcoa (seção Suprema testada) — vetor sem
texto extraível (fonte convertida em contorno); (4) Vitral Sul — desenho como
imagem raster embutida.
**Consequências:** Providers novos (OCR, DXF, DWG, API de fabricante) podem ser
adicionados sem alterar o Core Engine; o Pipeline nunca pode depender
exclusivamente de PDF; OCR passa a ser apenas mais um Provider, não uma mudança
estrutural.
**Afeta:** Volumes 2, 5, 6 | Entidades: Provider, Pipeline de Aquisição

---

### ADR-004 — FamíliaMercado representa linguagem do mercado

**Estado:** Validado (confirmado com evidência cruzada real — SU-019 entre Alcoa e Vitral Sul)

**Contexto:** análise de domínio trazida pelo Bruno — profissionais do setor pedem
"SU" ou "LG" (nomenclatura originada pela Alcoa), nunca os códigos internos de cada
fabricante (TMS, MG25, Nobile 2.5), o mesmo fenômeno de genericização de marca visto
em "Blindex" para vidro temperado.
**Decisão:** o domínio inclui uma entidade FamíliaMercado (nome canônico, origem
histórica, bitola, aliases por fabricante), representando exclusivamente o
vocabulário usado pelo mercado — não conhece geometria nem implica
intercambiabilidade técnica.
**Evidência:** confirmação cruzada real — código SU-019 aparece com peso muito
próximo (1,770 kg/m Alcoa vs. 1,678 kg/m Vitral Sul) em dois fabricantes sem relação
societária conhecida; o próprio catálogo da Vitral Sul declara "Linha Nobile 2.5 -
Suprema", reconhecendo a equivalência comercial.
**Consequências:** buscas/relatórios podem ser feitos pelo nome que o mercado usa
("Suprema"), não pelo código interno de cada fabricante; a existência de uma
FamíliaMercado nunca autoriza, por si só, tratar dois perfis como intercambiáveis
tecnicamente (ver ADR-005).
**Afeta:** Volume 3, 8 | Entidades: FamíliaMercado, Perfil

---

### ADR-005 — GeometriaPadrao é ativo de engenharia compartilhado

**Estado:** Validado (prova de conceito implementada; ainda não em escala de produção)

**Contexto:** decorrência direta do ADR-004 — se FamíliaMercado agrupa perfis
comercialmente equivalentes de fabricantes diferentes, redesenhar a mesma geometria
para cada fabricante é retrabalho evitável.
**Decisão:** GeometriaPadrao é uma entidade própria (contorno vetorial, versão,
status de homologação), referenciada por múltiplos Perfis através da entidade de
associação auditável PerfilGeometria (responsável pela homologação, método de
validação, nível de confiança). A associação nunca é inferida automaticamente pela
FamíliaMercado — é sempre decisão de curadoria humana caso a caso.
**Evidência:** prova de conceito implementada e testada — `ALCOA-SU-019` e
`VITRALSUL-SU-019`, dois Perfis de fabricantes distintos, resolvidos através de
`PerfilGeometria` para a mesma `GeometriaPadrao` (GEO-SU-019), gerando imagens com
geometria idêntica (confirmado por contagem de pixel).
**Consequências:** a Curadoria Geométrica de um código de mercado acontece uma
única vez, não uma vez por fabricante; toda associação Perfil↔GeometriaPadrao é
auditável (quem homologou, com que método, com que confiança) — nunca inferida
automaticamente.
**Afeta:** Volumes 3, 6, 8 | Entidades: GeometriaPadrao, Perfil, PerfilGeometria
**Nota explícita:** PerfilGeometria não é cache, não é otimização de performance,
não é tabela auxiliar descartável — é entidade de auditoria de primeira classe.
Removê-la eliminaria a rastreabilidade de quem homologou o compartilhamento de
geometria entre fabricantes, comprometendo o ADR-005 por completo.

---

### ADR-006 — Pipeline de Aquisição é extrator de conhecimento técnico, não apenas de perfis

**Estado:** Validado (seção Usinagens do Euroshow confirma o princípio; ainda sem consumidor formal desses dados)

**Contexto:** o catálogo Euroshow revelou uma seção ("Usinagens") documentando
explicitamente conexões perfil↔ferragem por tipologia — dado de Regra/Compatibilidade
que se assumia, com base só no catálogo Centenário, que precisaria ser sempre
construído manualmente.
**Decisão:** ampliar a visão do Pipeline — perfis são apenas um dos produtos
gerados; a arquitetura de saída também contempla ferragens, compatibilidades,
regras, tipologias, usinagens, documentação técnica e metadados. Sem alterar o Core
Engine, apenas ampliando o que o Pipeline procura extrair.
**Evidência:** seção "Usinagens" do catálogo Euroshow, documentando pares como
"CONEXÃO ES-054 - PERFIL ES-001".
**Consequências:** todo novo catálogo importado deve ser varrido também em busca de
seções de conexão/montagem, não só de fichas de perfil individuais; o Pipeline passa
a ter saída multi-tipo (perfis, ferragens, compatibilidades, regras...), mesmo que
alguns tipos ainda não tenham consumidor definido (ver ADR-007).
**Afeta:** Volumes 6, 8 | Entidades: Pipeline de Aquisição

---

### ADR-007 — Todo conhecimento estrutural é preservado, mesmo sem modelo ainda

**Estado:** Estável

**Contexto:** decorrência do ADR-006 — nem todo conhecimento encontrado num catálogo
tem, ainda, uma entidade de domínio pronta para representá-lo.
**Decisão:** todo conhecimento estrutural identificado pelo Pipeline deve ser
capturado e preservado em sua forma original (bruto), mesmo que ainda não exista um
modelo de domínio para representá-lo formalmente. Primeiro preservar, depois
compreender, depois modelar — sem obrigar estruturação imediata.
**Evidência:** princípio aplicado retroativamente às seções "Usinagens" (Euroshow) e
ao teor de conexões — capturadas como texto bruto, sem forçar schema antes de haver
exemplos suficientes de fabricantes diferentes documentando esse tipo de informação.
**Consequências:** o Pipeline nunca descarta informação estrutural só por falta de
entidade pronta; schemas novos (ex: Compatibilidade, Regra de Montagem) só são
formalizados depois de exemplos reais suficientes — evita generalização prematura.
**Afeta:** Volumes 6, 8 | Entidades: nenhuma ainda formalizada (por decisão)

---

## Índice de referência rápida

| ADR | Título curto |
|---|---|
| 001 | Geometria como fonte única de verdade |
| 002 | Renderer isolado de regras de engenharia |
| 003 | Provider abstrai origem dos dados |
| 004 | FamíliaMercado = linguagem de mercado |
| 005 | GeometriaPadrao = ativo compartilhado |
| 006 | Pipeline = extrator de conhecimento técnico |
| 007 | Preservar antes de modelar |
