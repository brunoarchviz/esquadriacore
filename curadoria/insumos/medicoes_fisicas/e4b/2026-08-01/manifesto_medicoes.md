# E.4B — Manifesto das medições físicas (2026-08-01)

Continuação da etapa 12. Este documento fecha a classificação dos sete perfis
identificados e deixa o SU-102 registrado como pendência isolada, conforme a
sequência de decisões abaixo.

**Aviso de método, antes de qualquer número.** Nas 39 fotos da primeira
remessa, os dedos que seguram a peça encobrem parte do paquímetro ou da seção,
e o perfil aparece girado em relação à câmera. Onde a classificação abaixo diz
"provável", é leitura visual minha, não fato confirmado por medição
independente. As cotas de catálogo não dependem dessa leitura — elas continuam
sendo a fonte principal dos sete perfis.

**Correção de leitura do instrumento (registrada por honestidade).** Numa
passagem anterior classifiquei as fotos 005–014 do SU-102 como "paquímetro
aberto no ar" e cheguei a propor rejeitar o lote. **Isso estava errado.** O que
aparecia aberto eram as *garras pequenas superiores*, usadas para medição
interna, que ficam naturalmente abertas quando se mede pelo lado externo. As
*garras grandes inferiores* estão em contato com as faces externas do perfil —
verifiquei por ampliação nas fotos 012, 013, 014 e 008. As medições do Bruno
são válidas e não precisam ser repetidas. O erro foi meu, de leitura do
instrumento.

---

## 1. SU-001 — bate com o catálogo (71,0 × 33,0)

| foto | valor (mm) | classificação | uso |
|---|---|---|---|
| 001 | 71 | largura externa (provável — mostra a face larga do perfil) | validação cruzada |
| 002 | 33 | altura externa (provável) | validação cruzada |
| 003 | 21 | dimensão parcial / interna | não usar como envelope |
| 004 | 52 | dimensão parcial / interna | não usar como envelope |
| 005 | 69 | largura externa alternativa (próxima de 71, dentro de folga de medição manual) | validação cruzada |

Catálogo prevalece: **SU-001 = 71,0 × 33,0 mm**. Δ ≈ 0.

## 2. SU-002 — decisão já arbitrada por Bruno

```yaml
001_69.jpeg: {tipo_de_medida: largura_externa, valor_fisico_mm: 69, valor_catalogo_mm: 71, decisao: MANTER_CATALOGO}
002_37.jpeg: {tipo_de_medida: altura_local_ou_parcial, usar_como_envelope: false}
003_23.jpeg: {tipo_de_medida: dimensao_parcial_ou_interna, usar_como_envelope: false}
004_21.jpeg: {tipo_de_medida: dimensao_parcial_ou_interna, usar_como_envelope: false}
005_49.jpeg: {tipo_de_medida: largura_parcial_ou_interna, usar_como_altura_externa: false, usar_como_envelope: false}
```

Nas fotos 003/004, o paquímetro está fechado sobre uma nervura interna do
perfil, não sobre o envelope externo — consistente com "não usar como
envelope".

Catálogo prevalece: **SU-002 = 71,0 × 47,0 mm**. A medição física é validação
cruzada, não substitui a cota.

## 3. SU-003 — bate com o catálogo (71,0 × 26,0)

| foto | valor (mm) | classificação | uso |
|---|---|---|---|
| 001 | 71 | largura externa (provável) | validação cruzada |
| 002 | 26 | altura externa (provável) | validação cruzada |
| 003 | 13,8 | dimensão interna/parcial (câmara) | não usar como envelope |
| 004 | 26 | repetição da altura (confirma 002) | validação cruzada |

Catálogo prevalece: **SU-003 = 71,0 × 26,0 mm**. Δ ≈ 0.

## 4. SU-039 — decisão já arbitrada por Bruno

```yaml
001_52,6.jpeg: {tipo_de_medida: largura_externa, valor_fisico_mm: 52.6, valor_catalogo_mm: 52.6, decisao: BATE}
002_26.jpeg:   {tipo_de_medida: altura_externa_maxima, valor_fisico_mm: 26, valor_catalogo_mm: 25, diferenca_mm: 1, decisao: MANTER_CATALOGO, status: VALIDACAO_FISICA_APROXIMADA_COM_DIVERGENCIA}
003_40,6.jpeg: {tipo_de_medida: dimensao_interna_ou_parcial, usar_como_envelope: false}
```

Catálogo prevalece: **SU-039 = 52,60 × 25,00 mm**. Divergência de 1,0 mm na
altura registrada, não reabre a geometria (pode ser posicionamento do
paquímetro, pintura ou variação de extrusão — só reabrir se repetições
confirmarem divergência substancial).

## 5. SU-040 — compatível com o catálogo (42,4 × 30,7)

| foto | valor (mm) | classificação | uso |
|---|---|---|---|
| 001 | 31 | altura externa (provável, Δ +0,3 do catálogo) | validação cruzada |
| 002 | 43 | largura externa (provável, Δ +0,6 do catálogo) | validação cruzada |
| 003 | 33 | dimensão parcial/interna | não usar como envelope |
| 004 | 11 | dimensão parcial (nervura/gancho) | não usar como envelope |
| 005 | 18 | dimensão parcial | não usar como envelope |
| 006 | 22 | dimensão parcial | não usar como envelope |

