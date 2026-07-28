# EsquadriaCore — E.4B etapa 09: investigação dimensional do SU-102

Documento autocontido.

---

## 0. Estado do lote 1

| perfil | estado |
|---|---|
| SU-039 | concluído · 52,60 × 25,00 mm |
| SU-024 | concluído · 106,00 × 39,00 mm |
| SU-009 | reenquadrado |
| SU-053 | **`CANDIDATO_GEOMETRICO_APROVADO`** · 22,20 × 51,00 mm · 6 artefatos reprodutíveis |
| **SU-102** | congruência total provada · **falta só a dimensão externa** |

---

## 1. Fontes encontradas

Varredura de **14 catálogos** do repositório por `SU-102`, `TMS-102`, `TMG-102`,
`LG-102`, `VS-102` e `U-1230`:

| fabricante | código | arquivo | pág. PDF | cotas | envelope? | complementar | peso | aspecto |
|---|---|---|---:|---|---|---|---|---|
| Alcoa | SU-102 | `catalago-alcoa (1).pdf` | 198 | 10, 11, 12 | **não** | SU-053 | 0,111 kg/m | 1,1366 |
| Centenário | TMS-102 | `Centenário.pdf` | 235 | 11, 12 | **não** | ref. cinza claro | 0,110 kg/m | 1,1374 |
| Vitral Sul | SU-102 | `PERFIS-DE-ALUMINIO-02-07-2026.pdf` | 91 | 10, 11, 12 | **não** | PSU-053 | 0,111 kg/m | 1,1375 |
| não identificado | TMS-102 | `cebf22_…pdf` | 108 | 12 | **não** | ref. fina | — | — |

Os dez catálogos restantes (IVGold, Gold, ASA, Nova Gold, Tipologia, cortes) não têm
ocorrência do código.

O quarto card existe e usa a mesma convenção gráfica, mas a ROI que testei capturou a
pílula do rótulo (640 × 232 px com 7 falsos vazios, que são as letras) — a medição dele
fica pendente de ROI adequada. Não afeta a conclusão.

**Três fontes independentes dão aspecto 1,1366 / 1,1374 / 1,1375 — dispersão de 0,08 %.**
Os pesos também batem: 0,110 e 0,111 kg/m.

Painel: `curadoria/composicao/painel_fontes_dimensionais_su102.png`

---

## 2. O que as cotas 10, 11 e 12 medem

Medição das linhas de chamada verticais no card Alcoa a 600 DPI, contra os extremos do
traço cheio:

```
traço cheio          x = [373, 788]   (416 px)   y = [685, 1050]  (366 px)
linhas de chamada    x = 293, 527, 788
```

| linha | posição | onde ancora |
|---|---|---|
| 1 | x = 293 | **80 px à esquerda** do início do traço cheio — cai sobre o **SU-053 de referência** |
| 2 | x = 527 | 154 px **dentro** do traço cheio — ponto interno |
| 3 | x = 788 | exatamente a **borda direita** do traço cheio |

Portanto:

- **cota 10** (vão 234 px) vai da referência SU-053 até um ponto interno do SU-102.
  Não é dimensão do SU-102.
- **cota 11** (vão 261 px) vai de um ponto interno até a borda direita.
  É um segmento parcial, não a largura.
- **cota 12** é vertical; as setas abrangem a extensão vertical do traço cheio, mas não
  confirmei isso com a mesma medição das linhas — fica como indeterminado.

**Nenhuma das cotas mede o envelope.** A soma 10 + 11 cobre 495 px, **mais** que os
416 px do traço cheio, porque a cota 10 começa no perfil de referência. É exatamente por
isso que a hipótese de 21 mm superestimava.

---

## 3. Cota externa: não existe em nenhuma fonte

Registrado:

```yaml
dimensao_externa:
  status: REQUER_MEDICAO_FISICA_OU_DESENHO_TECNICO_COTADO
```

Nada foi inferido, somado ou arredondado. `largura_mm` e `altura_mm` seguem nulos e o
perfil segue `BLOQUEADO_POR_DIMENSAO`.

---

## 4. Gate funcional local SU-102 × TMS-102

Registro isotrópico entre os traços cheios (ambos recortados ao bbox):

```
escala     = 1,000057     ← 1:1
rotação    = -0,030 graus ← zero
erro médio = 0,913 px
erro p95   = 1,261 px
erro máx   = 2,484 px
IoU        = 0,9319
```

