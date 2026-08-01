# EsquadriaCore — E.4B etapa 12: fechamento dimensional do SU-102

Documento autocontido. Fecha a curadoria do microlote E.4B com oito perfis.
**Não** é promoção oficial: nenhum `GEO-*` foi criado em `dados/`.

---

## 1. O que estava em aberto

O SU-102 (baguete, perímetro do vidro) era o único perfil do microlote sem cota
de envelope externo. Quatro catálogos foram investigados — Alcoa p.198,
Centenário TMS-102 p.235, Vitral Sul p.91 e uma quarta fonte não identificada —
e **nenhum cota o envelope**. As cotas visíveis (10, 11, 12) são segmentos
internos: a cota 10 sequer começa no SU-102, começa no SU-053 desenhado como
referência.

## 2. Uma correção metodológica minha, registrada e não apagada

Numa passagem anterior classifiquei as fotos 005–014 como "paquímetro aberto no
ar" e cheguei a propor rejeitar o lote inteiro de medições.

**Isso estava errado.** O que aparecia aberto eram as **garras pequenas
superiores** do paquímetro, usadas para medição interna, que ficam naturalmente
abertas quando se mede pelo lado externo. As **garras grandes inferiores** estão
em contato com as faces externas do perfil — confirmei por recorte e ampliação
nas fotos 012, 013, 014 e 008.

Erro de leitura do instrumento, meu, não erro de medição do Bruno. As medições
são válidas e nenhuma foto precisou ser repetida. Fica registrado porque o
histórico técnico não deve esconder o caminho até a conclusão.

## 3. Medições físicas aceitas

```yaml
eixo_maior:  {leituras: 4, imagens: [005, 006, 007, 008], valor_mm: 16.9}
eixo_menor:  {leituras: 3, imagens: [012, 013, 014],      valor_mm: 15.0}
alternativas: {imagens: [009, 010, 011], papel: evidencia_da_secao_e_do_encaixe}
preliminares: {imagens: [001, 002, 003, 004], repeticoes_validas: 0}
```

O perfil tem uma aba maior e outra menor para permitir o encaixe — por isso
posições de contato distintas produzem medidas próximas, mas não idênticas.
As imagens 009–011 ficam como evidência complementar, não como segundo eixo.

## 4. Os dois gates, separados

| | dimensões | aspecto | erro máx | limite | resultado |
|---|---|---|---|---|---|
| físico bruto | 16,9 × 15,0 | 1,126667 | 0,952% | 0,75% | **REPROVADO** |
| nominal | 17,0 × 15,0 | 1,133333 | 0,366% | 0,75% | **APROVADO** |

Catálogos usados na validação de forma e aspecto: Alcoa 1,1366, Centenário
1,1374, Vitral Sul 1,1375.

O gate físico bruto **reprovou** e continua registrado assim. Ele não foi
substituído pelo nominal, e o limite de 0,75% não foi alterado.

A decisão **não** é aprovação automática pelo gate:

```yaml
decisao_dimensional:
  tipo: APROVADO_POR_ARBITRAGEM_DE_DOMINIO_COM_NOMINALIZACAO
  especialista_dominio: Bruno
  justificativa: arredondamento_nominal_sem_impacto_funcional
```

O paquímetro leu 16,9 mm. 17,0 mm é a dimensão nominal adotada por
arredondamento declarado.

## 5. Normalização — anisotrópica, dito com todas as letras

`fator_x = 1,005917` ≠ `fator_y = 1,0`, logo a transformação **é
anisotrópica**. Um registro anterior a rotulava como "não é registro
anisotrópico", o que era falso. Corrigido.

```text
registro geométrico entre fontes  = ISOTRÓPICO   (escala 1,000054, rotação -0,03°)
nominalização dimensional final   = ANISOTRÓPICA (fator_x != fator_y), auditada
```

São etapas distintas. A anisotrópica **não** é usada no registro entre
catálogos (`usada_no_registro_entre_catalogos: false`) e não altera topologia.