Catálogo prevalece: **SU-040 = 42,4 × 30,7 mm**. Δ compatível com
arredondamento de paquímetro manual (±0,5 mm).

## 6. SU-041 — compatível com o catálogo (42,4 × 33,0)

| foto | valor (mm) | classificação | uso |
|---|---|---|---|
| 001 | 33 | altura externa (provável, Δ 0) | validação cruzada |
| 002 | 43 | largura externa (provável, Δ +0,6) | validação cruzada |
| 003 | 24 | dimensão parcial/interna | não usar como envelope |
| 004 | 15 | dimensão parcial | não usar como envelope |
| 005 | 11 | dimensão parcial (nervura/gancho) | não usar como envelope |
| 006 | 18 | dimensão parcial | não usar como envelope |
| 007 | 22 | dimensão parcial | não usar como envelope |

Catálogo prevalece: **SU-041 = 42,4 × 33,0 mm**. Δ compatível com
arredondamento.

## 7. SU-053 — compatível com o catálogo (22,2 × 51,0, via TMS-053)

| foto | valor (mm) | classificação | uso |
|---|---|---|---|
| 001 | 51 | eixo externo de 51 mm (provável, Δ 0) | validação cruzada |
| 002 | 0,4 | espessura de parede | não usar como envelope |
| 003 | 18 | dimensão parcial/interna | não usar como envelope |
| 004 | 22 | dimensão parcial, próxima da cota de altura (22,2) mas não confirmada como envelope | não usar como envelope sem confirmação |

Catálogo prevalece: **SU-053 = 22,2 × 51,0 mm**.

---

## 8. SU-102 — fechado pela medição física

Único perfil do microlote sem cota de envelope em catálogo nenhum. A dimensão
vem da medição física repetida do Bruno; os catálogos entram como validação de
forma e aspecto.

### 8.1 Classificação das 14 imagens

| grupo | imagens | papel | repetições válidas |
|---|---|---|---|
| preliminares | 001, 002, 003, 004 | diagnóstico; contato parcialmente encoberto | 0 |
| **eixo maior** | **005, 006, 007, 008** | **envelope externo, eixo A** | **4** |
| posições alternativas | 009, 010, 011 | evidência da seção e do encaixe | — (não é eixo independente) |
| **eixo menor** | **012, 013, 014** | **envelope externo, eixo perpendicular** | **3** |

O perfil tem uma aba maior e outra menor para permitir o encaixe — por isso
posições de contato distintas produzem medidas próximas, mas não idênticas.
As imagens 009–011 ficam como evidência complementar, não como um segundo eixo.

### 8.2 Dimensões

```yaml
medicoes_fisicas:
  eixo_maior_mm: 16.9      # o que o paquímetro leu
  eixo_menor_mm: 15.0

dimensoes_nominais:
  eixo_maior_mm: 17.0      # arredondamento declarado pelo especialista
  eixo_menor_mm: 15.0      # físico e nominal coincidem

arredondamento_nominal:
  eixo_maior: {medido_mm: 16.9, nominal_mm: 17.0, justificativa: tolerancia_pratica_sem_impacto}
```

O paquímetro **não** leu 17,0 mm. Leu 16,9 mm. Os dois valores ficam
registrados.

### 8.3 Os dois gates — separados, nenhum substitui o outro

**Gate de aspecto sobre a leitura física bruta:**

| dimensões | aspecto | erro mín | erro máx | limite | resultado |
|---|---|---|---|---|---|
| 16,9 × 15,0 | 1,126667 | 0,874% | 0,952% | 0,75% | **REPROVADO** |

**Gate de aspecto sobre a dimensão nominal:**

| dimensões | aspecto | erro mín | erro máx | limite | resultado |
|---|---|---|---|---|---|
| 17,0 × 15,0 | 1,133333 | 0,287% | 0,366% | 0,75% | **APROVADO** |

O resultado físico bruto fica registrado como de fato ocorreu. Ele **não** foi
substituído pelo nominal.

A decisão final **não** é `APROVADO_AUTOMATICAMENTE_PELO_GATE_FISICO`. É:

```yaml
decisao_dimensional:
  tipo: APROVADO_POR_ARBITRAGEM_DE_DOMINIO_COM_NOMINALIZACAO
  operador_medicao: Bruno
  especialista_dominio: Bruno
  leitura_fisica_mm: [16.9, 15.0]
  dimensao_nominal_mm: [17.0, 15.0]
  justificativa: arredondamento_nominal_sem_impacto_funcional
  validacao_cruzada: aspecto_de_tres_catalogos
```

Isso preserva o gate de 0,75% sem alterá-lo nem forçá-lo a passar.

### 8.4 Normalização — anisotrópica, e dito com todas as letras

