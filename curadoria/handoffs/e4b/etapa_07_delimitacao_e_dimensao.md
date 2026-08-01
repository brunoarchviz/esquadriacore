# EsquadriaCore — E.4B: fontes separadas por papel, registro isotrópico e gate de equivalência

Documento autocontido. Sexta etapa.

---

## 0. Estado do lote 1

| perfil | estado |
|---|---|
| SU-039 | concluído · 52,60 × 25,00 mm · reprodutível |
| SU-024 | concluído · 106,00 × 39,00 mm · reprodutível |
| SU-009 | reenquadrado · geometria intacta |
| **SU-053** | fontes separadas por papel · **bloqueado: ROIs dos motivos nunca foram medidas** |
| **SU-102** | congruente com TMS-102 · **bloqueado por dimensão** |

---

## 1. SU-053 — as quatro fontes, separadas por papel

Persistido no config:

| papel | fabricante | código | página |
|---|---|---|---|
| **geométrica primária** | Centenário | TMS-053 | 222 |
| **dimensional primária** | Centenário | TMS-053 | 222 |
| **semântica dos motivos** | Alcoa | SU-053 | 187 |
| **evidência de contaminação** | Alcoa | SU-053 | 187 |

Não é conflito de fontes — é divisão explícita de papéis. Trocar a fonte geométrica não
apaga o ground truth dos cinco motivos, que continua confirmado no card Alcoa.

Registrado também que o card Centenário **não usa separação por espessura**: ele não tem
perfil de referência sobreposto, e a abertura morfológica mataria o perfil deixando só a
pílula do rótulo — 639 × 331 px com 14 falsos vazios, que são as letras.

---

## 2. Bloqueio real: as ROIs dos cinco motivos nunca foram medidas

O item 4 pedia transferir as regiões dos motivos de Alcoa para TMS-053 por transformação
de similaridade. **Não há o que transferir:**

```
#1 GAB-ESCOVINHA-SU-01              zona_protegida = null   roi_status = pendente_delimitacao
#1 MOTIVO-ENCAIXE-BAGUETE-INTERNO   zona_protegida = null   roi_status = pendente_delimitacao
#1 GAB-OLHAL-01                     zona_protegida = null   roi_status = pendente_delimitacao
#1 MOTIVO-ENCAIXE-BAGUETE-EXTERNO   zona_protegida = null   roi_status = pendente_delimitacao
#2 GAB-ESCOVINHA-SU-01              zona_protegida = null   roi_status = pendente_delimitacao
```

As cinco classes estão confirmadas; as **coordenadas** nunca foram delimitadas. A
máquina de transferência está pronta (`registro_isotropico.transferir_zona`), mas a
entrada não existe.

Isso é entrada ausente, não falha de método. Sem as cinco ROIs de origem não há
transferência, não há gate local dos motivos, e o SU-053 não pode ser concluído.

---

## 3. Registro isotrópico — módulo novo

`curadoria/aquisicao/registro_isotropico.py`

Ajusta uma transformação de **similaridade**: uma escala, uma rotação, translação.
Reflexão é rejeitada explicitamente (checagem do determinante). Não há escala
anisotrópica, cisalhamento nem deformação local — por construção, não por convenção.

Método: ICP com Procrustes isotrópico a cada iteração, sobre os pontos de contorno
completos, com busca de vizinho por FLANN.

Existe porque **bounding box não serve para calibrar**: ele é decidido por quatro pixels
extremos e é sensível a espessura de traço, antialiasing, caco isolado e corte pequeno.
O registro usa o contorno inteiro.

Validação sintética (regressão): forma escalada 1,35 × e girada 12° é recuperada com
escala 1,3527, rotação 11,99°, erro médio 0,40 px, IoU 0,9948. E uma forma esticada só
num eixo **não** consegue erro baixo — a deformação anisotrópica não é absorvível.

---

## 4. SU-102 — o registro isotrópico responde a pergunta, e ela é "não"

O item 9 estava certo: os 1,34 % anteriores vinham de bounding box. Refeito por registro
do contorno completo:

```
escala   = 23,7978 px/mm   (única)
rotação  = 0,006 graus     (zero)
erro médio = 2,61 px = 0,109 mm
erro p95   = 6,71 px
erro máx   = 10,46 px
```

**Existe uma escala única e a rotação é zero.** O bbox não era o problema, e não há giro
entre as fontes.

Mas a escala única não reproduz as duas cotas:

| eixo | px | mm pela escala única | nominal | erro |
|---|---|---|---|---|
| largura | 529 | 22,229 | 22,2 | **0,13 %** |
| altura | 1199 | 50,383 | 51,0 | **1,21 %** |

A largura fecha; a altura não. A referência fina do card Alcoa é proporcionalmente mais
baixa que 22,2 × 51.

Dado revelador: **o próprio TMS-053 erra 0,67 %** contra sua própria cota (1214 px pela
escala da largura → 50,659 mm, não 51,0). Nenhum desenho reproduz exatamente 22,2 × 51 —
o TMS é o mais próximo, e passa raspando no gate.

Gate mantido em 0,75 %. Não ampliei, não calibrei X e Y separadamente, não gravei
dimensão aproximada.

Painel: `painel_registro_isotropico_su102.png`

---