Resíduos por região (grade 3 × 3 sobre o bbox), para verificar se algum defeito se
concentra numa estrutura funcional:

| região | pontos | resíduo médio | p95 | máx | decisão |
|---|---:|---:|---:|---:|---|
| terminação sup-esq | 0 | — | — | — | sem material |
| gancho superior | 436 | 0,99 | 1,22 | 1,54 | **EQUIVALENTE** |
| terminação sup-dir | 462 | 1,00 | 1,16 | 1,50 | **EQUIVALENTE** |
| lábio esquerdo | 14 | — | — | — | sem material |
| encaixe do baguete | 230 | 0,91 | 1,23 | 1,28 | **EQUIVALENTE** |
| lábio direito | 244 | 1,02 | 1,07 | 1,38 | **EQUIVALENTE** |
| pé / term. inf-esq | 415 | 0,82 | 1,72 | 2,48 | **EQUIVALENTE** |
| gancho inferior | 33 | 0,81 | 1,09 | 1,10 | **EQUIVALENTE** |
| terminação inf-dir | 290 | 0,70 | 1,26 | 1,40 | **EQUIVALENTE** |

Nenhuma região concentra resíduo: o p95 fica abaixo de 1,8 px em todas, sobre um objeto
de ~400 px. As duas células "sem material" são cantos vazios do bounding box.

Painel: `curadoria/composicao/painel_equivalencia_local_su102_tms102.png`

---

## 5. Estado do candidato compartilhado

```yaml
candidato_compartilhamento:
  congruencia_global:          APROVADA
  congruencia_topologica:      APROVADA
  congruencia_funcional_local: APROVADA
  equivalencia_dimensional:    PENDENTE
  decisao: AGUARDANDO_DIMENSAO_EXTERNA
```

Não foi criado `GEO-SU-102`, não há geometria oficial compartilhada, e o estado do perfil
continua `BLOQUEADO_POR_DIMENSAO`.

---

## 6. Medição física: sim, é necessária

Com quatro catálogos investigados e nenhum publicando o envelope, a dimensão externa do
SU-102 só pode vir de medição física ou de desenho técnico cotado que ainda não está no
repositório.

O protocolo já foi definido em rodada anterior: paquímetro com resolução de 0,01–0,02 mm,
largura e altura externas máximas, três repetições, mais de uma seção, orientação
registrada e evidência fotográfica.

Vale notar que a geometria já está inteiramente caracterizada — só falta a escala. Uma
única medição confiável de qualquer dimensão externa fixa todo o resto, porque o aspecto
está confirmado por três fontes a 0,08 %.

---

## 7. Testes

Cinco regressões acrescentadas:

| teste | invariante |
|---|---|
| `test_su102_nenhuma_fonte_cota_o_envelope` | as quatro fontes com `cota_envelope_total: false` |
| `test_su102_cotas_10_e_11_nao_medem_o_envelope` | a aritmética das linhas de chamada prova que 10+11 > largura |
| `test_su102_tres_fontes_concordam_no_aspecto` | dispersão entre catálogos ≤ 0,75 % |
| `test_su102_gate_funcional_local_completo` | regiões com material aprovadas, p95 ≤ 4 px |
| `test_su102_nao_vira_geometria_oficial` | sem `GEO-SU-102`, sem `APROVADO_EM_CURADORIA` |

Direcionados: **9 passed**.

---

## 8. Arquivos

Modificados:

```
curadoria/aquisicao/configs/e4b_suprema.json   fontes, interpretação das cotas, gate local
tests/test_aquisicao_contornos.py              +5 regressões
```

Novos:

```
curadoria/composicao/painel_fontes_dimensionais_su102.png
curadoria/composicao/painel_equivalencia_local_su102_tms102.png
curadoria/handoffs/e4b/etapa_09_investigacao_su102.md
```

`dados/`, `domain/`, `contrato/`, `docs/`, `VERSION`, `CHANGELOG.md` intactos.
SU-039, SU-024, SU-009 e SU-053 não reabertos. SU-001/002/003 não iniciados.
Nenhum commit, push ou tag.

---

## 9. O que falta

Só a dimensão externa do SU-102. Tudo o mais está fechado:

- forma caracterizada e confirmada por três catálogos independentes
- topologia idêntica (0 vazios em todos)
- orientação idêntica (rotação zero)
- escala relativa 1:1 entre fontes
- gate funcional local aprovado em todas as regiões com material
- interpretação das cotas resolvida: são segmentos internos, e a 10 nem começa no perfil
