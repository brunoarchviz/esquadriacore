# Ingestão do catálogo Alcoa Suprema como manifesto autônomo

**Fonte:** catálogo técnico Linha Suprema — Alcoa, GMPE 009 AGO 04
**Manifesto:** `composicao/insumos/proveniencia_alcoa_suprema.yaml`
**Data:** 2026-08-11
**Sprint:** E.4H, ingestão Nível 1

> **NATUREZA DESTE DOCUMENTO — leia antes de citar.**
> Isto é um **REGISTRO DE PROCESSO** da ingestão: o que foi conferido, o que
> entrou e o que ficou de fora, e por quê. **Não é evidência** e **não está
> registrado como fonte em manifesto nenhum** — nada aqui sustenta afirmação.
> A evidência é o próprio catálogo, cujo sha256 está no manifesto.

---

## 1. O que foi ingerido

O catálogo entra como **manifesto de proveniência autônomo**, com raiz lógica
própria (`ALCOA_LINHA_SUPREMA`), separado do manifesto do acervo de campo
(`SUPREMA_CORRER_2F`), que **não foi tocado**.

```
arquivo   : alcoa-linha-suprema.pdf   (FORA do Git, 8,7 MB)
sha256    : e64577df8d4ff33a7ec0d204f03a321136450507407e29f4e6c080e442d12deb
tamanho   : 9.120.081 bytes
páginas   : 135
título     : SUPREMA-2004.pmd · PDF criado em 2004-08-19
```

Classificação: **documentação primária do fabricante, revisão histórica.**
Não é evidência de campo e não descreve nenhum exemplar medido.

---

## 2. Por que manifesto separado, e não dentro do `SUPREMA_CORRER_2F`

Decisão arquitetural da auditoria cross-manifest da E.4H, e o contrato a
impõe: `validar_manifesto` reprova artefato externo cuja `raiz_logica` não
seja a do próprio manifesto. Um manifesto é uma **unidade autocontida de
resolução** — `id_fonte` e `derivada_de` resolvem só dentro do documento.

Consequência aceita conscientemente: **nenhuma afirmação do
`SUPREMA_CORRER_2F` consegue hoje citar estruturalmente uma CAT-\***. Isso
não é dívida escondida — é o desenho. As afirmações do catálogo dizem o que o
**fabricante** afirma; as regras da tipologia combinam catálogo com medição de
campo e pertencem ao **domínio**, não ao fabricante.

Duas alternativas foram avaliadas e **recusadas**:

- **duplicar a fonte** nos dois manifestos — bloqueada pelo invariante de raiz
  lógica, e criaria dois `id_fonte` para um único artefato sem detecção de
  colisão entre manifestos;
- **registrar o catálogo como `identificador_externo`** dentro do manifesto de
  campo — validaria, mas `verificar-acervo` passaria a **aprovar sem abrir o
  arquivo**, e o sha256 viraria decoração. Falso positivo, recusado.

---

## 3. Como as páginas foram registradas

O deslocamento entre a folha impressa e a página do PDF **não é constante**
neste catálogo:

| conteúdo | folha impressa | página do PDF | deslocamento |
|---|---|---|---|
| perfis SU-001/002/003 | 45 | 42 | −3 |
| perfis SU-039/040/041/053 | 59 | 56 | −3 |
| perfil SU-102 | 71 | 68 | −3 |
| índice de montagens | 116 | 112 | −4 |
| SUP JCR 200 | 117 | 113 | −4 |
| SUP JCR 200A | 118 | 114 | −4 |

