# EsquadriaCore — correção transacional do PR #5

Documento autocontido. Estado em 2026-08-02.

Os quatro bloqueadores da auditoria de execução foram corrigidos na branch
`sprint-e4c-promocao-oficial-suprema`. Nenhum PR novo, nenhum merge, nenhuma
tag, nenhum release, nenhum force.

---

## 1. `CONFIG_FINALIZADO` era só um rótulo

**Era assim.** `_finalizacao_auditavel()` gravava o manifesto e avançava direto
para `CONFIG_FINALIZADO` sem escrever o config, usando o objeto `cfg` carregado
antes da transação. Passava na branch viva porque o config já estava promovido.
Partindo do estado real de uma promoção, `promocao_oficial_realizada: false`
nunca viraria `true`.

**Agora.** `curadoria/promocao/config_promovido.py` traz
`construir_config_promovido_e4b(config_antes, candidatos)` — função **pura**:
trabalha sobre cópia profunda, não altera o objeto recebido, não lê disco, é
idempotente.

Ela marca os oito perfis como `PROMOVIDO`, preenche os oito IDs GEO e os oito
`perfil_id_oficial`, marca `promocao_oficial_realizada: true`,
`lote_promocao: E4C`, mantém `pendencia_restante: null`, corrige as notas de
estado atual e **preserva o histórico** movendo o texto anterior para blocos
`historico_pre_promocao` datados.

Nada é apagado. E ela recusa sobrescrever qualquer nota cujo texto não seja nem
o pré-promoção conhecido nem o já promovido — não sobrescreve edição que
ninguém revisou.

**A prova mais forte:** partindo do config do commit `53fcfac` (pré-promoção), a
função gera **byte a byte** o arquivo publicado.

```python
gerado == CAMINHO_CONFIG.read_text()   # True
```

SU-102 continua preservando leitura física 16,9 × 15,0, cota nominal
17,0 × 15,0, a arbitragem de domínio, a identidade SU-102 = TMS-102 e
`tms102_medido_separadamente: false`.

---

## 2. O rollback cobria só dois arquivos

**Era assim.** Depois que o journal existia, qualquer exceção caía em
`restaurar_backup(backups)` — e esses backups temporários só abrangiam
`dados/geometrias.json` e `dados/perfil_geometria.json`. Manifesto gravado +
verificação falhando depois = manifesto novo permanece no disco, e o journal
(única coisa capaz de desfazer os quatro) era apagado em seguida.

**Agora.** Existe **um** mecanismo de rollback.

```text
antes do journal   apagar temporários; nenhum destino foi modificado
depois do journal  o journal é a ÚNICA autoridade
```

O caminho pós-journal executa preflight completo, restaura os quatro artefatos,
confere todos os hashes anteriores, **remove** o artefato que não existia antes
(o manifesto da primeira promoção), e só limpa journal e backups depois de
confirmar. Rollback que falha não limpa nada.

`criar_backup_temporario` e `restaurar_backup` foram removidos — dois mecanismos
concorrentes eram o problema, não a solução.

---

## 3. Journal sem hash final de config e manifesto

**Era assim.** `journal.preparar()` aceitava hashes esperados para os quatro
papéis, mas a transação só passava os de geometrias e associações. Os campos
`hash_esperado_depois` de config e manifesto ficavam `null`: o journal conhecia
os quatro caminhos e não sabia confirmar o conteúdo final de nenhum dos dois.

**Agora.** Os **quatro** documentos são construídos em memória e hasheados
**antes** do primeiro `os.replace`. `preparar()` recusa qualquer papel sem hash
final. Nenhum dos quatro fica `null`.

O manifesto continua descrevendo o evento canônico — `46 → 54`, `245 → 253` —
e não a simulação viva.

---

## 4. A retomada não retomava estado nenhum

**Era assim.** Para qualquer estado de `DADOS_VALIDOS` em diante, `cmd_recuperar()`
carregava o config atual, reconstruía o manifesto, rodava o verificador e
limpava o journal. Não gravava o config, não passava pelos marcos e não usava o
estado encontrado para decidir nada. Um journal `CONCLUIDA` era apagado sem
conferir coisa alguma.

