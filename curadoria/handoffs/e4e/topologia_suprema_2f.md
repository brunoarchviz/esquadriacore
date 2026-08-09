# Topologia estrutural — Janela Suprema de correr, 2 folhas, vidro por baguete

## 0. O QUE ESTE DOCUMENTO É — leia antes de citá-lo

Este é um **REGISTRO DERIVADO DE ARBITRAGEM DE DOMÍNIO**.

**NÃO é evidência física primária.** Não é foto, não é medição, não é ficha de
campo. É o registro escrito de uma decisão técnica tomada por um especialista.

Arbitragem: **Bruno** — 2026-08-09.

O que o SHA-256 deste arquivo prova:

- a integridade e a identidade **deste documento**;
- **quais decisões técnicas foram registradas** nele.

O que o SHA-256 deste arquivo **NÃO** prova:

- que o SU-001 está fisicamente no quadro superior de uma janela real;
- que o SU-040 encontra o SU-041 numa janela real;
- que existem oito baguetes numa janela real;
- nenhuma outra afirmação sobre o mundo físico.

Um documento íntegro pode registrar uma decisão errada. Hash é prova de que o
texto não mudou, nunca de que o texto está certo.

### Evidências primárias que originaram a arbitragem

A decisão do especialista se apoiou em:

- três janelas físicas reais e independentes (Pequena, Média, Grande);
- o quadro da Grande sem folhas;
- ficha de campo preenchida;
- fotografias;
- benchmark Wvetro (1500×1200), usado apenas como comparação externa — nenhuma
  regra, fórmula ou arquitetura foi copiada dele;
- material VidroSys, na mesma condição de benchmark.

### PENDENTE DE INGESTÃO DAS EVIDÊNCIAS PRIMÁRIAS

**Nenhum desses artefatos está disponível no repositório nesta branch.** Eles
não foram lidos, não foram hasheados e não foram vinculados a afirmação
nenhuma.

Por isso, deliberadamente, **não existe** aqui nem em `composicao/`:

- path para foto, ficha, janela medida ou material de benchmark;
- SHA-256 de qualquer um deles;
- ID de fonte representando qualquer um deles;
- qualquer estado que sugira "evidência local verificada".

Inventar esses registros faria a receita parecer lastreada em prova física
quando está lastreada em decisão de especialista. A ingestão é rodada própria,
imediatamente após o fechamento da E.4E: lá os artefatos reais entram, ganham
hash e passam a sustentar cada afirmação individualmente.

**Até lá, a procedência da topologia é: arbitragem de domínio, primárias
pendentes.**

---

## 1. Escopo

Este documento registra **topologia** — onde cada perfil fica. Nenhuma medida,
fórmula, folga, desconto, tolerância ou offset aparece aqui.

É a fonte citada por `composicao/receita.py` (`FONTE-TOPOLOGIA-E4E`) para os
componentes e para a relação de encontro central.

---

## 2. Perfis oficiais envolvidos

Os oito perfis promovidos no E.4C: SU-001, SU-002, SU-003, SU-039, SU-040,
SU-041, SU-053, SU-102.

---

## 3. Quadro

| ocorrência | perfil | papel | orientação |
|---|---|---|---|
| `SUPREMA_CORRER_2F:QUADRO-SUPERIOR` | SU-001 | `MARCO_SUPERIOR` | horizontal |
| `SUPREMA_CORRER_2F:QUADRO-INFERIOR` | SU-002 | `MARCO_INFERIOR` | horizontal |
| `SUPREMA_CORRER_2F:QUADRO-LATERAL-1` | SU-003 | `MARCO_LATERAL` | vertical |
| `SUPREMA_CORRER_2F:QUADRO-LATERAL-2` | SU-003 | `MARCO_LATERAL` | vertical |

As duas ocorrências de SU-003 têm **identificadores distintos e o mesmo papel
neutro**. Esquerda e direita não são gravadas: a receita precisa poder ser
espelhada sem trocar de identidade técnica. Lateralidade é configuração de uma
instância, não da tipologia.

Os sufixos `-1` e `-2` são apenas desambiguação de ocorrência. Não afirmam
lado, ordem de montagem nem posição no vão.

---

## 4. Planos das folhas — convenção formal

A janela tem duas folhas móveis, cada uma no seu trilho:

```text
PLANO_INTERNO   plano da folha mais próximo do ambiente INTERNO da edificação
PLANO_EXTERNO   plano da folha mais próximo do EXTERIOR da edificação
```

É uma relação de **profundidade** da esquadria em relação a interior/exterior
do edifício. A convenção **não** significa:

- esquerda ou direita;
- o lado de quem observa uma foto ou um desenho;
- direção ou sentido de abertura.

Consequência que importa: **a convenção continua válida quando a composição é
espelhada.** Espelhar troca lados, não troca qual folha está mais perto de
dentro.

Nenhuma distância ou offset entre os planos é declarada — a relação registrada
é qualitativa.

### Folha do plano interno

