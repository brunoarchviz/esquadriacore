# EsquadriaCore — estado atual do E.4B

Resumo curto do **estado presente**. O histórico por etapa está em
`curadoria/handoffs/e4b/etapa_*.md`.

---

## Branch e PR

```yaml
branch:   sprint-e4-composicao-correr-suprema
upstream: origin/sprint-e4-composicao-correr-suprema
pr:       3
```

Commits que fecharam a etapa 12:

```
d6a6009  feat(curadoria): conclui escala dimensional do SU-102
f3a2924  docs(curadoria): registra fechamento dimensional do E.4B
```

---

## Microlote

```yaml
microlote:
  fechados_na_curadoria: 8
  aguardando_evidencia_externa: 0
  promocao_oficial_realizada: false
```

**8 de 8 fechados na curadoria.** Nenhum perfil promovido oficialmente —
nenhum `GEO-*` existe em `dados/`.

---

## Os oito perfis da janela

| perfil | dimensões | estado |
|---|---|---|
| SU-001 | 71,00 × 33,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-002 | 71,00 × 47,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-003 | 71,00 × 26,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-039 | 52,60 × 25,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-040 | 42,40 × 30,70 mm | `CANDIDATO_PREVIAMENTE_APROVADO` |
| SU-041 | 42,40 × 33,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-053 | 22,20 × 51,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |
| SU-102 | 17,00 × 15,00 mm | `CANDIDATO_GEOMETRICO_APROVADO` |

### Fora da contagem

`SU-009` e `SU-024` são trabalhos auxiliares. O SU-024 provou a família de
contaminação por apêndice com tirante fino; o SU-009 expôs o gate RECORTE.
Importantes, mas não fazem parte da composição da janela.

---

## SU-041

```yaml
SU-041:
  estado: CANDIDATO_GEOMETRICO_APROVADO
  pendencia_zona: resolvida
```

A arbitragem visual das zonas foi concluída — ver
`etapa_11_arbitragem_su041.md`.

---

## SU-102

Único perfil do microlote cuja cota não vem de catálogo: **nenhuma das quatro
fontes investigadas cota o envelope externo**. A dimensão veio de medição
física repetida, e os catálogos entraram como validação de forma e aspecto.

```yaml
SU-102:
  dimensao_fisica_mm:  [16.9, 15.0]
  dimensao_nominal_mm: [17.0, 15.0]
  estado_geometrico:   CANDIDATO_GEOMETRICO_APROVADO
  estado_dimensional:  DIMENSAO_NOMINAL_APROVADA_POR_ARBITRAGEM_DE_DOMINIO
  promocao_oficial:    ainda_nao_autorizada
```

Os dois gates ficam registrados separadamente — um não substitui o outro:

| | aspecto | erro máx | limite | resultado |
|---|---|---|---|---|
| físico bruto 16,9 × 15,0 | 1,126667 | 0,952% | 0,75% | **REPROVADO** |
| nominal 17,0 × 15,0 | 1,133333 | 0,366% | 0,75% | **APROVADO** |

A aprovação vem da arbitragem de domínio sobre a nominalização, não do gate.
O limite de 0,75% não foi alterado. A nominalização é **anisotrópica** e
declarada (`fator_x` 1,005917 ≠ `fator_y` 1,0); ela não é usada no registro
entre catálogos, que segue isotrópico.

Artefatos em `curadoria/contornos/SU-102/` — seis, reprodutíveis, F1 = 1,0,
0 vazios.

---

## TMS-102 — a pendência que resta

```yaml
TMS-102:
  equivalencia_dimensional_com_SU102: PENDENTE
  decisao: AGUARDANDO_DIMENSAO_EXTERNA_DO_TMS102
```

Duas afirmações distintas, que não devem ser confundidas:

```text
SU-102 fechado dimensionalmente na curadoria   = SIM
SU-102 e TMS-102 dimensionalmente equivalentes = AINDA NÃO PROVADO
```

Medir fisicamente o SU-102 não mede o perfil do outro catálogo. A congruência
global, topológica e funcional local está aprovada; falta o envelope externo do
TMS-102, obtido de forma independente.

---

## Suíte

```
184 testes direcionados verdes
246 testes completos verdes — execução 1
246 testes completos verdes — execução 2
EXIT_CODE=0 nas três
```

---

## O que não reabrir

Os oito perfis estão fechados na curadoria. A frente restante é **a
equivalência dimensional entre SU-102 e TMS-102**, que depende de medir o
TMS-102 — não de remedir o SU-102.

Este estado conclui a curadoria. **Não** é promoção oficial, merge em `main`,
tag ou release.