**Agora**, em `curadoria/promocao/finalizacao.py`:

```text
DADOS_VALIDOS        grava manifesto → grava config → verifica → conclui → limpa
MANIFESTO_GRAVADO    grava config → verifica → conclui → limpa
CONFIG_FINALIZADO    verifica → conclui → limpa
VALIDACAO_UNIFICADA  repete a verificação → conclui → limpa
CONCLUIDA            confere os quatro hashes e a verificação ANTES de limpar
```

Cada marco só avança **depois** que a gravação aconteceu e bateu com o hash
prometido pelo journal.

A retomada reconstrói os quatro documentos pela mesma função pura e exige que
os hashes batam com o journal. Se não baterem — ou se o recibo divergir dos
fatos canônicos de `evento.py` — ela recusa **sem tocar em nada**: journal
preservado, backups preservados, zero arquivos alterados.

---

## Endurecimento do journal

Validado no carregamento: exatamente os quatro papéis; nenhum caminho absoluto;
nenhum `..`; todos os destinos resolvem dentro da raiz; hashes com 64 hex; hash
final presente para os quatro; recibo completo; estado pertencente à máquina de
estados.

O preflight confere, antes de qualquer mutação: backups necessários, hashes dos
backups, hashes dos destinos compatíveis com o estado (nem o anterior nem o
esperado = edição externa, bloqueia) e recibo canônico. A conferência dos
documentos finais reconstruídos vive na retomada, onde os documentos existem.

A limpeza sincroniza **cada** diretório de onde removeu backup — `dados/`,
`curadoria/aquisicao/configs/` e `curadoria/promocoes/e4c/` — não só `dados/`.

---

## Resíduo documental corrigido

O handoff dizia que uma reconstrução marca `reconstruido_apos_gravacao`. Falso.
Agora diz: reconstrói fisicamente o arquivo, mas preserva
`reconstruido_apos_gravacao: false`, porque o campo pertence ao evento canônico
e não à operação de recuperação.

---

## Testes

```text
472 passed, 0 falhas, 0 pulados
```

Novos, além dos que já existiam:

- **Falha injetada na finalização** em quatro pontos — depois de gravar o
  manifesto, depois de gravar o config, durante a verificação unificada e
  depois dela. Cada caso prova que geometrias, associações e config voltam ao
  hash anterior e que o manifesto (que não existia) é removido.
- **Caso obrigatório**: manifesto não existia → é gravado → verificação
  unificada falha → manifesto removido, todo o resto restaurado.
- **Crash sem `except` nos oito marcos**, de `PREPARADA` a `CONCLUIDA`, com uma
  recuperação nova para cada um: rollback dos quatro antes de `DADOS_VALIDOS`,
  retomada determinística dali em diante, validação antes da limpeza em
  `CONCLUIDA`.
- **Teste integral** numa árvore isolada materializada do commit `53fcfac`:
  46 geometrias, 245 associações, config com `promocao_oficial_realizada: false`,
  manifesto ausente. Ao final: 54/253, config promovido, manifesto canônico
  `46 → 54`, verificação unificada aprovada, zero journal, zero backups. A
  árvore isolada reproduz **byte a byte** os hashes publicados do evento. Uma
  segunda execução não muda nada.
- **Journal inválido** recusado em sete mutações; alteração externa de destino
  durante a janela da transação bloqueia; recibo divergente bloqueia.

O config pré-promoção **reprova** a verificação unificada — isso está provado
por teste. Sem essa prova, o teste integral não significaria nada.

---

## O que NÃO mudou

A parte geométrica, o manifesto canônico e os fatos históricos continuam como
estavam. `domain/`, `contrato/`, `docs/`, `VERSION` e `CHANGELOG.md` intactos.

Uma diferença honesta no manifesto: os `avisos` deixaram de listar
`id_ja_promovido_identico: GEO-SU-xxx` oito vezes. Aqueles avisos eram resíduo
de o manifesto ter sido reconstruído sobre dados já promovidos; construído a
partir da simulação real do evento, a lista é vazia — que é o valor correto
para o que aconteceu.

---

## Continua valendo

