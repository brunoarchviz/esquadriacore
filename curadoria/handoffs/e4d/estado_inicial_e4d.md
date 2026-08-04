# EsquadriaCore — estado inicial da Sprint E.4D

Documento durável. Descreve o ponto de partida da receita técnica da Janela
Suprema de correr com duas folhas.

---

## 1. De onde se parte

A Sprint E.4C está **concluída e integrada**. A biblioteca oficial tem oito
perfis Suprema promovidos, com geometria auditada e associação de fabricante:

| perfil | geometria | associação |
|---|---|---|
| SU-001 | GEO-SU-001 | ALCOA-SU-001 |
| SU-002 | GEO-SU-002 | ALCOA-SU-002 |
| SU-003 | GEO-SU-003 | ALCOA-SU-003 |
| SU-039 | GEO-SU-039 | ALCOA-SU-039 |
| SU-040 | GEO-SU-040 | ALCOA-SU-040 |
| SU-041 | GEO-SU-041 | ALCOA-SU-041 |
| SU-053 | GEO-SU-053 | ALCOA-SU-053 |
| SU-102 | GEO-SU-102 | ALCOA-SU-102 |

O evento da promoção está registrado em
`curadoria/promocoes/e4c/manifesto_promocao_e4b.json`.

SU-102 e TMS-102 são o **mesmo perfil físico**; não existe `GEO-TMS-102`, e
criar um quebraria a identidade confirmada.

---

## 2. Para que serve a E.4D

A biblioteca tem as peças. Ela **não sabe montar a janela**.

A E.4D existe para transformar "temos oito perfis" em "sabemos como estes oito
perfis viram uma janela de correr de duas folhas": qual perfil cumpre cada
papel, quantas peças de cada um, com que corte, que folga, que vidro, que
acessório.

Nada disso pode ser inferido do catálogo nem da geometria.

---

## 3. O que esta rodada preparou

Um pacote `composicao/` que **registra conhecimento** — e não calcula nada:

```text
composicao/modelos.py     estados, fontes, componentes, regras, casos reais
composicao/fontes.py      biblioteca oficial (pelo contrato) e ficha de campo
composicao/receita.py     receita preliminar SUPREMA_CORRER_2F
composicao/validar.py     validações e os três gates
composicao/prontidao.py   relatório do que falta, e por quê
composicao/cli.py         diagnosticar, validar-ficha, prontidao
```

A biblioteca é lida pelo **contrato de consumo**, nunca por `dados/*.json`
direto (ADR-003). A receita **referencia** os perfis por id e nunca copia
contorno (ADR-001).

Comandos:

```bash
python -m composicao.cli diagnosticar --tipologia SUPREMA_CORRER_2F
python -m composicao.cli validar-ficha <caminho da ficha>
python -m composicao.cli prontidao --tipologia SUPREMA_CORRER_2F [--markdown|--json]
```

Não existe comando `calcular`, e não vai existir enquanto o gate de cálculo
estiver bloqueado.

---

## 4. O princípio que governa tudo aqui

Quatro categorias, sempre explícitas:

```text
FATO CONFIRMADO           tem fonte registrada
HIPÓTESE                  leitura plausível, ainda não arbitrada
PENDÊNCIA DE DOMÍNIO      ninguém respondeu
REGRA DE FABRICAÇÃO       confirmada E conferida contra janela real
```

**Valor desconhecido não vira informação.** `None` significa "não informado" e
nunca é lido como zero, como string vazia nem como um default plausível; papel
não confirmado é `NAO_CONFIRMADO`; regra sem evidência fica `PENDENTE` com
`expressao=None`; ficha sem identificador fica com `identificador=None` — nunca
`CASO_A_PEQUENO`.

Um `0` — ou um identificador chutado — no lugar de um desconhecido produziria
um dado inventado com aparência de resposta, e o erro só apareceria no alumínio
já cortado.

### Quatro palavras que não são sinônimas

