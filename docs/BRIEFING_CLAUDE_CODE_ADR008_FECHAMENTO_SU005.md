# BRIEFING — Formalização ADR-008 + Fechamento GEO-SU-005

> Enviado pelo Bruno em 2026-07-12. Insumo anexo: arquivo
> `ADR-008_geometriapadrao_contorno_externo_vazios_internos.md`
> (versão consolidada pelo ChatGPT — é o insumo da Etapa 1 deste briefing).

## Aprovações registradas

- Contorno do GEO-SU-005 (iteração 11): **aprovado visualmente pelo Bruno**.
- ADR-008: **aprovado pelo ChatGPT**, condicionado à inclusão da frase de salvaguarda
  (já presente no arquivo anexo).
- Este briefing: aprovado pelo Bruno.

---

## ETAPA 0 — Verificação prévia (antes de escrever qualquer coisa)

1. **Nomes reais dos campos:** conferir em `domain/`, `dados/geometrias.json`,
   `core_engine/` e `tests/` se os campos são `contorno_externo`/`vazios_internos`
   ou `contorno_externo_mm`/`vazios_internos_mm`.
   **O ADR usa os nomes que o código já usa.** Não renomear por estética — se
   necessário, apenas explicar no texto do ADR que as coordenadas são em milímetros.
   Reportar ao Bruno qual nomenclatura foi encontrada.
2. **Estrutura real da documentação:** conferir se existe Volume 10 (Testes) em
   `docs/`. Os adendos devem referenciar apenas volumes que existem no repositório.
   Priorizar a estrutura real do repo sobre qualquer suposição.
3. **Nome do arquivo de evidência:** confirmar o nome real do arquivo/imagem da
   iteração 11 aprovada (para preencher o campo `evidencia_contorno`).

---

## ETAPA 1 — ADR-008 (usar o arquivo anexo como base → status Aceito)

O arquivo anexo já contém a estrutura completa. Ajustes obrigatórios ao gravar a
versão final em `docs/` (substituindo o rascunho `adr008_perfil_oco.md` ou
renomeando conforme a convenção do repo):

1. **Nomes de campo:** ajustar o documento inteiro para os nomes reais
   verificados na Etapa 0.
2. **Limpar seções transitórias:** após a verificação de nomes, REMOVER do ADR a
   "Observação de nomenclatura" (dentro de Decisão) e a seção "Encaminhamento" —
   são instruções de execução, não decisão arquitetural. Um ADR aceito não carrega
   instruções condicionais ("se o código usar X, ajustar este documento").
3. **Status simples:** o campo Status deve ser apenas `Aceito`. A condição já está
   expressa na frase de salvaguarda logo abaixo (que deve permanecer):
   > "A validação do ADR-008 não implica homologação automática das geometrias
   > individuais que utilizam esse modelo."
4. A salvaguarda aparece duas vezes no anexo (Status e Conclusão) — manter nas duas.

---

## ETAPA 2 — Adendos (NUNCA alterar os volumes congelados da v1.0)

Criar `docs/adendos/` com arquivos novos, referenciando os volumes REAIS
encontrados na Etapa 0:

- `adendo_volume3_geometriapadrao_perfil_oco.md` — evolução da entidade
- `adendo_volume7_renderer_vazios_internos.md` — extrusão com furos
  (ajustar o número se o volume do Renderer for outro no repo)
- `adendo_volume9_validacoes_contornos_com_vazios.md` — validações do novo formato
- Adendo de testes apenas SE o volume de Testes existir; caso contrário,
  incorporar o conteúdo ao adendo de validações.

Cada adendo abre com a frase:
"Este adendo complementa o Volume N da documentação v1.0 (congelada) sem alterá-lo.
Origem: ADR-008."

Conteúdo dos adendos: usar as seções "Impacto no Core Engine", "Impacto nas
validações" e "Impacto nos testes" do ADR anexo como fonte.

---

## ETAPA 3 — Fechamento GEO-SU-005 em dados/geometrias.json

- Gravar contorno externo + vazios internos definitivos (iteração 11 aprovada).
- Campos (NÃO misturar equivalência com contorno — são eixos independentes):
  - `status_geometria`: `homologada` (já era — equivalência validada na curadoria
    Suprema; não alterar semântica)
  - `nivel_contorno`: `2_renderizavel_comercial`
  - `status_contorno`: `validado_visualmente`
  - `metodo_contorno`: `contorno_externo_vazios_internos`
  - `evidencia_contorno`: [nome real do arquivo confirmado na Etapa 0.3]
- **Apenas o GEO-SU-005.** As outras 45 geometrias permanecem `bruto_aproximado` —
  nenhuma alteração de nível em lote.

---

## ETAPA 4 — Método de curadoria fina (docs/plano_de_curadoria.md)

Registrar como procedimento padrão para os próximos contornos:

1. Claude Code gera seção 2D olhando a evidência `_lado_a_lado.png`
2. Bruno marca correções por cor sobre a imagem + legenda textual
3. Imagem marcada vai para `curadoria/feedback/` (versionada, nunca apagada —
   evidência de auditoria)
4. Claude Code corrige olhando a imagem marcada diretamente
5. Iterações versionadas, sem sobrescrever anteriores
6. Validação visual final do Bruno
7. Gravação somente após aprovação explícita
8. Atualizar `nivel_contorno` e `status_contorno` após a gravação

---

## ETAPA 5 — Testes, regeneração e fechamento

1. Implementar as validações do novo formato (lista no ADR, seção "Impacto nas
   validações").
2. Implementar os testes novos (lista no ADR, seção "Impacto nos testes"), com uma
   correção importante no item 8:
   **A "regressão do GEO-SU-005 iteração 11" deve ser regressão de DADOS, não de
   imagem** — verificar número de vazios internos, quantidade de pontos do contorno,
   áreas, contenção dos vazios. NÃO comparar imagens pixel a pixel (frágil: quebra
   com versão do matplotlib, fontes, DPI).
3. Regenerar a extrusão 3D do GEO-SU-005.
4. Regenerar `curadoria/biblioteca_curadoria.xlsx`.
5. Rodar a suíte completa (`pytest tests/ -v`) — rede de segurança obrigatória,
   tudo verde antes do commit.
6. Atualizar CHANGELOG.md.
7. Commit + push. Sugestão de mensagem:
   `ADR-008 aceito: perfil oco + GEO-SU-005 contorno renderizavel comercial`

---

## Critério de conclusão

A tarefa termina com um REPORT ao Bruno contendo:

- nomenclatura de campos encontrada no código (Etapa 0.1);
- volumes reais referenciados nos adendos (Etapa 0.2);
- nome do arquivo de evidência usado (Etapa 0.3);
- confirmação de que as seções transitórias foram removidas do ADR final;
- resultado da suíte de testes;
- hash do commit.

O Bruno leva esse report ao ChatGPT para fechar o ciclo de revisão.