| ocorrência | perfil | papel | orientação |
|---|---|---|---|
| `FOLHA-INTERNA:MONTANTE-LATERAL` | SU-039 | `MONTANTE_LATERAL_FOLHA` | vertical |
| `FOLHA-INTERNA:MONTANTE-CENTRAL` | SU-040 | `MONTANTE_CENTRAL_FOLHA` | vertical |
| `FOLHA-INTERNA:TRAVESSA-SUPERIOR` | SU-053 | `TRAVESSA_SUPERIOR_FOLHA` | horizontal |
| `FOLHA-INTERNA:TRAVESSA-INFERIOR` | SU-053 | `TRAVESSA_INFERIOR_FOLHA` | horizontal |

### Folha do plano externo

| ocorrência | perfil | papel | orientação |
|---|---|---|---|
| `FOLHA-EXTERNA:MONTANTE-LATERAL` | SU-039 | `MONTANTE_LATERAL_FOLHA` | vertical |
| `FOLHA-EXTERNA:MONTANTE-CENTRAL` | SU-041 | `MONTANTE_CENTRAL_FOLHA` | vertical |
| `FOLHA-EXTERNA:TRAVESSA-SUPERIOR` | SU-053 | `TRAVESSA_SUPERIOR_FOLHA` | horizontal |
| `FOLHA-EXTERNA:TRAVESSA-INFERIOR` | SU-053 | `TRAVESSA_INFERIOR_FOLHA` | horizontal |

Ou seja:

```text
SU-040   montante central da folha do PLANO INTERNO
SU-041   montante central da folha do PLANO EXTERNO
```

**Terminologia:** SU-040 e SU-041 são os perfis/montantes **mão de amigo**.
Mão de amigo é **perfil**, não ferragem. Por isso o papel registrado é
`MONTANTE_CENTRAL_FOLHA` — a posição estrutural — e não `MAO_DE_AMIGO`, que
permanece no enum apenas por compatibilidade.

Travessa superior e inferior são posições verticais dentro da folha, não
lateralidade; ficam registradas porque a arbitragem as distingue.

---

## 5. Encontro central — relação, não peça

```text
FOLHA-INTERNA:MONTANTE-CENTRAL   (SU-040, plano interno)
        ↕  ENCONTRO_CENTRAL
FOLHA-EXTERNA:MONTANTE-CENTRAL   (SU-041, plano externo)
```

São **duas peças diferentes em dois planos diferentes**. Não existe uma terceira
peça chamada "encontro central", e o encontro não é papel de nenhuma delas.

Registrado como `RelacaoEntreComponentes`, citando os **identificadores das
ocorrências** — não os códigos de perfil. Citar "SU-040 encontra SU-041" ficaria
ambíguo assim que um perfil aparecesse em mais de uma ocorrência.

`PapelComponente.ENCONTRO_CENTRAL` continua existindo no enum por
compatibilidade e **não é usado** nesta receita.

---

## 6. Baguetes

SU-102 está presente nas duas folhas, prendendo o vidro. A regra arbitrada é
**exatamente esta, e nada além dela**:

```text
por folha   2 baguetes horizontais + 2 baguetes verticais
total       SU-102 × 8
```

Os oito identificadores são **neutros**:

```text
FOLHA-INTERNA:BAGUETE-HORIZONTAL-1     FOLHA-EXTERNA:BAGUETE-HORIZONTAL-1
FOLHA-INTERNA:BAGUETE-HORIZONTAL-2     FOLHA-EXTERNA:BAGUETE-HORIZONTAL-2
FOLHA-INTERNA:BAGUETE-VERTICAL-1       FOLHA-EXTERNA:BAGUETE-VERTICAL-1
FOLHA-INTERNA:BAGUETE-VERTICAL-2       FOLHA-EXTERNA:BAGUETE-VERTICAL-2
```

Os sufixos `-1` e `-2` **desambiguam ocorrências e nada mais**. Não está
arbitrado, e portanto não deve ser lido de lugar nenhum, que:

```text
HORIZONTAL-1 = superior      HORIZONTAL-2 = inferior
VERTICAL-1   = esquerda      VERTICAL-2   = direita
```

Por isso a posição dos baguetes fica **não declarada** na receita: afirmar
"superior" ou "esquerda" aqui seria inventar identidade que a arbitragem não
estabeleceu, e que a ingestão das evidências primárias ainda pode contradizer.

O baguete é acabamento do vidro, não quadro estrutural da folha. Os dois grupos
ficam distinguíveis pelo papel (`BAGUETE` contra os papéis estruturais), o que
permite contar sem misturar:

```text
12 ocorrências estruturais   (4 de quadro + 4 por folha × 2)
 8 ocorrências de baguete
20 ocorrências físicas no conjunto
```

---

## 7. O que este documento NÃO estabelece

Nenhuma medida, fórmula de corte, regra de vidro, regra de baguete, folga,
tolerância, arredondamento, offset entre planos, roldana, fecho, escova ou
acessório. Nenhuma quantidade dimensional.

A topologia diz **onde cada perfil fica**. Quanto cada peça mede continua sendo
pergunta aberta, e será respondida contra janelas reais medidas — não por
inferência a partir de benchmark externo.

Os gates de cálculo e de produção permanecem **bloqueados**: registrar topologia
não é calcular. E, enquanto as evidências primárias não forem ingeridas, esta
topologia é decisão de especialista registrada — não fato verificado no
repositório.