Registrar só uma das duas páginas mandaria conferir a folha errada em pelo
menos uma das regiões. É a confirmação de campo do motivo pelo qual
`pagina_documento` e `pagina_pdf` são campos distintos no `LocalizadorDeFonte`
(PR #12).

---

## 4. O que entrou — 12 afirmações, todas LITERAIS

Cada uma foi conferida abrindo a página correspondente do PDF.

| ID | conteúdo | folha |
|---|---|---|
| CAT-01 | SUP JCR 200 é registrado como "Janela de correr 2 folhas" | 116 |
| CAT-02 | a prancha do SUP JCR 200 traz exatamente os oito códigos SU- | 117 |
| CAT-03 | SU-001 = "Marco superior / correr 2", 0,762 kg/m | 45 |
| CAT-04 | SU-002 = "Marco inferior / correr 2", 0,707 kg/m | 45 |
| CAT-05 | SU-003 = "Marco lateral / correr 2", 0,523 kg/m | 45 |
| CAT-06 | SU-039 = "Montante da folha", 0,520 kg/m | 59 |
| CAT-07 | SU-040 = "Montante mão de amigo", 0,480 kg/m | 59 |
| CAT-08 | SU-041 = "Montante mão de amigo", 0,507 kg/m | 59 |
| CAT-09 | SU-053 = "Travessa da folha", 0,507 kg/m | 59 |
| CAT-10 | SU-102 = "Baguete", 0,111 kg/m | 71 |
| CAT-11 | as cotas impressas na prancha, **cruas e sem interpretação** | 117 |
| CAT-12 | SUP JCR 200A é montagem distinta, com outros perfis de marco | 118 |

Todas em `CONFIRMADO_CATALOGO`, com citação `DIRETA` e localizador completo.

Dois achados que o texto do catálogo entrega e que valem registro:
- **SU-040 e SU-041 têm o MESMO nome** ("Montante mão de amigo") e pesos
  diferentes. O nome impresso, sozinho, não distingue um do outro.
- **SU-003 é "Marco lateral" NEUTRO** — o catálogo não separa esquerdo de
  direito, coerente com a arbitragem da E.4E.

---

## 5. O que **não** entrou, e por quê

A proposta anterior listava 14 afirmações candidatas. Três foram **recusadas**
por serem interpretação, não texto do fabricante:

| proposta original | motivo da recusa |
|---|---|
| "L e H do catálogo são as dimensões externas do quadro" | exige rastrear onde as linhas de cota terminam no desenho — leitura visual, não frase impressa |
| "H-50 mede a altura total da folha" | mesma razão: afirma o que a cota mede, e isso não está escrito |
| "a folga do vidro é 3 mm por lado / 6 mm total" | é aritmética sobre duas cotas, não uma declaração do catálogo |

As cotas em si (`L`, `H`, `H-50`, `H-134`, `(L-131,2)/2`, `(L-143,2)/2 Vidro`)
**estão registradas cruas em CAT-11**, sem dizer o que medem. A interpretação
fica disponível para uma rodada de domínio futura, sem ser atribuída à Alcoa.

Também **não** entrou, por não ser declaração do fabricante:

- que a tipologia que estudamos **é** o SUP JCR 200 — o catálogo não conhece
  nosso caso; a identificação é conclusão nossa;
- qualquer expressão em função do **VÃO** (`L-32`, `H-5`, `H-55`,
  `(L-132)/2`), que combina desenho do fabricante com medição de campo;
- quantização, arbitragem ficha × catálogo, conclusões de Caso A/B/C, conflito
  do vidro, hipótese do baguete vertical.

Um teste parametrizado (`test_nenhuma_regra_derivada_entra_como_afirmacao_do_fabricante`)
guarda essa fronteira por padrão de texto, e um segundo teste verifica que o
guarda realmente reprova — um padrão que nunca casasse passaria em silêncio
sobre um manifesto contaminado.

---

## 6. Limites de prova que não podem ser escondidos

- **Nenhuma fórmula de corte foi encontrada nas páginas inspecionadas.** Isso
  **não** afirma que o catálogo inteiro não contenha nenhuma: as 135 páginas
  não foram todas lidas visualmente.
- **Revisão de 2004.** Não descreve necessariamente exemplares fabricados
  depois. Quando físico e catálogo divergirem, registrar ambos — não corrigir
  o físico para caber no catálogo.
- **Nome de papel não é prova de posição.** O catálogo chama o SU-001 de
  "Marco superior"; isso descreve o perfil no catálogo e não prova, sozinho,
  qual peça ocupa qual posição numa janela real medida em campo.

---

## 7. O que esta ingestão **não** mudou

Contrato, schema, gates e o manifesto do acervo de campo permanecem
exatamente como estavam. Nenhuma fórmula foi implementada, nenhuma pendência
dimensional foi resolvida, nenhum gate foi promovido.
