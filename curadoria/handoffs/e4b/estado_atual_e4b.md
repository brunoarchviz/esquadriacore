# EsquadriaCore — estado atual do E.4B

Resumo curto do **estado durável** da curadoria do E.4B. Não registra branch,
PR nem hashes de commit — esses são transitórios e ficariam obsoletos logo após
cada merge. O histórico por etapa, com os commits, está em
`curadoria/handoffs/e4b/etapa_*.md`.

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

## SU-102 × TMS-102 — mesmo perfil físico

O especialista de domínio (Bruno) confirmou em 2026-08-01 que **SU-102 e
TMS-102 são o mesmo perfil físico** — mesma extrusão, códigos diferentes entre
catálogos. Não é semelhança geométrica nem compatibilidade de família de
mercado (ADR-004): é identidade de produto.

```yaml
SU-102_TMS-102:
  identidade_de_perfil:    CONFIRMADA
  equivalencia_geometrica: APROVADA
  equivalencia_topologica: APROVADA
  equivalencia_funcional:  APROVADA
  equivalencia_dimensional: APROVADA
  dimensao_nominal_mm: [17.0, 15.0]
  fundamento_dimensional: medicao_fisica_do_mesmo_perfil
```

A procedência da cota fica explícita e não deve ser abreviada:

```text
medição física realizada no perfil SU-102
identidade SU-102 = TMS-102 confirmada pelo especialista de domínio
dimensão transferida por identidade de produto
```

O TMS-102 **não** foi medido separadamente, e o config registra isso
(`tms102_medido_separadamente: false`). A identidade é coerente com a evidência
já registrada: o registro isotrópico entre as duas fontes dá escala 1,000054 e
rotação −0,03°, isto é, o mesmo desenho na mesma escala.

---

## Suíte

```
204 testes direcionados verdes
266 testes completos verdes
EXIT_CODE=0 nas duas execuções
```

---

## O que não reabrir

Os oito perfis estão fechados na curadoria e não há pendência dimensional entre
SU-102 e TMS-102.

Este estado conclui a curadoria. **Não** é promoção oficial dos candidatos para
`dados/` — essa continua sendo uma etapa futura e separada.
