# Backlog — Melhorias Editoriais Futuras

*Este backlog existe fora dos Volumes estáveis, propositalmente. Nenhum item aqui
muda arquitetura ou domínio — são melhorias de apresentação/navegação, sem
prioridade definida, a serem puxadas quando fizer sentido (nunca como justificativa
para reabrir um Sprint já encerrado).*

- Diagramas Mermaid (substituindo os blocos de texto ASCII atuais)
- Imagens e exemplos ilustrados (ex: a imagem real gerada pelo Core Engine)
- Hyperlinks internos entre Volumes
- Referências cruzadas automáticas (ADR ↔ Volume ↔ Entidade)
- IDs permanentes por entidade (DOM-001, DOM-002...) — já registrado como
  evolução futura no Volume 3
- Glossário oficial (Volume 12 ou anexo) — já registrado como evolução futura
  no Volume 11
- Volume 12 — Estudos de Caso — já registrado como evolução futura no Volume 11
- v2.0: reduzir duplicação de explicação entre ADR-002 e Volume 7 (Renderer) via
  referência cruzada única, em vez de reafirmar o mesmo conteúdo em dois lugares
- v2.0: mover as "Notas do Claude" espalhadas pelos Volumes para um anexo/histórico
  editorial único, deixando o texto principal mais enxuto — só depois que a
  documentação atingir maturidade ainda maior (essas notas hoje têm valor de
  registrar a discordância no momento em que ela ocorreu)

## Itens de longo prazo (v2.0/v3.0, explicitamente não agora)

**Volume 8 subdividido (8A-8E)** quando crescer demais — registrado para quando o
Volume 8 (ainda não escrito, Sprint E) existir de fato e revelar se precisa mesmo
de subdivisão. Não decido isso antecipadamente sem o conteúdo real na frente.

**Volume 0 — Visão Executiva** (10 páginas, para investidor/novo colaborador não-
técnico) — ideia razoável, mas o próprio ChatGPT enquadrou como "não agora, quando
o projeto crescer". Concordo com o adiamento.

**ADR futuro sobre Pipeline determinístico** (mesmo Provider + mesmo catálogo =
mesmo resultado) — nota do Claude: não crio esse ADR agora porque ADR documenta
decisão com evidência real, e isso hoje é presunção razoável, não algo que já
precisou ser decidido contra uma alternativa concreta. Registro aqui como
candidato a ADR-008 quando (e se) o determinismo do Pipeline vira uma decisão de
verdade — ex: se aparecer necessidade de cache/paralelismo que dependa disso.

**Versão "oficial" sem atribuição** (remover "Nota do Claude", "ChatGPT sugeriu",
"Bruno observou" do texto principal, movendo para anexo/histórico de repositório).
Nota do Claude: concordo com o raciocínio (daqui a 5 anos importa a decisão, não
quem propôs) mas discordo do timing. Reescrever todos os Volumes agora para remover
atribuição significaria manter duas versões em paralelo enquanto o conteúdo ainda
muda a cada rodada — dobrando custo de edição por benefício que só se realiza
quando a documentação parar de mudar de fato. As notas de atribuição hoje têm valor
operacional real: permitem a qualquer um dos três rastrear por que uma decisão foi
tomada, no momento em que isso ainda importa para decidir a próxima. Revisitar essa
limpeza quando o projeto sair da fase de consolidação ativa (pós Sprint D/E).



**Carta de Princípios do EsquadriaCore** — documento curto (1-2 páginas) acima da
própria Constituição, com princípios permanentes e atemporais (ex: "conhecimento é
mais importante que implementação", "geometria é a fonte de verdade", "fabricantes
são provedores de conhecimento, não proprietários do modelo interno"). Diferença
de propósito: a Constituição organiza *como* a documentação é mantida; a Carta
explicaria *por que* o projeto existe. Nota do Claude: o próprio ChatGPT enquadrou
isso como "não agora, talvez v2.0 ou v3.0" — concordo integralmente com o adiamento.
Boa parte do conteúdo sugerido já está coberto pela Tese do EsquadriaCore (Volume 1)
e pelos Princípios Fundamentais (Volume 1) — a Carta seria uma consolidação
posterior desses dois, não conteúdo genuinamente novo hoje.

**Volume 12 — Arquitetura Física do código** (apps/, packages/, providers/, etc.) e
**Convenções de Código** (Interfaces, Repositories, DTOs, naming, imports
proibidos): o ChatGPT propôs ambos. Nota do Claude: recusado por agora, não por
serem ideias ruins — porque hoje não existe repositório de código real além dos
protótipos desta conversa (Fase 0, parser de Linha 25/30, prova de conceito de
GeometriaPadrao). Documentar estrutura de pastas e convenções de implementação
antes de existir um repositório de produção real seria a mesma generalização
prematura que a Regra 1 existe para evitar — organização de código nasce de
código real crescendo, não de antecipação. Retomar quando o projeto migrar de
protótipo para repositório de desenvolvimento contínuo.

**Volume 2 — visão física** (Providers → Pipeline → Banco → Core Engine →
Renderer → Aplicações): recusado por dois motivos concretos. (1) Pressupõe um
"Banco" que ainda não foi escolhido/implementado — documentar isso agora seria a
mesma antecipação sem repositório real que já recusamos para o Volume 12
(Arquitetura Física). (2) É redundante com o diagrama "Camadas de valor" já
adicionado ao Volume 1 (Mercado → Conhecimento → Pipeline → Domínio → Core Engine
→ Produtos) — mesma ideia, dois lugares.

**"Patrimônio Técnico" como conceito formal novo**: recusado por ser redundante —
já é exatamente o que a camada "Conhecimento" do diagrama do Volume 1 descreve
(FamíliaMercado, GeometriaPadrao, Compatibilidades, Regras...). Criar um terceiro
nome para a mesma coisa (depois de "Biblioteca de Conhecimento" e "Conhecimento")
aumentaria confusão de vocabulário, não clareza.

**Volume de Convenções de Dados** (nomenclatura de IDs como GEO-0001/PER-0001,
convenção de unidades, versionamento v1/v2/deprecated): recusado pelo mesmo motivo
já registrado para Volume 12 e para a "visão física" do Volume 2 — pressupõe um
esquema de geração de ID e persistência real que ainda não existe. Os IDs usados
até agora nesta conversa (`GEO-SU-019`, `ALCOA-SU-019`) são ad-hoc, criados pra
provar o conceito, não uma convenção formal de produção. Formalizar isso antes de
haver banco de dados real seria decidir um detalhe de implementação sem o
implementador na mesa. Retomar junto com o Sprint que de fato escolher a
tecnologia de persistência.

## Regra de uso deste backlog

Qualquer item aqui só é implementado quando alguém precisar dele de verdade (ex:
um novo colaborador se perdeu por falta de link cruzado) — não por antecipação.
Mesma disciplina de evidência aplicada ao domínio, aplicada agora à forma da
documentação.