```text
campo preenchido   alguém escreveu algo na ficha
decisão confirmada valor + estado confirmado + fontes_ids existentes +
                   autoria, quando a decisão é do especialista
regra aprovada     decisão confirmada + fórmula + evidência
caso validado      registro estruturado de validação com resultado APROVADO
```

A CLI conta as duas primeiras separadamente, de propósito: tratar preenchimento
como confirmação faria um rascunho virar ordem de corte.

Regra confirmada **sem fonte** é recusada na construção. Decisão de
especialista sem autoria — responsável, data e referência — reprova o gate de
cálculo, valha ela para componente, regra dimensional, regra de acessório ou
aprovação final.

### Evidência é citada por ID, nunca por tipo

Cada fonte tem `id_fonte` obrigatório e único (`FONTE-[A-Z0-9_-]+`); cada
afirmação cita as suas em `fontes_ids`. Tipos podem se repetir — duas fotos são
duas fontes —, IDs não. Fonte sem ID **reprova**: gerar um automaticamente
inventaria a identidade da evidência.

Um índice por tipo fazia a segunda fonte do mesmo tipo sobrescrever a primeira,
e a afirmação não dizia a qual das duas se referia.

**Fonte existente não é fonte apta.** O estado da fonte precisa sustentar o
estado da afirmação:

```text
CONFIRMADO_CATALOGO             catálogo ou tabela de fabricação
CONFIRMADO_BIBLIOTECA_OFICIAL   manifesto de promoção ou biblioteca oficial
CONFIRMADO_ESPECIALISTA         especialista de domínio, com autoria completa
CONFIRMADO_CASO_REAL            medição, foto, croqui, lista real, software
DERIVADO_DE_REGRA_APROVADA      evidência da regra aprovada correspondente
```

Não é uma escala numérica: cada confirmação tem natureza própria. Uma foto não
confirma cota de catálogo, e um catálogo não prova o que foi medido numa janela
real. Nenhuma fonte citada pode estar `PENDENTE` ou `HIPOTESE`, e ao menos uma
tem de ser compatível. Afirmação confirmada com evidência incompatível vira
**erro visível**, não some da lista de confirmações.

### Cada afirmação carrega o seu estado e a sua evidência

`caso_real`, `vista`, cada perfil e cada item de `cortes`, `vidros`,
`baguetes`, `acessorios`, `folgas` e `sobreposicoes` têm `estado` e
`fontes_ids` próprios. Uma fonte solta no fim do documento **não** confirma
seção nenhuma.

Croquis são evidência visual, não decisão dimensional: ficam com `tipo`,
`referencia` e `descricao`, e viram `FonteEvidencia` com `id_fonte` próprio
quando alguém quiser citá-los. Duas representações do mesmo fato — uma com
estado e outra sem — entrariam em conflito.

### REPROVADO nunca é aprovação

`AprovacaoEspecialista.resultado` é um enum: `APROVADO`, `REPROVADO`,
`REVOGADO`. Antes, a mera existência do registro abria o portão, e um parecer
negativo abriria o mesmo portão que um positivo.

O gate de produção exige **exatamente uma** aprovação por escopo, com resultado
`APROVADO`. Duas aprovações do mesmo escopo bloqueiam: conflito não se resolve
pela ordem da lista.

A aprovação cita a evidência por `fonte_id`, resolvido no **registro central**
da receita (`indice_fontes_receita`). Carregar o objeto da fonte permitia
aprovar com evidência que não existe em lugar nenhum. A fonte tem de estar
registrada, ser `especialista_de_dominio`, estar `CONFIRMADO_ESPECIALISTA`, ter
autoria completa, e bater em responsável e data com a aprovação.

### Caso validado exige integridade E validação

`bool(caso.cortes)` aceitava uma tupla com objetos vazios: o gate abria porque
a lista não estava vazia, sem uma única peça descrita.
`validar_integridade_caso_real()` confere item a item — campos mínimos, estado
e evidência apta:

```text
dimensões    largura, altura, estado confirmado e fontes compatíveis
cortes       perfil (do microlote oficial), comprimento, quantidade, evidência
vidros       folha, largura, altura, espessura, evidência
demais       campos mínimos da categoria, estado e evidência
```

