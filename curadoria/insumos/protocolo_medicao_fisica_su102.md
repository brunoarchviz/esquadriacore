# Protocolo de medição física — SU-102 (baguete)

Este arquivo é um **formulário a preencher**, não um registro de resultado. Os campos
`null` e as listas vazias significam *não medido*. Não preencher por estimativa.

## Por que a medição é necessária

Quatro catálogos foram investigados e **nenhum publica a dimensão do envelope externo**.
As cotas 10, 11 e 12 medem segmentos internos — a cota 10 nem começa no SU-102, ela parte
do perfil de referência SU-053 desenhado no mesmo card.

A forma já está caracterizada: três fontes independentes dão aspecto **1,137** com
dispersão de **0,08 %**, mesma orientação, mesma topologia, e o gate funcional local
passou em todas as regiões com material.

Falta apenas a escala.

## Por que duas dimensões, e não uma

Com o aspecto travado a 0,08 %, uma única medida seria **matematicamente** suficiente para
derivar a outra. Não basta para homologação: uma medida sozinha não tem como ser
conferida, e um erro de leitura entraria no domínio sem deixar rastro.

Medir largura **e** altura, três vezes cada. O aspecto dos catálogos entra depois, como
**validação cruzada** — nunca como substituto da segunda medida.

## Procedimento

1. Identificar o perfil pelo código gravado ou pela etiqueta; confirmar o fabricante.
2. Limpar a face de medição (rebarba ou tinta acumulada deslocam a leitura).
3. Medir a **largura externa máxima** — a maior distância entre faces opostas no eixo
   horizontal da seção, com o perfil apoiado na orientação do catálogo.
4. Medir a **altura externa máxima** no eixo perpendicular.
5. Repetir cada dimensão **três vezes**, reposicionando o paquímetro entre as leituras.
6. Quando a barra permitir, repetir em **mais de uma seção** ao longo do comprimento —
   extrusão pode variar de ponta a ponta.
7. Fotografar o perfil com o paquímetro em posição, com o mostrador legível.

Instrumento: paquímetro com resolução de **0,01 mm** (0,02 mm aceitável).

## Formulário

```yaml
perfil: SU-102
fabricante:
codigo:
instrumento:
resolucao_instrumento_mm:

largura_externa_mm:
  - null
  - null
  - null

altura_externa_mm:
  - null
  - null
  - null

media_largura_mm:
media_altura_mm:
aspecto_medido:
aspecto_catalogos: 1.137
erro_relativo_aspecto:
evidencias_fotograficas: []
operador:
observacoes:
```

## Critério de aceitação

O resultado entra na curadoria quando:

- as três leituras de cada dimensão ficarem dentro da resolução do instrumento entre si;
- `erro_relativo_aspecto` contra 1,137 ficar **≤ 0,75 %**, a mesma tolerância do gate de
  aquisição;
- houver evidência fotográfica.

Divergência acima de 0,75 % **não** deve ser acomodada: ou a medição está errada, ou o
perfil medido não é o mesmo que os catálogos desenham. Nos dois casos, bloquear e
arbitrar.

## Fontes já investigadas (nenhuma cota o envelope)

| fabricante | código | arquivo | pág. PDF | cotas | aspecto |
|---|---|---|---:|---|---|
| Alcoa | SU-102 | `catalago-alcoa (1).pdf` | 198 | 10, 11, 12 | 1,1366 |
| Centenário | TMS-102 | `Centenário.pdf` | 235 | 11, 12 | 1,1374 |
| Vitral Sul | SU-102 | `PERFIS-DE-ALUMINIO-02-07-2026.pdf` | 91 | 10, 11, 12 | 1,1375 |
| não identificado | TMS-102 | `cebf22_…pdf` | 108 | 12 | pendente de ROI |

Peso declarado: 0,110–0,111 kg/m nas três fontes principais — mais um indício de que os
catálogos descrevem o mesmo perfil.
