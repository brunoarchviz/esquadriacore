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

**Valor desconhecido não vira número.** `None` significa "não informado" e
nunca é lido como zero; papel não confirmado é `NAO_CONFIRMADO`; regra sem
evidência fica `PENDENTE` com `expressao=None`.

Um `0` no lugar de um desconhecido produziria uma peça com medida errada sem
nenhum aviso — o erro só apareceria no alumínio já cortado.

Regra confirmada **sem fonte** é reprovada. Decisão de especialista sem autoria
registrada é reprovada.

---

## 5. Gates

```text
visualização preliminar   ABERTO
    aceita papéis pendentes, desde que a receita se declare preliminar e
    todas as referências geométricas resolvam na biblioteca oficial

cálculo                   BLOQUEADO
    exige todos os componentes confirmados (papel, quantidade, orientação,
    fonte) e todas as regras com fórmula confirmada e evidência

produção                  BLOQUEADO
    exige o gate de cálculo aberto, três casos reais validados
    (pequeno, médio e grande) e aprovação registrada do especialista
```

Estado atual: 0 de 8 papéis confirmados, 0 de 9 regras dimensionais
confirmadas, 0 casos reais recebidos.

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
- medidas em milímetros;
- `fonte` diz **como** você sabe: catálogo, medição física, especialista,
  lista de corte real, software externo, foto, croqui, tabela de fabricação;
- caminho de foto ou croqui sempre **relativo** à raiz do repositório.

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