Item parcial continua guardado no caso como dado recebido — o que ele não pode
é ser contado como prova para produção. E aprovar a validação **não** salva um
caso incompleto: integridade dos dados e validação estruturada são necessárias
ao mesmo tempo.

### Caso validado tem registro estruturado

`VALIDADO` deixou de ser uma string que qualquer código podia escrever. Ele é
**derivado** de uma `ValidacaoCasoReal` com resultado `APROVADO`, responsável,
data real e fontes existentes. Os estados de recebimento continuam sendo
`AGUARDANDO_DADOS`, `RECEBIDO_PARCIAL` e `RECEBIDO_NAO_VALIDADO` — e nenhum
deles pode ser escrito como `VALIDADO`.

### Modelos são profundamente imutáveis

`frozen=True` congela os atributos do dataclass, não o conteúdo de um `dict`.
`dados_adicionais` é congelado na construção — cópia recursiva com
`MappingProxyType`, `tuple` e `frozenset` —, então alterar o dicionário
original depois não muda o registro, e mutar o conteúdo do modelo falha.
`para_dict()` devolve uma cópia nova e mutável: mexer nela não afeta o modelo.

### Datas são datas de verdade

`2026-02-30` parece uma data e não é. A validação usa o calendário real, não só
o formato — vale para fontes, aprovações e validações de caso.

---

## 5. Gates

```text
visualização preliminar   ABERTO
    aceita papéis pendentes, desde que a receita se declare preliminar e
    todas as referências geométricas resolvam na biblioteca oficial

cálculo                   BLOQUEADO
    exige todos os componentes confirmados (papel, quantidade, orientação,
    fonte e autoria), todas as regras dimensionais com fórmula confirmada, e
    todas as regras de ACESSÓRIO com quantidade e posição confirmadas

produção                  BLOQUEADO
    exige o gate de cálculo aberto; os TRÊS casos canônicos
    (CASO_A_PEQUENO, CASO_B_MEDIO, CASO_C_GRANDE), sem duplicata, com medidas
    completas, lista de corte, vidros e fonte, e com dimensões distintas entre
    si; e duas aprovações estruturadas do especialista — da receita e das
    fórmulas — cada uma com responsável, data, escopo e evidência
```

Acessórios entram no gate de cálculo: uma lista de fabricação completa em
perfis e vidro, e silenciosa sobre quantas roldanas a janela leva, não é lista
de fabricação.

Três casos com as mesmas medidas não distinguem constante de proporção — por
isso as dimensões têm de ser diferentes, e o mesmo caso repetido três vezes não
conta como três.

Estado atual: nenhum papel confirmado, nenhuma regra dimensional confirmada,
nenhuma regra de acessório confirmada, nenhum caso real recebido.

Os gates existem para que "ainda não sabemos" seja uma resposta possível do
sistema. Sem eles, a única saída seria inventar um número.

---

## 6. O que depende do especialista

Nada abaixo pode ser deduzido do que já existe no repositório:

1. Qual perfil cumpre cada papel (marco superior, inferior, laterais, travessas
   e montantes de folha, encontro central, mão-de-amigo, baguete).
2. Quantas peças de cada perfil entram numa janela de duas folhas.
3. A orientação de corte de cada peça.
4. O desconto de corte de cada perfil em relação à medida de vão.
5. As folgas de montagem — entre folha e marco, e entre as duas folhas.
6. A sobreposição no encontro central.
7. Como o vidro é dimensionado a partir da folha.
8. Quais acessórios entram, em que quantidade e em que posição.
9. Qual folha corre no trilho interno e qual no externo, vista de que lado.
10. Onde fica o fecho e qual o sentido de movimento de cada folha.

---

## 7. Formato esperado da ficha

Modelo em `composicao/insumos/suprema_2f_modelo_preenchimento.yaml`.

Regras de preenchimento:

