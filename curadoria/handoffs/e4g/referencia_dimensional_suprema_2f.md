# Referência dimensional da Suprema de correr 2 folhas — arbitragem de domínio

**Tipologia:** `SUPREMA_CORRER_2F`
**Arbitrado por:** Bruno de Oliveira Freitas — especialista de domínio
**Data:** 2026-08-09
**Sprint:** E.4G, Rodada 2

> **NATUREZA DESTE DOCUMENTO — leia antes de citar.**
> Isto é um **REGISTRO DERIVADO DE ARBITRAGEM DE DOMÍNIO**. Não é evidência
> física primária. O sha256 deste arquivo prova a **integridade do documento** e
> **quais decisões estão registradas nele** — não prova nenhuma afirmação sobre
> o mundo físico. Um arquivo íntegro pode registrar uma decisão errada.
>
> Este documento **não contém fórmula executável** e não autoriza cálculo.

---

## 1. A decisão

Nas fórmulas da ficha de campo da Suprema de correr de 2 folhas:

```
L = LARGURA DO VÃO
H = ALTURA DO VÃO
```

**Não** são a largura e a altura do quadro acabado, nem da folha, nem da
abertura interna da folha.

Exemplo confirmado pelo especialista — Janela Pequena:

```
L = 2047 mm            (largura do vão)
SU-001 / SU-002:  L - 32  =  2047 - 32  =  2015 mm
```

Bruno confirmou explicitamente que a expressão **parte do vão**, e não da
dimensão já acabada do quadro.

## 2. O que esta decisão resolve

Resolve a **semântica da variável** de entrada das expressões dimensionais da
ficha: quando a ficha escreve `L`, está falando do vão.

## 3. O que esta decisão NÃO resolve

Não torna nenhuma expressão homologada para produção. Em particular, **não**
autoriza inferir nenhuma política para resultados fracionários — nem
arredondamento, nem truncamento, nem descarte de 0,5, nem tolerância.

Referência da entrada, expressão, saída e política de quantização são **quatro
questões separadas**. Confirmar a primeira não decide as outras três.

## 4. Base factual da arbitragem

A ficha de campo (`01_ficha_campo.docx`, sha256 `409b532bb906…`) registra, na
seção 5, uma coluna **"Corte real (mm)"** — saída de corte medida. Ela existe
**somente para o caso principal**, a Janela Pequena.

Contra esses cortes reais, com `L`/`H` lidos como vão (2047 × 745):

| perfil | expressão da ficha | calculado | corte real | resíduo |
|---|---|---|---|---|
| SU-001 | `L - 32` | 2015 | 2015 | **0** |
| SU-002 | `L - 32` | 2015 | 2015 | **0** |
| SU-003 | `H - 5` | 740 | 740 | **0** |
| SU-039 | `H - 55` | 690 | 690 | **0** |
| SU-040 | `H - 55` | 690 | 690 | **0** |
| SU-041 | `H - 55` | 690 | 690 | **0** |
| SU-053 | `(L - 132) / 2` | **957,5** | **957** | **−0,5** |

Nenhuma outra referência testada (quadro, folha, medida interna da folha, vidro,
baguete) reproduz qualquer um desses cortes.

## 5. Limitação que a aritmética não podia vencer

Nos três casos medidos, `QUADRO = VÃO − 32` na largura e `VÃO − 5` na altura.
Como o desconto da expressão é o **mesmo número**, estas duas leituras produzem
resultados idênticos em todos os casos disponíveis:

```
SU-001 = VÃO_L − 32          e          SU-001 = QUADRO_L
SU-003 = VÃO_H − 5           e          SU-003 = QUADRO_H
SU-039 = VÃO_H − 55          e          SU-039 = QUADRO_H − 50
```

Os números **sozinhos nunca poderiam** ter separado essas leituras: os três
casos não variam a relação vão→quadro, então funcionam como um único teste.

**Coincidência algébrica não é definição de variável.** Foi a arbitragem do
especialista, e não a aritmética, que fixou a semântica. Este parágrafo existe
para que ninguém, no futuro, leia a coincidência numérica como se fosse a prova.

## 6. Estado das expressões — dois eixos independentes