O mecanismo **não** promete commit atômico conjunto. Dois `os.replace`
sequenciais não são um. A consistência do conjunto vem do journal, da
recuperação e da finalização retomável — e agora essas três coisas fazem, de
verdade, o que o journal e a documentação dizem que fazem.

---

# Segunda rodada — compatibilidade futura e fechamento

Três pontos corrigidos depois da aprovação da implementação transacional.

## A. Evento histórico separado de integridade atual

`verificar_integridade_promocao_e4b()` exigia que os arquivos vivos tivessem
exatamente o hash e a contagem do fim do E.4C. Uma promoção futura legítima
acrescenta registros e muda o hash global — e passaria a ser lida como
corrupção.

Agora são duas funções:

```text
verificar_evento_historico_e4c(manifesto)
    46 → 54, 245 → 253, hashes canônicos, oito IDs, oito associações,
    commits, data e versão. Não olha para o disco.

verificar_permanencia_atual_e4b(config, geometrias, associacoes, candidatos)
    os oito GEOs presentes, contornos idênticos ponto a ponto, dimensões,
    vazios, oito associações corretas, config declarando PROMOVIDO,
    GEO-TMS-102 ausente.
```

A unificada soma as duas. A permanência **permite** geometrias e associações
novas não relacionadas, contagens acima de 54/253 e hash global diferente do
histórico.

A transação não afrouxou: durante a promoção ou recuperação ativa, o journal
continua exigindo os quatro hashes finais exatos.

Provado por teste: com `GEO-FUTURO-001` e `FABRICANTE-FUTURO-001` adicionados
(55/254), a verificação do E.4B **aprova**. Alterar um ponto do SU-001, remover
o SU-041, apontar `ALCOA-SU-053` para outro GEO, alterar a dimensão do SU-102,
criar `GEO-TMS-102` ou mexer no fato histórico `46 → 54`: todas **reprovam**.

## B. Reconstrução do manifesto virou comando explícito

O caminho silencioso dentro de `promover` decidia sucesso só porque os oito GEOs
existiam. `promover` agora recusa e aponta:

```bash
python -m curadoria.promocao.cli reconstruir-manifesto --lote E4B --apply
```

O comando confirma ausência de journal pendente, recusa sobrescrever manifesto
existente, valida config/dados/associações **sem depender do manifesto**,
confirma os oito registros e as oito associações, grava por temporário +
`fsync` + `os.replace`, relê, roda a verificação unificada e **remove o
manifesto recém-criado** se ela reprovar. `dados/` e config nunca são tocados.

Bloqueiam, com manifesto continuando ausente e zero outros arquivos alterados:
config ainda não promovido, associação errada, GEO ausente, contorno alterado,
`GEO-TMS-102` criado.

## C. `CONCLUIDA` é o ponto de commit

Alcançado `CONCLUIDA`, a promoção está confirmada. Falha ao apagar backup, ao
remover o journal ou no `fsync` final **não** dispara rollback: seria trocar um
resultado verificado por uma reversão, por causa de arquivo auxiliar que ninguém
consome.

```text
promoção confirmada     → tentar limpeza
limpeza falhou          → limpeza_pendente=True, quatro artefatos preservados
recuperar (próxima vez) → confere os quatro hashes, repete a verificação
                          unificada, termina a faxina, nunca reverte
```

`aplicar_promocao_transacional()` lê o journal antes de decidir rollback: em
`CONCLUIDA` não reverte. A CLI informa e sai com código 3.

O teste antigo que chamava `journal.limpar()` direto após um `CONCLUIDA`
abandonado passou a usar o fluxo de retomada — chamar `limpar()` direto provaria
apenas que `unlink` funciona.

## Testes desta rodada

```text
229 em tests/test_promocao.py (eram 204)
```

Novos: geometria e associação futuras aprovadas; seis mutações de registro do
E.4B reprovadas; fato histórico mutado reprovado enquanto a permanência atual
continua aprovada (são perguntas diferentes); comando de reconstrução em caso
íntegro, exigindo `--apply`, recusando sobrescrever e bloqueando cinco estados
incoerentes; falha de limpeza em três pontos (backup, journal, `fsync`) sem
desfazer a promoção, com a recuperação seguinte terminando a faxina e
revalidando antes de apagar.
