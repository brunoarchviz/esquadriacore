# EsquadriaCore — E.4B etapa 11: arbitragem das zonas do SU-041

Documento autocontido.

---

## 1. O problema original

O SU-041 tem **dois motivos confirmados** — a classe de cada um nunca esteve em dúvida:

```
GAB-ESCOVINHA-SU-01     escovinha SU
GAB-MA-DIAG-ESC-01      mão de amigo diagonal
```

O que estava pendente era **espacial**. Havia uma zona medida, `[23.0, 28.0, 38.5, 33.0]`,
anexada ao `GAB-MA-DIAG-ESC-01` com `atribuicao_geometrica: pendente` — ninguém havia
decidido a qual dos dois motivos ela pertencia. E a escovinha estava sem ROI, porque o
bolso que havia sido medido para ela era, na verdade, um **olhal** (correção de
25/07/2026, que invalidou aquelas medições).

Diferente do SU-053, onde faltavam todas as cinco ROIs. Aqui existia uma zona a mais que
motivo identificado.

Esse é o padrão já estabelecido no projeto: motivo é ocorrência local, e quando um perfil
tem dois ou mais, a atribuição de cada bolso medido exige arbitragem — o detector genérico
não decide.

---

## 2. Os candidatos

O detector de bolsos encontrou dez. Referencial: 42,40 × 32,92 mm, origem no canto
inferior esquerdo, x para a direita, y para cima.

| cand | área mm² | boca | circ | ret | lábios | zona [x_min, y_min, x_max, y_max] mm | cobre M2 |
|---|---:|---:|---:|---:|---|---|---:|
| C1 | 28,38 | 4,33 | 0,51 | 0,70 | não | `[34.27, 23.59, 41.00, 30.33]` | **13 %** |
| C2 | 12,11 | 4,08 | 0,38 | 0,48 | não | `[12.08, 0.00, 18.56, 6.08]` | — |
| C3 | 7,49 | 2,79 | 0,43 | 0,51 | não | `[37.29, 0.49, 42.40, 5.67]` | — |
| C4 | 7,40 | 2,83 | 0,43 | 0,50 | não | `[37.27, 19.27, 42.40, 24.51]` | — |
| **C5** | 6,46 | 2,62 | 0,46 | 0,54 | **sim** | `[12.00, 19.55, 17.02, 24.57]` | — |
| C6 | 6,04 | 2,62 | 0,43 | 0,49 | **sim** | `[12.02, 4.90, 17.04, 9.92]` | — |
| C7 | 1,99 | 3,00 | 0,22 | 0,23 | não | `[8.58, 0.00, 13.98, 4.68]` | — |
| C8 | 1,94 | 3,00 | 0,22 | 0,25 | não | `[34.22, 20.25, 39.62, 25.65]` | — |
| C9 | 1,92 | 3,00 | 0,22 | 0,25 | não | `[14.83, 20.25, 20.23, 25.65]` | — |
| C10 | 1,90 | 3,00 | 0,22 | 0,25 | não | `[34.21, 0.00, 39.61, 4.71]` | — |

C5 e C6 são os **únicos dois com lábios de retenção**, e são simétricos entre si: mesma
boca (2,62), áreas próximas (6,46 e 6,04), um alto e um baixo.

---

## 3. Decisão: M1 = C5

```yaml
GAB-ESCOVINHA-SU-01:
  candidato: C5
  zona_protegida: [12.00, 19.55, 17.02, 24.57]
  atribuicao_geometrica: confirmada_por_arbitragem_visual
  classe_status: confirmado
  roi_status: confirmado
  metodo_delimitacao: candidato_automatico_arbitrado
```

C5 é o canal superior esquerdo: boca estreita e lábios de retenção — o discriminante da
escovinha segundo a regra do próprio config.

---

## 4. Decisão: M2 = zona manual confirmada

```yaml
GAB-MA-DIAG-ESC-01:
  candidato: null
  zona_protegida: [23.0, 28.0, 38.5, 33.0]
  atribuicao_geometrica: confirmada_por_arbitragem_visual
  classe_status: confirmado
  roi_status: confirmado
  metodo_delimitacao: zona_manual
```

A zona existente foi confirmada. O motivo é uma **região estrutural composta** — a aba
diagonal — e não um bolso. Por isso nenhum candidato automático corresponde a ele, e não
precisa corresponder: exigir que todo motivo apareça como bolso detectado seria impor uma
forma que o motivo não tem.

---

## 5. C6 descartado para M1

```yaml
C6:
  nao_corresponde_a: GAB-ESCOVINHA-SU-01
  interpretacao: olhal
  motivo: formato_C_com_serrilhas_internas
```

C6 é o encaixe inferior, com formato de "C" e serrilhas internas — **é exatamente a região
que havia sido confundida com escovinha** antes da correção de 25/07/2026. Ter os dois no
mesmo painel, lado a lado, é o que torna a distinção verificável.

Isso **não** cria uma ocorrência oficial de olhal no SU-041. Essa classe não está no
levantamento confirmado do perfil, e a observação fica como registro do descarte.

---

## 6. C1 descartado para M2

```yaml
C1:
  relacao_com_zona_m2: sobreposicao_parcial_incidental
  cobertura_zona_m2: 0.13
  usar_como_delimitacao_m2: false
```

C1 é a cavidade adjacente. Cobre apenas 13 % da zona do M2, e a sobreposição é incidental
— proximidade, não identidade. Substituir a zona manual por ele trocaria uma delimitação
correta por uma que cobre um sétimo da região.

