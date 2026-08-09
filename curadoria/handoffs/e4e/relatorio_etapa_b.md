# E.4E — Topologia da Suprema 2 folhas · relatório para auditoria

Data: 2026-08-09 · Branch: `sprint-e4e-topologia-suprema-2f` (local, **não** enviada)
Base: `dd1abaf` (merge da PR #7, main)

---

## Etapa A — fechamento da E.4D (concluída)

PR #7 mergeada normal (não squash), main fast-forwarded, commit de higiene é
ancestral de main. Coleta 895 · `test_receita_suprema.py` 398 passed · suíte
completa **895 passed, EXIT=0**. Branches apagadas local e remoto,
`fetch --prune` feito. Sem tag, sem release, sem force. Zero symlinks
rastreados no repositório.

---

## Etapa B — 17 itens

### 1. Auditoria antes de tocar no schema

Reinspecionados `PapelComponente`, `ComponenteReceita`, `ReceitaTipologia`
(incluindo `COLECOES`), `validar_cobertura_estrutural_receita` e
`validar_prontidao_para_visualizacao`. Achado que mudou o plano: **a receita
não tem `para_dict()` e nunca é serializada em disco** — quem vai para YAML é
a ficha de campo. Ver item 14.

### 2. Extensão do schema — aditiva, sem migração destrutiva

| adicionado | onde |
|---|---|
| `PapelComponente.MARCO_LATERAL` | `modelos.py` |
| `PapelComponente.MONTANTE_CENTRAL_FOLHA` | `modelos.py` |
| `TipoRelacaoComponentes.ENCONTRO_CENTRAL` | `modelos.py` |
| `RelacaoEntreComponentes` | `modelos.py` |
| `ReceitaTipologia.relacoes` + entrada em `COLECOES` | `modelos.py` |
| `PAPEIS_DE_QUADRO`, `PAPEIS_ESTRUTURAIS_DE_FOLHA`, `PAPEIS_DE_BAGUETE` | `modelos.py` |

**Nada foi removido.** `MARCO_LATERAL_ESQUERDO`, `MARCO_LATERAL_DIREITO`,
`MAO_DE_AMIGO` e `PapelComponente.ENCONTRO_CENTRAL` continuam no enum, com
comentário dizendo que ficam por compatibilidade. Teste dedicado
(`test_papeis_antigos_continuam_disponiveis`).

### 3. Quadro — 4 ocorrências

```text
QUADRO-SUPERIOR    SU-001  MARCO_SUPERIOR   horizontal
QUADRO-INFERIOR    SU-002  MARCO_INFERIOR   horizontal
QUADRO-LATERAL-1   SU-003  MARCO_LATERAL    vertical
QUADRO-LATERAL-2   SU-003  MARCO_LATERAL    vertical
```

Identificadores distintos, **mesmo papel neutro**. `folha=None`: quadro não
pertence a folha.

### 4. Espelhabilidade

Esquerda/direita não existe em lugar nenhum da receita. Há teste que varre
identificador, posição, folha e observações de todos os 20 componentes
procurando "esquerd"/"direit" e falha se achar
(`test_nenhum_componente_grava_lateralidade`).

### 5. Folhas — mesma estrutura, montante central diferente

```text
PLANO_INTERNO    SU-039 lateral · SU-040 central · SU-053 sup · SU-053 inf
PLANO_EXTERNO    SU-039 lateral · SU-041 central · SU-053 sup · SU-053 inf
```

Só dois planos, e a contagem bate com `quantidade_folhas`.

### 6. Mão de amigo é perfil, não ferragem

SU-040 e SU-041 entram com papel `MONTANTE_CENTRAL_FOLHA` — posição
estrutural. `MAO_DE_AMIGO` não é usado por nenhuma ocorrência, e nenhum item
de acessório menciona "amigo". Testado.

### 7. Encontro central — relação, não peça

```text
SUPREMA_CORRER_2F:FOLHA-INTERNA:MONTANTE-CENTRAL   (SU-040)
        ↕ ENCONTRO_CENTRAL
SUPREMA_CORRER_2F:FOLHA-EXTERNA:MONTANTE-CENTRAL   (SU-041)
```

Não é terceira peça, não é papel de peça, não está em `observacoes` (testado
nos três eixos). Cita **identificadores de ocorrência**, nunca códigos de
perfil — teste confirma que nenhum participante é um código `SU-xxx`.

### 8. Baguetes — 8, distinguíveis

SU-102 ×8: por folha, 2 horizontais + 2 verticais. Papel `BAGUETE`, e os três
frozensets de papéis são disjuntos entre si, então contar estrutural nunca
inclui acabamento:

```text
12 estruturais + 8 baguetes = 20 ocorrências
```

### 9. Perfil não é peça

`{SU-001:1, SU-002:1, SU-003:2, SU-039:2, SU-040:1, SU-041:1, SU-053:4,
SU-102:8}` — 8 perfis no inventário, 20 peças na janela. Identificadores
únicos.

### 10. Validação da relação — na construção

Recusa: tipo fora do vocabulário · participante vazio · participante repetido
· aridade errada (`ENCONTRO_CENTRAL` é binário: 0, 1 ou 3 participantes são
recusados).

### 11. Validação da relação — contra a receita

`validar_relacoes_da_receita()`, chamada de dentro de
`validar_cobertura_estrutural_receita` (logo, pelos três gates). Recusa:
referência fantasma · relação duplicada · participantes na mesma folha ·
evidência que não sustenta o estado da relação.

**Verificado por mutação:** removi a chamada do validador e os 5 testes
correspondentes falharam; restaurada, voltaram a passar. Não são testes que
passam por acidente.

### 12. Imutabilidade

`participantes` e `fontes` congelados por `como_tupla` na construção (mutar a
lista de origem depois não afeta a relação); `relacoes` congelada pelo
`COLECOES` da receita com checagem de tipo elemento a elemento; atribuição
depois da construção levanta erro. Padrão idêntico ao das outras coleções.

### 13. Evidência — nada inventado

`FONTE-TOPOLOGIA-E4E`, tipo `especialista_de_dominio`, estado
`CONFIRMADO_ESPECIALISTA`, responsável Bruno, data 2026-08-09, apontando para
`curadoria/handoffs/e4e/topologia_suprema_2f.md` — **arquivo que existe no
repositório**, com sha256 e tamanho reais:

```text
85ac6f8862cbeee70b51d661a810e8fe9eea2360c01ffc305a04dc111cec9407   5122 bytes
```

O teste recalcula o hash do arquivo e falha se o documento mudar sem a fonte
mudar junto. Nenhum hash, path ou artefato foi inventado, e nenhuma validação
foi relaxada.

### 14. Round-trip YAML — o que foi provado e o que não foi

`RelacaoEntreComponentes.para_dict()` → `yaml.safe_dump` → `safe_load` →
reconstrução → **igual ao original**, incluindo as fontes embutidas. A
topologia inteira (20 componentes) também sobrevive ao round-trip.

**Ressalva honesta:** hoje a `ReceitaTipologia` não é persistida em YAML —
só a ficha de campo é. O contrato de serialização da relação está provado em
si mesmo, não através de um schema de arquivo que ainda não existe. O schema
da ficha **não foi alterado** nesta rodada.

### 15. Testes

```text
tests/test_receita_suprema.py   435 passed   (era 398)
suíte completa                  932 passed   EXIT=0   (era 895)
```

37 testes novos. Nenhum comando git rodou em paralelo com as suítes —
`test_extrair_nao_escreve_em_disco` continua intacto e passando.

**10 testes atualizados**, os que gravavam o invariante da E.4D
(`componentes == ()`). Eles agora gravam o invariante da E.4E: topologia
conhecida, dimensional pendente. O que o gate de cálculo exigia continua
testado — `test_bloqueia_calculo_sem_ocorrencias_funcionais` roda sobre uma
receita sem ocorrências, e um teste novo confirma que a topologia registrada
**não** é o que abre o gate.

### 16. Gates

```text
visualização preliminar   ABERTO
cálculo                   BLOQUEADO   16 bloqueios, todos por falta de fórmula
produção                  BLOQUEADO
```

Antes o cálculo era bloqueado *também* por "nenhuma ocorrência funcional".
Esse motivo saiu porque foi respondido; o gate continua fechado pelo motivo
certo. Registrar topologia não é calcular.

### 17. Escopo — o que ficou de fora

Nenhuma medida, fórmula, folga, tolerância, arredondamento, offset entre
planos, regra de vidro, regra de baguete, roldana, fecho, escova ou acessório.
Nada de L-32, H-5, H-55, (L-132)/2, VidroSys ou Wvetro — `git diff` da branch
inteira não casa com nenhum desses termos. Renderer, UI e integrações
intocados. Perguntas dimensionais seguem abertas (desconto, folga,
sobreposição, vidro, acessório — testado).

---

## Estado da entrega

Dois commits na branch local:

```text
e7bdb1e  feat(composicao): papel lateral neutro e relação tipada entre componentes
2b1221e  feat(composicao): registra a topologia da Suprema de correr 2 folhas
```

**Sem push, sem PR, sem merge, sem tag, sem release.** Parado para auditoria.

## Gaps e decisões que pedem tua arbitragem

1. **Persistência da receita** — a relação atravessa YAML, mas a receita nunca
   é gravada. Se a topologia precisar sair do código para arquivo, isso é uma
   rodada própria (schema de persistência da receita, não da ficha).
2. **Posição do baguete** — registrei `superior/inferior/lateral-1/lateral-2`
   por folha. Se a tua convenção de fabricação nomeia diferente, é troca de
   rótulo, não de estrutura.
3. **Convenção de "interno"** — a receita diz interno/externo sem dizer visto
   de que lado. Deixei como pergunta aberta em vez de fixar uma convenção.
