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

### 13. Evidência — nada inventado (CORRIGIDO, ver adendo)

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


---

# ADENDO — rodada de correção de proveniência (2026-08-09)

Auditoria aprovou a estrutura e mandou corrigir a semântica da fonte + três
arbitragens. HEAD anterior `8b6396e` → novo HEAD `771e25c`.

## Arquivos alterados

```text
composicao/receita.py
curadoria/handoffs/e4e/topologia_suprema_2f.md
tests/test_receita_suprema.py
```

`modelos.py` e `validar.py` **não foram tocados** — o contrato de fontes não
foi ampliado.

## Como FONTE-TOPOLOGIA-E4E passou a ser classificada

`TIPOS_DE_FONTE` não tem tipo de arbitragem, e a ordem foi não ampliar o schema
só por isso. Mantido `especialista_de_dominio` / `CONFIRMADO_ESPECIALISTA` — o
tipo mais honesto disponível, porque afirma **"um especialista decidiu"**, não
"existe foto provando". Não virou `foto`, `medicao_fisica`, `croqui` nem
`software_externo`. A correção foi de **texto e estado semântico**, não de tipo.

## Distinção registrada, em texto

Arbitragem derivada, na `descricao` da fonte:

> "REGISTRO DERIVADO DE ARBITRAGEM DE DOMÍNIO, não evidência física primária.
> […] O hash prova a integridade DESTE documento e quais decisões ele registra
> — não prova a composição física de nenhuma janela."

Primárias pendentes, na mesma `descricao`:

> "Evidências primárias (três janelas reais, quadro sem folhas, ficha de campo,
> fotografias, benchmarks externos): PENDENTE DE INGESTÃO DAS EVIDÊNCIAS
> PRIMÁRIAS — ausentes do repositório, sem path, sem hash e sem id_fonte nesta
> rodada."

O documento abre com uma seção 0 dizendo o que o hash prova e o que não prova,
e a pendência também entra em `perguntas_abertas`, aparecendo no relatório de
prontidão.

## Hash do handoff

```text
a2134ed8c1c01c9e4f6b78ecb783cb1804dd64a16556f2273d47b7f7f68fcd45   8607 bytes
```

Teste recalcula e falha se o documento mudar sem a fonte mudar junto —
verificado adicionando um byte ao arquivo.

## Baguetes — nomes finais

```text
SUPREMA_CORRER_2F:FOLHA-INTERNA:BAGUETE-HORIZONTAL-1    posicao = None
SUPREMA_CORRER_2F:FOLHA-INTERNA:BAGUETE-HORIZONTAL-2    posicao = None
SUPREMA_CORRER_2F:FOLHA-INTERNA:BAGUETE-VERTICAL-1      posicao = None
SUPREMA_CORRER_2F:FOLHA-INTERNA:BAGUETE-VERTICAL-2      posicao = None
SUPREMA_CORRER_2F:FOLHA-EXTERNA:BAGUETE-HORIZONTAL-1    posicao = None
SUPREMA_CORRER_2F:FOLHA-EXTERNA:BAGUETE-HORIZONTAL-2    posicao = None
SUPREMA_CORRER_2F:FOLHA-EXTERNA:BAGUETE-VERTICAL-1      posicao = None
SUPREMA_CORRER_2F:FOLHA-EXTERNA:BAGUETE-VERTICAL-2      posicao = None
```

`superior`/`inferior`/`lateral` saíram. `-1` e `-2` desambiguam ocorrência e
nada mais.

## Plano interno / externo — definição documentada

```text
PLANO_INTERNO   plano da folha mais próximo do ambiente INTERNO da edificação
PLANO_EXTERNO   plano da folha mais próximo do EXTERIOR da edificação
```

Profundidade da esquadria em relação a dentro/fora do edifício. Não é
esquerda/direita, não é o lado de quem olha a foto, não é sentido de abertura —
e por isso sobrevive ao espelhamento. Sem offset, sem distância entre planos.

## Testes

Oito novos, nenhum removido:

```text
test_fonte_da_topologia_nao_se_apresenta_como_evidencia_primaria
test_documento_de_arbitragem_declara_a_propria_natureza
test_nenhuma_evidencia_primaria_foi_inventada
test_pendencia_de_ingestao_esta_visivel_na_receita
test_identificadores_de_baguete_nao_gravam_lateralidade
test_sufixo_numerico_do_baguete_nao_afirma_ordem
test_convencao_de_plano_esta_documentada
test_plano_e_profundidade_nao_lado
```

## Resultado

```text
tests/test_receita_suprema.py   443 passed   (era 435)
suíte completa                  940 passed   EXIT=0   (era 932)
git diff --check                limpo
```

Nenhum git rodou em paralelo com pytest.

## Gates finais

```text
visualização preliminar   ABERTO
cálculo                   BLOQUEADO   17 bloqueios
producao                  BLOQUEADO
```

Os 17: 9 regras sem fórmula, 6 acessórios sem quantidade/posição, 1 receita
ainda preliminar, 1 gate sem raiz do repositório. Nenhum deles é "falta
topologia" — e nenhum deles some por causa dela.

## Novos gaps

1. **Posição do baguete dentro da folha** ficou explicitamente não declarada.
   Entra como pergunta aberta: qual do par é o de cima, e se isso chega a
   importar para corte.
2. **Ingestão das primárias** é a próxima rodada. Quando os artefatos entrarem,
   cada afirmação de topologia precisa passar a citar a fonte primária
   correspondente — hoje todas citam a arbitragem.
3. **Persistência da receita** segue registrada como possibilidade futura, não
   como defeito: nada foi implementado, conforme arbitrado.
