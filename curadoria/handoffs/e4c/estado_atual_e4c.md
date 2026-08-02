# EsquadriaCore — estado atual do E.4C

Documento durável. Não registra branch, PR nem hashes de commit — esses são
transitórios. A execução da sprint fica na seção histórica ao final.

---

## Objetivo

Promover para a biblioteca oficial (`dados/`) os oito perfis fechados na
curadoria do E.4B, de forma validada, transacional, idempotente e auditável.

Promover **não** é recurar: nenhum contorno foi redesenhado, simplificado ou
recalculado. O que a curadoria aprovou é copiado ponto a ponto.

---

## Base de origem

Microlote E.4B, oito perfis fechados, nenhuma pendência dimensional restante.
SU-102 e TMS-102 confirmados como o mesmo perfil físico.

---

## Os oito perfis promovidos

| perfil | ID oficial | associação | dimensão (mm) | pontos | vazios |
|---|---|---|---:|---:|---:|
| SU-001 | `GEO-SU-001` | `ALCOA-SU-001` | 71,00 × 33,00 | 187 | 0 |
| SU-002 | `GEO-SU-002` | `ALCOA-SU-002` | 71,00 × 47,00 | 163 | 0 |
| SU-003 | `GEO-SU-003` | `ALCOA-SU-003` | 71,00 × 26,00 | 83 | 0 |
| SU-039 | `GEO-SU-039` | `ALCOA-SU-039` | 52,60 × 25,00 | 126 | 1 |
| SU-040 | `GEO-SU-040` | `ALCOA-SU-040` | 42,40 × 30,70 | 82 | 1 |
| SU-041 | `GEO-SU-041` | `ALCOA-SU-041` | 42,40 × 33,00 | 93 | 1 |
| SU-053 | `GEO-SU-053` | `ALCOA-SU-053` | 22,20 × 51,00 | 163 | 0 |
| SU-102 | `GEO-SU-102` | `ALCOA-SU-102` | 17,00 × 15,00 | 87 | 0 |

Todas em `nivel_contorno: 2_renderizavel_comercial` — renderizável comercial,
**não** é CAD e **não** autoriza fabricação.

### Por que o prefixo ALCOA

`SU-xxx` é o namespace de código da Alcoa: as associações preexistentes provam
a convenção (`ALCOA-SU-005` ao lado de `CENTENARIO-TMS-005`). Que o *desenho*
de alguns perfis tenha vindo do card Centenário não muda o namespace do
código — são coisas distintas, e a procedência guarda a fonte real do desenho.

Nenhuma associação foi criada para outros fabricantes. Fazer isso afirmaria
intercambiabilidade entre fabricantes que **não foi curada** para estes oito
perfis (ADR-004).

---

## Procedência

A cota de sete perfis vem de catálogo. A do SU-102 não:

```yaml
SU-102:
  leitura_fisica_mm:   [16.9, 15.0]
  dimensao_nominal_mm: [17.0, 15.0]
  origem_dimensional:  MEDICAO_FISICA_COM_NOMINALIZACAO_POR_DOMINIO
  gate_aspecto_fisico_bruto: REPROVADO   # 0,952% contra limite de 0,75%
  gate_aspecto_nominal:      APROVADO    # 0,366%
  decisao: APROVADO_POR_ARBITRAGEM_DE_DOMINIO_COM_NOMINALIZACAO
```

A cota oficial é a **nominal**. O valor bruto medido continua registrado no
manifesto e na nota da geometria — quem passou no gate foi o nominal, e isso
não é escondido.

---

## SU-102 × TMS-102

```yaml
identidade_de_perfil: CONFIRMADA
tms102_medido_separadamente: false
geo_tms102_criado: false
associacao_tms102_criada: false
```

São o mesmo perfil físico. A dimensão vale para os dois por identidade de
produto, não por medição independente.

Nenhuma geometria duplicada foi criada. Como `TMS-102` **não existe** como
entidade de perfil na biblioteca oficial, nenhuma associação foi criada para
ele nesta sprint — criá-la seria inventar uma entidade. Se o TMS-102 for
cadastrado no futuro, deve apontar para `GEO-SU-102`, nunca para uma
geometria nova.

---

## Mecanismo transacional

`curadoria/promocao/` é o único ponto do repositório autorizado a escrever em
`dados/`, e só sob `--apply` explícito. O caminho de aquisição continua
proibido de tocar os caminhos oficiais.

Fluxo: carrega → valida os oito → simula em memória → confere idempotência →
copia backup → grava temporários **no mesmo filesystem** → relê os
temporários → substitui os destinos com `os.replace` → relê os destinos →
valida pós-gravação → gera manifesto.

Em qualquer falha depois do início da escrita, **ambos** os arquivos são
restaurados e os hashes conferidos contra os originais antes de reportar
sucesso do rollback. Nunca fica estado parcial.

```bash
python -m curadoria.promocao.cli diagnosticar --lote E4B
python -m curadoria.promocao.cli simular      --lote E4B
python -m curadoria.promocao.cli promover     --lote E4B --apply
python -m curadoria.promocao.cli verificar    --lote E4B
```

### Idempotência

Confirmada **em disco**, não só em memória: promover de novo produz diff
vazio, hashes inalterados, oito IDs reconhecidos como já promovidos.

### Rollback

Coberto por regressão com falha **injetada** em três pontos distintos: depois
do primeiro temporário, entre os dois `os.replace`, e na validação
pós-gravação. Cada caso confere que os dois arquivos voltaram ao hash original
e que nenhum ficou com JSON parcial. Um teste que só percorresse o caminho
feliz não provaria nada.

---

## Estado final de `dados/`

```yaml
geometrias:  46 -> 54
associacoes: 245 -> 253
registros_antigos_alterados: 0
associacoes_orfas: 0
diff: puramente aditivo (0 deleções)
```

A ausência de alteração nos registros anteriores é conferida por hash canônico
registro a registro, não por inspeção visual.

O arquivo é gravado na **mesma indentação** em que estava. A primeira tentativa
usou o default do serializador e reformatou 24 mil linhas — um diff assim
esconderia qualquer alteração real de geometria. Há regressão travando isso.

---

## Limitações

1. **Nível 2, não CAD.** As geometrias são renderizáveis comercialmente. Não
   autorizam fabricação, corte nem cálculo de vidro.
2. **Um fabricante por perfil.** Só `ALCOA-SU-xxx`. Equivalência com outros
   fabricantes exigiria curadoria própria, perfil a perfil.
3. **TMS-102 sem entidade.** Ver seção acima.
4. **Nenhuma receita de tipologia.** A biblioteca tem as peças; não sabe montar
   a janela. Folgas, descontos de corte e posição funcional continuam
   indefinidos.
5. **SU-040 vem do lote 1.** Estado `CANDIDATO_PREVIAMENTE_APROVADO`, artefatos
   no layout legado. Foi promovido a partir do artefato aprovado, sem
   reprocessamento.

---

## Próxima etapa recomendada

A receita de tipologia da janela de correr Suprema (E.4D), que depende de
decisões de domínio ainda não tomadas:

- qual perfil cumpre cada papel na janela;
- folgas de montagem;
- descontos de corte;
- regra de dimensionamento do vidro.

Nada disso pode ser inferido dos catálogos ou da geometria. Depende do
especialista.

---

## Histórico da execução (fica obsoleto — não é estado)

Sprint E.4C, executada em 2026-08-02 sobre a `main` no merge do PR #4.
Suíte na conclusão da sprint: 119 testes de promoção, 204 de aquisição,
37 do contrato, **383 no total**, `EXIT_CODE=0`.