- campo que você não souber: **deixe em branco** — em branco vira pendência;
- nunca escreva `0`, `n/a` ou um chute para preencher espaço;
- medidas em milímetros; datas em `AAAA-MM-DD`;
- `fonte` diz **como** você sabe: catálogo, medição física, especialista,
  lista de corte real, software externo, foto, croqui, tabela de fabricação,
  manifesto de promoção, biblioteca oficial;
- caminho de foto ou croqui sempre **relativo** à raiz do repositório —
  caminho absoluto (`/home/...`, `C:\...`) e travessia com `..` são recusados,
  porque a evidência precisa sobreviver ao clone em outra máquina; para algo
  que não é arquivo, declare `forma_referencia: identificador_externo` ou `url`;
- a ficha é **versionada** (`versao_ficha: 1`); versão desconhecida é recusada
  em vez de lida com significado errado;
- nome de campo com erro de digitação **reprova**, com sugestão do nome certo:
  `largura_totall_mm` seria uma medida perdida em silêncio, e a ficha pareceria
  completa.

O conversor **preserva todas as seções**: vista, perfis, cortes, vidros,
baguetes, acessórios, folgas, sobreposições, croquis, fontes e dúvidas. Nada do
que a visita produziu é descartado.

**Política de dados adicionais**, uma só e explícita:

```text
campo desconhecido FORA de dados_adicionais         reprova
conteúdo DENTRO de dados_adicionais                 preservado, sem interpretação
```

`dados_adicionais` é um mapeamento e existe na raiz e em cada afirmação. Nada
ali participa de cálculo, e o relatório marca esse conteúdo como não
interpretado. "Qualquer campo é preservado" seria conveniente e perigoso: um
`largura_totall_mm` guardado em silêncio faria a ficha parecer completa.

Uma ficha só com folgas medidas e fotos já conta como `RECEBIDO_PARCIAL` — ela
trouxe dado de campo real. Os estados são:

```text
AGUARDANDO_DADOS       nada preenchido
RECEBIDO_PARCIAL       trouxe dado, mas falta medida, corte ou identificação
RECEBIDO_NAO_VALIDADO  identificada, com medidas, lista de corte e vidros
VALIDADO               conferida e aceita como prova
```

Copie o modelo antes de preencher (um arquivo por janela real) e valide:

```bash
python -m composicao.cli validar-ficha composicao/insumos/suprema_2f_caso_a.yaml
```

O comando lista, separadamente, o que foi respondido e o que continua pendente.

Três casos são esperados: `CASO_A_PEQUENO`, `CASO_B_MEDIO`, `CASO_C_GRANDE`.
Um caso só não permite distinguir uma constante de uma proporção.

---

## 8. Checklist da visita à serralheria

Gerado pelo comando `prontidao --markdown`. Em resumo: fotos com escala,
medidas do vão e do produto acabado, **lista de corte real peça a peça**,
descontos aplicados, folgas medidas nos quatro lados, sobreposição central,
medidas do vidro e folga de encaixe, encaixe da baguete nos dois lados,
acessórios com quantidade e posição, trilho de cada folha, sentido de
movimento, posição do fecho, e o croqui do serralheiro mesmo rabiscado.

---

## 9. Próximos passos, depois dos dados

1. Transcrever a ficha preenchida e validar a estrutura.
2. Atribuir os papéis funcionais com fonte e autoria.
3. Registrar cada caso real com sua lista de corte.
4. **Derivar** fórmulas candidatas a partir dos casos — marcadas `HIPOTESE`,
   nunca aprovadas automaticamente.
5. Submeter cada fórmula à arbitragem do especialista.
6. Conferir a fórmula aprovada contra os três casos reais.
7. Só então abrir o gate de cálculo.

O gate de produção continua fechado até que o cálculo reproduza, sem
divergência, as listas de corte das janelas realmente fabricadas.

---

## 10. O que esta rodada deliberadamente NÃO fez

Nenhum desconto de corte, medida de vidro, folga, sobreposição, quantidade de
acessório, posição definitiva de perfil ou desenho oficial da janela.

Não porque faltou tempo — porque inventar qualquer um deles produziria um
número com aparência de resposta.