---

## 7. Referencial verificado

```yaml
referencial_zona_m2:
  largura_perfil_mm: 42.4
  altura_perfil_mm: 33.0
  origem: recorte_isolado_SU-041
  deslocamento_suspeito_entre_cards: false
```

O card do SU-041 tem **dois perfis lado a lado**: "MONTANTE MÃO DE AMIGO" com 0,520 kg/m e
o `SU-041 (P-629/E)` com 0,507 kg/m. A ROI captura o segundo.

Isso levantava a dúvida de a zona medida ter vindo de uma leitura sobre o card inteiro, com
referencial deslocado. Verificado que não: a zona cabe nos 42,40 × 33,00 mm do recorte e
atinge y = 33,0, que é o limite superior real do perfil, cobrindo a aba diagonal.

---

## 8. Pendência conhecida removida

`PENDENCIAS_CONHECIDAS` esvaziou, e o validador de schema passou a reportar
**config íntegro**.

Quatro travas novas foram acrescentadas ao validador, porque as três decisões são fáceis
de desfazer por engano — o C6 parece escovinha, o C1 encosta na zona do M2, e uma zona que
não corresponde a bolso nenhum convida a "consertar" substituindo por um candidato:

| trava | falha se |
|---|---|
| M1 = C5 | o candidato do M1 deixar de ser C5 |
| C6 ≠ escovinha | o C6 for atribuído à escovinha |
| M2 = zona manual | o C1 (ou qualquer candidato) substituir a zona manual |
| sem pendente | reaparecer `atribuicao_geometrica: pendente` |

---

## 9. Invariância geométrica

A arbitragem é **semântica**. Nada de geometria mudou, verificado em três frentes:

**Artefatos versionados, HEAD contra working tree:**

| arquivo | hash | |
|---|---|---|
| `20_contorno_bruto.json` | `8143daa880b36405` | idêntico |
| `30_contorno_comercial.json` | `ea3fa8a960e4aa36` | idêntico |
| `40_metricas_bruto.json` | `3ccd444c3648bb74` | idêntico |
| `45_metricas_comercial.json` | `aa84e996805ee878` | idêntico |

**Geometria declarada no config:** `largura_mm` 42,4 · `altura_mm` 33,0 ·
`vazios_esperados` 1 · `roi_norm` `[0.5, 0.36, 0.97, 0.67]` · `pagina_pdf` 184 ·
`fonte_pdf` — todos idênticos ao HEAD, e a assinatura topológica também.

**`git diff` do config:** zero linhas alteradas em chave geométrica. Só metadado semântico
e evidência.

---

## 10. Oito regressões acrescentadas

| teste | invariante |
|---|---|
| `test_su041_m1_aponta_para_c5` | M1 = C5, com a zona e o selo |
| `test_su041_c6_nao_pode_ser_a_escovinha` | C6 é olhal e não virou ocorrência oficial |
| `test_su041_m2_usa_zona_manual` | M2 sem candidato, método `zona_manual` |
| `test_su041_c1_nao_delimita_m2` | `usar_como_delimitacao_m2: false` e os 13 % |
| `test_su041_sem_atribuicao_pendente` | nenhuma atribuição pendente sobrou |
| `test_su041_zona_m2_cabe_no_referencial` | as duas zonas dentro de 42,4 × 33,0 |
| `test_su041_zonas_sobrevivem_a_limpeza_byte_identicamente` | `restaurar_zonas` preserva byte a byte |
| `test_su041_geometria_nao_mudou_na_arbitragem` | dimensões e topologia esperadas intactas |

### Uma correção estrutural que veio junto

Foi a **quarta vez** nesta sprint que um selo novo de procedência quebrou um teste que
repetia a lista de selos aceitos. Parei de remendar caso a caso e centralizei em
`validar_config`:

```python
ROI_STATUS_HUMANO    = ("confirmado_bruno", "confirmado")
ATRIBUICAO_HUMANA    = ("medida", "zona_curada", "confirmada_por_arbitragem_visual")
ATRIBUICAO_PENDENTE  = ("pendente", "pendente_arbitragem")
zona_tem_procedencia_humana(motivo)
```

Os testes importam de lá. Um selo novo agora entra num lugar só.

---

## 11. Suíte

```
pytest tests/test_aquisicao_contornos.py -q   ->  169 passed
pytest -q                                     ->  231 passed   EXIT_CODE=0
```

Zero falhas, zero pulados.

---

## 12. Estado

```yaml
SU-041:
  estado: CANDIDATO_GEOMETRICO_APROVADO
  pendencia_zona: resolvida
  promocao_oficial: ainda_nao_autorizada
```

Microlote da janela:

```yaml
fechados_na_curadoria: 7        # SU-001, SU-002, SU-003, SU-039, SU-040, SU-041, SU-053
aguardando_evidencia_externa: 1
pendencia_restante:
  perfil: SU-102
  motivo: escala_dimensional
```

**Nenhuma promoção oficial.** Não existe `GEO-*` em `dados/`, e não há associação oficial
entre fabricantes.

Painel: `curadoria/composicao/painel_delimitacao_motivos_su041.png` — mostra a arbitragem
aplicada, com o C5 em verde, o C6 e o C1 em vermelho com a razão do descarte, e a zona
manual em tracejado.

---

## 13. O que resta no E.4B

Só a escala física do SU-102. Protocolo em
`curadoria/insumos/protocolo_medicao_fisica_su102.md`.
