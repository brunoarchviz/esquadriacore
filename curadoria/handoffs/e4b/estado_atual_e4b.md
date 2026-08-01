# EsquadriaCore — estado atual do E.4B

Resumo curto. Os documentos por etapa estão em `curadoria/handoffs/e4b/etapa_*.md`.

---

## Commits locais

```
afdef66  docs(curadoria): registra evidências do lote 2 E.4B
10419a3  feat(curadoria): conclui aquisição do lote 2 E.4B
095ba09  docs(curadoria): registra evidências e handoffs do lote 1 E.4B
258509d  feat(curadoria): consolida aquisição e candidatos do lote 1 E.4B
```

Branch `sprint-e4-composicao-correr-suprema`, **sem upstream — nada foi enviado**.

---

## Os oito perfis da janela

| perfil | dimensões | estado |
|---|---|---|
| SU-001 | 71,00 × 33,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-002 | 71,00 × 47,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-003 | 71,00 × 26,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-039 | 52,60 × 25,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-053 | 22,20 × 51,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-040 | 42,40 × 30,70 mm | `CANDIDATO_PREVIAMENTE_APROVADO` |
| SU-041 | — | **`BLOQUEADO_POR_ZONA_PENDENTE`** |
| SU-102 | — | `CANDIDATO_ADIMENSIONAL_APROVADO` · dimensional **aguardando medição física** |

**5 de 8 completamente fechados.** Um praticamente fechado (SU-040), um com pendência
localizada (SU-041), um adimensional (SU-102).

Nenhum foi promovido a geometria oficial. Não existe `GEO-*` em `dados/`.

### Fora da contagem

`SU-009` e `SU-024` são trabalhos auxiliares. O SU-024 provou a família de contaminação
por apêndice com tirante fino; o SU-009 expôs o gate RECORTE. Importantes, mas não fazem
parte da composição da janela.

---

## Pendência 1 — SU-041

O perfil tem **dois motivos confirmados**:

| motivo | zona | atribuição |
|---|---|---|
| `GAB-ESCOVINHA-SU-01` | `null` | `pendente_arbitragem` |
| `GAB-MA-DIAG-ESC-01` | `[23.0, 28.0, 38.5, 33.0]` | **`pendente`** |

O problema exato: **existe uma zona medida, mas não foi decidido a qual dos dois motivos
ela pertence.** Ela está anexada ao `GAB-MA-DIAG-ESC-01`, com a atribuição declarada
pendente — pode ser dele ou da escovinha.

A escovinha continua sem ROI porque o bolso que havia sido medido para ela era, na
verdade, um olhal (correção de 25/07/2026 que invalidou aquelas medições).

Isso é o padrão já estabelecido no projeto: motivo é ocorrência local, e quando um perfil
tem dois ou mais, a atribuição de cada bolso medido exige arbitragem — o detector
genérico não decide.

**Como resolver:** o mesmo caminho que fechou o SU-053. Gerar painel numerado com os
candidatos de bolso do SU-041, e mapear `M → C` por arbitragem visual. A máquina de
transferência e validação já existe e está testada.

O validador de schema reporta essa incoerência a cada execução, e ela está registrada em
`PENDENCIAS_CONHECIDAS` nos testes — com um segundo teste que falha se ela sumir sem
alguém atualizar a lista.

---

## Pendência 2 — SU-102 — **RESOLVIDA em 2026-08-01**

Forma já estava inteiramente caracterizada; faltava só a escala. **Fechada por
medição física.**

```
três catálogos independentes  : aspecto 1,1366 / 1,1374 / 1,1375
dispersão                     : 0,08 %
topologia                     : 0 vazios em todos
escala relativa entre fontes  : 1,00005  (registro ISOTRÓPICO)
gate funcional local          : aprovado em todas as regiões com material
```

**Nenhum dos quatro catálogos cota o envelope externo** — isso continua verdade.
A cota veio da medição física do Bruno, e os catálogos entraram como validação
de forma e aspecto.

```
leitura física    : 16,9 x 15,0 mm   (4 repetições eixo maior, 3 eixo menor)
dimensão nominal  : 17,0 x 15,0 mm   (arredondamento declarado, sem impacto funcional)

gate físico bruto : aspecto 1,1267, erro até 0,952 %  ->  REPROVA
gate nominal      : aspecto 1,1333, erro até 0,366 %  ->  PASSA
decisão           : arbitragem de domínio com nominalização
                    (NÃO é aprovação automática pelo gate)
```

A nominalização é **anisotrópica** e declarada (`fator_x 1,005917 ≠ fator_y 1,0`).
Ela não é usada no registro entre catálogos, que segue isotrópico.

Artefatos de curadoria em `curadoria/contornos/SU-102/` — seis, reprodutíveis,
F1 = 1,0, 0 vazios. `promocao_oficial: ainda_nao_autorizada`, nenhum `GEO-SU-102`.

Detalhes em `etapa_12_fechamento_dimensional_su102.md`, incluindo duas correções
metodológicas minhas registradas ali (leitura errada das garras do paquímetro e
guard de promoção em escopo errado no driver).

**Equivalência com o TMS-102 continua pendente**: medir o SU-102 não mede o
perfil do outro catálogo.

---

## Microlote E.4B

```yaml
fechados_na_curadoria: 8
aguardando_evidencia_externa: 0
perfis: [SU-001, SU-002, SU-003, SU-039, SU-040, SU-041, SU-053, SU-102]
```

Curadoria concluída. **Não** é promoção oficial, merge em `main`, tag ou release.

---

## Suíte

```
pytest -q  ->  223 passed in 320,89s (0:05:20)
EXIT_CODE=0
```

Zero falhas, zero pulados. Execução posterior aos commits C e D.

---

## O que não reabrir

SU-001, SU-002, SU-003, SU-039, SU-053 e agora **SU-102** estão fechados na
curadoria. A frente viva restante é **a arbitragem da zona do SU-041**.