## 5. SU-102 × TMS-102 — os dois catálogos publicam o mesmo desenho

Aquisição **independente** do TMS-102 no card Centenário (p.235), com separação de
camadas: 414 × 364 px, 0 vazios, não toca borda.

Registro isotrópico contra o SU-102 do Alcoa:

```
escala     = 1,000054      ← 1:1
rotação    = -0,030 graus  ← zero
erro médio = 0,91 px
erro p95   = 1,26 px
erro máx   = 2,48 px
IoU        = 0,9224
```

Escala 1,00005 e rotação zero significam que **os dois catálogos publicam o mesmo desenho
na mesma escala**. O erro médio de 0,91 px sobre um objeto de ~400 px é 0,23 %.

### Relatório de equivalência

```yaml
equivalencia_global:          PASSA      # aspecto 0,07% · IoU 0,9224 · rotação 0°
equivalencia_topologica:      PASSA      # 0 vazios nos dois
equivalencia_dimensional:     PENDENTE   # nenhuma fonte cota o bounding box
equivalencia_funcional_local: PENDENTE   # falta o gate por região
decisao: CONGRUENCIA_GLOBAL_SEM_EQUIVALENCIA_GEOMETRICA_COMPLETA
```

O SU-102 permanece `BLOQUEADO_POR_DIMENSAO`, com `largura_mm` e `altura_mm` nulos.

Painel: `painel_gate_local_su102_tms102.png`

---

## 6. Testes acrescentados

| teste | invariante |
|---|---|
| `test_su053_fontes_separadas_por_papel` | os quatro papéis declarados; motivos preservados |
| `test_tms053_nao_usa_separacao_por_espessura` | o card Centenário exige binarização simples |
| `test_registro_isotropico_recupera_similaridade` | escala e rotação recuperadas em sintético |
| `test_registro_isotropico_nao_deforma_anisotropicamente` | deformação num eixo **não** é absorvida |
| `test_calibracao_isotropica_do_su102_reprova` | largura fecha, altura não — e é isso que bloqueia |
| `test_su102_congruente_mas_sem_equivalencia_completa` | IoU e aspecto não bastam |
| `test_gate_de_075_nao_foi_ampliado` | a tolerância segue 0,0075 no código |
| `test_curadoria_nao_grava_em_dados_oficiais` | `dados/`, `domain/`, `contrato/`, `docs/` barrados |

### Suíte

```
primeira execução : 194 passed, 1 failed
depois da correção: 195 passed in 209,39s
```

A falha foi minha e o teste fez o trabalho dele: renomeei `fonte_dimensional` para
`fonte_dimensional_primaria` ao reorganizar o config nesta rodada e deixei
`test_su053_altura_vem_da_fonte_dimensional_nao_do_bbox` lendo a chave antiga
(`KeyError`). Não era regressão de comportamento — era inconsistência introduzida por
mim na mesma rodada, apanhada pela suíte.

---

## 7. O que não executei, e por quê

| item da ordem | situação |
|---|---|
| 2 — transferir as cinco ROIs | **entrada ausente**: `zona_protegida = null` nos cinco |
| 3 — validar os motivos localmente | depende do item 2 |
| 4 — reprodutibilidade do SU-053 | depende dos motivos validados |
| 11 — segmentos das cotas 11 e 12 | depende da calibração passar, e ela reprova |

O gate funcional local por região (ganchos, pé, encaixes, terminações) do item 11 não foi
executado: com a dimensão pendente, ele não muda a decisão — a equivalência completa já
está barrada pela via dimensional.

---

## 8. Arquivos desta rodada

Modificados:

```
curadoria/aquisicao/configs/e4b_suprema.json   fontes por papel, calibração, equivalência
tests/test_aquisicao_contornos.py              +8 regressões
```

Novos:

```
curadoria/aquisicao/registro_isotropico.py     módulo de similaridade
curadoria/composicao/painel_registro_isotropico_su102.png
curadoria/composicao/painel_gate_local_su102_tms102.png
```

Caminhos protegidos intactos. SU-039, SU-024 e SU-009 não reabertos. SU-040 e SU-041 não
tocados. SU-001/002/003 não iniciados. Nenhum commit, push ou tag.

---

## 9. O que precisa de decisão

### 9.1 Delimitar as cinco ROIs do SU-053

É o bloqueio de caminho crítico. Sem as coordenadas no card Alcoa, nada do SU-053 avança.
Posso gerar um painel ampliado numerado para você marcar cada uma, se ajudar.

### 9.2 SU-102 — nenhuma fonte cota o bounding box

Os dois catálogos publicam o mesmo desenho, mas nenhum cota a dimensão externa. As cotas
11 e 12 são segmentos internos em ambos. Ou aparece um terceiro catálogo que cote o
envelope, ou a dimensão do SU-102 vem de medição física, não de catálogo.

### 9.3 Nenhum desenho reproduz 22,2 × 51 exatamente

O TMS-053 erra 0,67 % contra sua própria cota; o Alcoa erra 1,2–1,5 %. Isso sugere que a
tolerância de 0,75 % está no limite do que desenho de catálogo entrega. Vale decidir se
0,75 % é a régua certa para fonte raster de catálogo, ou se o gate deveria distinguir
"erro de desenho" de "erro de aquisição".