| perfil | expressão | eixo 1 — referência da variável | eixo 2 — expressão de corte |
|---|---|---|---|
| SU-001 | `L - 32` | **CONFIRMADA POR DOMÍNIO** (L = vão) | candidata, com 1 corte real exato |
| SU-002 | `L - 32` | **CONFIRMADA POR DOMÍNIO** | candidata, com 1 corte real exato |
| SU-003 | `H - 5` | **CONFIRMADA POR DOMÍNIO** (H = vão) | candidata, com 1 corte real exato |
| SU-039 | `H - 55` | **CONFIRMADA POR DOMÍNIO** | candidata, com 1 corte real exato |
| SU-040 | `H - 55` | **CONFIRMADA POR DOMÍNIO** | candidata, com 1 corte real exato |
| SU-041 | `H - 55` | **CONFIRMADA POR DOMÍNIO** | candidata, com 1 corte real exato |
| SU-053 | `(L - 132) / 2` | **CONFIRMADA POR DOMÍNIO** | candidata, **com quantização pendente** |

"1 corte real exato" quer dizer exatamente isso: **um** caso. Não é validação
multicaso, e não abre gate de produção.

## 7. SU-053 — a fração continua em aberto

```
Caso A:  L = 2047      (2047 - 132) / 2 = 957,5      corte real = 957
```

O que está registrado: o resultado matemático é 957,5 e o corte medido é 957.

O que **não** está decidido: qual mecanismo transforma ou interpreta o resultado
fracionário na fabricação ou no sistema. Pode ser regra do sistema, prática de
oficina, medida de fita, arredondamento de catálogo ou outra coisa. **Nenhuma
delas foi escolhida.**

Nota sobre operações que às vezes se confundem: para valores **positivos**, que
é o caso de todo comprimento de corte deste domínio, `floor` e `trunc` devolvem
o mesmo resultado. Uma medição futura **não** distingue as duas. Ela pode, no
máximo, corroborar que a fração de 0,5 mm não foi levada para cima.

## 8. Casos B e C

As Janelas Média e Grande têm dimensões montadas registradas, mas **não têm
saída de corte real** para nenhum perfil.

```
SAÍDA DE CORTE REAL NÃO DISPONÍVEL
```

Usar quadro, folha ou medida interna como substituto do corte seria comparar
grandezas diferentes. Não foi feito. Os dois casos continuam valiosos para as
relações entre dimensões montadas — não para validar expressão de corte.

## 9. Relações empíricas observadas — não são regra

Constantes nos três casos:

| relação | largura | altura |
|---|---|---|
| `VÃO − QUADRO` | 32 mm | 5 mm |
| `MEDIDA_INTERNA_DA_FOLHA − VIDRO` | 6 mm | 6 mm |
| `BAGUETE_LARGURA` | igual à medida interna de largura da folha | — |

A relação do vidro considera os valores não conflitantes (ver seção 11).
Nenhuma destas relações foi promovida a regra nem entrou em motor algum.

## 10. Fontes externas — o que cada uma vale aqui

**VidroSys** — referência derivada / sistema anterior do próprio Bruno. Documenta
literalmente `L = Largura do vão` e `H = Altura do vão`, e repete as quatro
expressões. Classificação: **CORROBORAÇÃO DERIVADA**. Não é segunda prova física
independente — pode compartilhar a mesma origem de catálogo da ficha.

**Wvetro** — benchmark externo. Entrada `1500 × 1200`, campo `Medida: Interna`.
Comparado com as expressões da ficha, continua divergindo: `+1 mm` nos marcos e
montantes, `−3 mm` no SU053. A confirmação de Bruno **não** significa que a
palavra "INTERNA" do Wvetro queira dizer vão — são documentos e sistemas
diferentes. Wvetro permanece benchmark, nunca autoridade física.

**TMS001** — permanece literal. **Nenhuma equivalência com SU-001 foi criada.**
Ela não é necessária para esta arbitragem e continua PENDENTE.

## 11. Pendências preservadas

| pendência | estado |
|---|---|
| vidro da folha 2: 934 (§9 e §6 folha 1) × 994 (§6 folha 2) | **CONFLITO — ARBITRAGEM PENDENTE**, tratado na subrodada de vidro |
| baguete vertical do Caso B = 980 mm, fora do padrão de A e C | **REGISTRADO, não corrigido** |
| política de quantização do SU-053 | **PENDENTE** |
| equivalência TMS001 × SU-001 | **PENDENTE**, não bloqueante |
| "trilho interno" × `PLANO_INTERNO` | **PENDENTE**, não bloqueante — SU-040 e SU-041 têm a mesma expressão e o mesmo corte |
| validação multicaso das expressões | **PENDENTE** — existe 1 caso com corte real |

## 12. Gates

Esta arbitragem **não** altera nenhum gate.

```
visualização preliminar    ABERTO
cálculo                    BLOQUEADO
produção                   BLOQUEADO
```

Nenhum motor de cálculo, parser, evaluator ou regra executável foi criado.
