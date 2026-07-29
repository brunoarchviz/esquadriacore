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

## Pendência 2 — SU-102

Forma inteiramente caracterizada; falta só a escala.

```
três catálogos independentes  : aspecto 1,1366 / 1,1374 / 1,1375
dispersão                     : 0,08 %
topologia                     : 0 vazios em todos
orientação                    : idêntica, rotação zero
escala relativa entre fontes  : 1,00005
gate funcional local          : aprovado em todas as regiões com material
```

**Nenhum dos quatro catálogos investigados cota o envelope externo.** As cotas 10, 11 e 12
são segmentos internos — a 10 nem começa no SU-102, parte do perfil de referência SU-053
desenhado no mesmo card.

Protocolo pronto em `curadoria/insumos/protocolo_medicao_fisica_su102.md`: paquímetro de
0,01 mm, largura e altura externas máximas, três leituras de cada, mais de uma seção,
evidência fotográfica. Critério de aceitação: erro de aspecto ≤ 0,75 % contra 1,137.

Uma medida sozinha bastaria matematicamente — mas não para homologação, porque não teria
como ser conferida.

---

## Suíte

```
pytest -q  ->  223 passed in 320,89s (0:05:20)
EXIT_CODE=0
```

Zero falhas, zero pulados. Execução posterior aos commits C e D.

---

## O que não reabrir

SU-001, SU-002, SU-003, SU-039 e SU-053 estão fechados. As duas frentes vivas são
**a arbitragem da zona do SU-041** e **a medição física do SU-102**.
