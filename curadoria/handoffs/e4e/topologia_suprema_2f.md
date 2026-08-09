# Topologia estrutural — Janela Suprema de correr, 2 folhas, vidro por baguete

Documento durável. Registra a **arbitragem de domínio** que estabeleceu quais
perfis oficiais ocupam quais posições na tipologia `SUPREMA_CORRER_2F`.

Responsável pela arbitragem: **Bruno** — 2026-08-09.

Este documento é a fonte citada por `composicao/receita.py` para os componentes
e para a relação de encontro central. Ele registra **topologia**, não cálculo:
nenhuma medida, fórmula, folga, desconto ou offset aparece aqui.

---

## 1. De onde vem esta topologia

Estabelecida fora do repositório, a partir de:

- três janelas físicas reais e independentes;
- ficha de campo;
- comparação com um sistema externo, usada apenas como **benchmark** — nenhuma
  regra, fórmula ou arquitetura foi copiada dele;
- conhecimento de domínio confirmado pelo especialista.

O que está aqui é a **posição funcional de cada perfil**. As medidas continuam
pendentes e serão levantadas numa rodada dimensional própria.

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

---

## 4. Folhas — dois planos

A janela tem duas folhas móveis, cada uma em seu plano/trilho:

```text
PLANO_INTERNO   folha cujo montante central é o SU-040
PLANO_EXTERNO   folha cujo montante central é o SU-041
```

Nenhuma distância entre os planos é declarada — a relação registrada é
**qualitativa**: interno e externo.

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

**Terminologia:** SU-040 e SU-041 são os perfis/montantes **mão de amigo**.
Mão de amigo é **perfil**, não ferragem. Por isso o papel registrado é
`MONTANTE_CENTRAL_FOLHA` — a posição estrutural — e não `MAO_DE_AMIGO`, que
permanece no enum apenas por compatibilidade.

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

SU-102 está fisicamente presente nas duas folhas, prendendo o vidro:

```text
por folha   2 baguetes horizontais + 2 verticais
total       SU-102 × 8
```

O baguete é acabamento do vidro, não quadro estrutural da folha. Os dois
grupos ficam distinguíveis pelo papel (`BAGUETE` contra os papéis estruturais),
o que permite contar sem misturar:

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
inferência a partir de sistema externo.

Os gates de cálculo e de produção permanecem **bloqueados**: registrar topologia
não é calcular.