## 6. Guard de promoção — correção de escopo

Numa rodada anterior eu bloqueei `parametros()` no driver quando
`promocao_oficial == "ainda_nao_autorizada"`. **Era escopo errado.**

`executar_lote1_e4b.py` só escreve em `curadoria/contornos/`, via
`exportar.gravar_artefatos_curadoria`, que já recusa `dados/`, `domain/`,
`contrato/` e `docs/` (`OFICIAIS_PROIBIDOS`). O driver é estruturalmente
incapaz de promover — meu guard bloqueava curadoria legítima sem proteger nada.

Aplicada a solução preferencial: **guard removido do driver**. A proteção
permanece onde a promoção ocorreria, no exportador, e coberta por regressão.

## 7. Artefatos de curadoria

`curadoria/contornos/SU-102/` — seis artefatos, gates aprovados (F1 = 1,0,
0 vazios, estratégia LIMPO):

| artefato | sha256 (16) |
|---|---|
| assinatura_topologica.json | `9977f724e9ceb0dc` |
| contorno_bruto.json | `58d65067725ee40e` |
| contorno_comercial.json | `58d65067725ee40e` |
| contorno_comercial.svg | `b14830a4204d9309` |
| metricas.json | `47e31ab87cbe98a8` |
| operacoes_limpeza.json | `adf1e5b6afcfceaf` |

Hashes idênticos em execuções independentes. `contorno_bruto` e
`contorno_comercial` coincidem porque a limpeza comercial não precisou de
nenhuma operação — não é erro de gravação.

O histórico dimensional viaja dentro do `metricas.json`: leitura física,
dimensão nominal, os dois gates, os fatores X e Y.

### Duas mudanças não previstas na ordem

O SU-102 nunca havia sido reproduzido. Foram necessárias:

1. **`separacao_por_espessura: true` no próprio perfil.** O card Alcoa p.198
   desenha o SU-053 em linha fina como referência de aplicação; sem separar as
   camadas, o detector genérico de contaminação bloqueava o SU-102 em
   `BLOQUEIO_PARA_ARBITRAGEM`. Antes, a separação só ligava via
   `fonte_geometrica_primaria`, que o SU-102 não tem — a geometria dele vem do
   card dele mesmo. `fonte_de_geometria()` passou a aceitar a flag no perfil.
2. **`vazios_esperados: 0`**, já registrado em
   `equivalencia_tms102.evidencia.vazios_su102`.

## 8. Estado final

```yaml
SU-102:
  largura_mm: 17.0
  altura_mm: 15.0
  estado_geometrico: CANDIDATO_GEOMETRICO_APROVADO
  estado_dimensional: DIMENSAO_NOMINAL_APROVADA_POR_ARBITRAGEM_DE_DOMINIO
  promocao_oficial: ainda_nao_autorizada
  geo_su102: NAO_CRIADO
```

Equivalência com o TMS-102 **continua pendente**: medir o SU-102 não mede o
perfil do outro catálogo.

## 9. Microlote E.4B

```yaml
fechados_na_curadoria: 8
aguardando_evidencia_externa: 0
perfis: [SU-001, SU-002, SU-003, SU-039, SU-040, SU-041, SU-053, SU-102]
```

Significa **curadoria concluída**. Não significa promoção oficial, merge em
`main`, tag ou release.

## 10. Commits desta etapa

```
d6a6009  feat(curadoria): conclui escala dimensional do SU-102
f3a2924  docs(curadoria): registra fechamento dimensional do E.4B
5537e1e  fix(curadoria): alinha estado final e equivalencia do E.4B
cc365be  Merge pull request #3
```

Registrados aqui, no handoff histórico, e não no documento de estado atual —
hashes e branches são transitórios.

## 11. Governança

`dados/`, `domain/`, `contrato/`, `docs/`, `VERSION`, `CHANGELOG.md`:
inalterados. Nenhum `GEO-SU-102`.