`fator_x = 1.005917` e `fator_y = 1.0` são diferentes. Portanto a transformação
**é matematicamente anisotrópica**. Numa versão anterior deste manifesto eu a
rotulei como "não é registro anisotrópico", o que era falso — corrigido.

```yaml
normalizacao_dimensional:
  tipo: NOMINALIZACAO_POS_CURADORIA_COM_FATORES_INDEPENDENTES
  anisotropica: true
  origem_fisica_mm: [16.9, 15.0]
  destino_nominal_mm: [17.0, 15.0]
  fator_x: 1.005917
  fator_y: 1.0
  aplicada_apos: [aquisicao_da_forma, registro_isotropico_entre_fontes, gate_de_aspecto_das_fontes]
  finalidade: ajustar_escala_fisica_para_dimensao_nominal
  usada_no_registro_entre_catalogos: false
  altera_topologia: false
  justificativa: {tipo: arbitragem_de_dominio, responsavel: Bruno, impacto_funcional: nenhum}
```

A distinção que importa:

```text
registro geométrico entre fontes  = ISOTRÓPICO   (escala 1,000054, rotação -0,03°)
nominalização dimensional final   = ANISOTRÓPICA (fator_x != fator_y), auditada
```

São duas transformações distintas, em etapas distintas. A anisotrópica não é
usada no registro entre catálogos.

### 8.5 Estado

```yaml
SU-102:
  largura_mm: 17.0
  altura_mm: 15.0
  estado_geometrico: CANDIDATO_GEOMETRICO_APROVADO
  estado_dimensional: DIMENSAO_NOMINAL_APROVADA_POR_ARBITRAGEM_DE_DOMINIO
  fonte_dimensional_primaria:
    tipo: medicao_fisica_repetida_com_nominalizacao
    operador: Bruno
    leitura_fisica_mm: [16.9, 15.0]
    dimensao_nominal_mm: [17.0, 15.0]
  validacao_catalogo:
    funcao: validacao_de_forma_e_aspecto
    dimensao_externa_diretamente_cotada: false
    aspectos: [1.1366, 1.1374, 1.1375]
  promocao_oficial: ainda_nao_autorizada
  geo_su102: NAO_CRIADO
```

A equivalência com o TMS-102 **continua pendente**: medir o SU-102 não mede o
perfil do outro catálogo.

### 8.6 Artefatos de curadoria

Reproduzido em `curadoria/contornos/SU-102/`, seis artefatos, gates aprovados
(F1 = 1,0, 0 vazios, estratégia LIMPO), hashes idênticos em execuções
independentes:

| artefato | sha256 (16) |
|---|---|
| assinatura_topologica.json | `9977f724e9ceb0dc` |
| contorno_bruto.json | `58d65067725ee40e` |
| contorno_comercial.json | `58d65067725ee40e` |
| contorno_comercial.svg | `b14830a4204d9309` |
| metricas.json | `47e31ab87cbe98a8` |
| operacoes_limpeza.json | `adf1e5b6afcfceaf` |

`contorno_bruto` e `contorno_comercial` têm o mesmo hash porque a limpeza
comercial não precisou de nenhuma operação — o contorno bruto já passou nos
gates comerciais. Não é erro de gravação.

Para isso funcionar foram necessárias duas mudanças que **não** estavam
previstas na ordem, ambas registradas no config:

1. `separacao_por_espessura: true` no próprio perfil. O card Alcoa p.198
   desenha o SU-053 em linha fina como referência; sem separar, o detector
   genérico de contaminação bloqueava o SU-102 em `BLOQUEIO_PARA_ARBITRAGEM`.
   Antes, a separação só ligava via `fonte_geometrica_primaria`, que o SU-102
   não tem — a geometria dele vem do card dele mesmo.
2. `vazios_esperados: 0`, já registrado em
   `equivalencia_tms102.evidencia.vazios_su102`.

---

## 9. Resumo

```yaml
fechados_na_curadoria: 8
aguardando_evidencia_externa: 0
perfis:
  - SU-001   # 71,0 x 33,0  catalogo
  - SU-002   # 71,0 x 47,0  catalogo
  - SU-003   # 71,0 x 26,0  catalogo
  - SU-039   # 52,6 x 25,0  catalogo (divergencia fisica +1,0mm registrada)
  - SU-040   # 42,4 x 30,7  catalogo
  - SU-041   # 42,4 x 33,0  catalogo
  - SU-053   # 22,2 x 51,0  catalogo (via TMS-053)
  - SU-102   # 17,0 x 15,0  MEDICAO FISICA (nenhum catalogo cota o envelope)

divergencias_registradas_sem_reabrir_geometria: [SU-039 altura +1,0mm]
```

Isto é o fechamento da **curadoria** do microlote E.4B. **Não** é promoção
oficial para `dados/` — nenhum `GEO-*` foi criado.

## 10. Governança

Nenhuma alteração em `dados/`, `domain/`, `contrato/`, `docs/`, `VERSION`,
`CHANGELOG.md`. Nenhum `GEO-SU-102` criado ou promovido. Nenhum commit, push,
tag, PR ou release nesta rodada.
