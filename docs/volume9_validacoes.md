# Volume 9 — Validações de Domínio

---
**Versão:** 1.0.0
**Status:** Estável (especificação validada — implementação ainda não existe, ver
cabeçalho "Implementação correspondente")
**Sprint de origem:** Sprint B
**Última atualização:** 2026-07-08
**ADRs relacionados:** ADR-003, ADR-004, ADR-005
**Implementação correspondente:** ainda não codificado — este Volume é a
especificação; a implementação (validators por entidade) é o próximo passo natural,
não coberto aqui
**Dependências:** Volume 3 (Modelo de Domínio)
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** 10
---

## Objetivo

Definir as regras de consistência que cada entidade do domínio deve respeitar,
antes de existir volume real de importação que torne erros silenciosos caros.

## Nota do Claude (registrada, não uma pergunta em aberto)

Este Volume documenta **regras**, não implementa **enforcement**. Construir um
framework de validação automática agora, sem volume real de dados para validar
contra, seria o mesmo padrão de over-engineering que já evitamos em outras
decisões (ex: Providers sem demanda, Aggregate Roots sem persistência). A
implementação de código das validações abaixo só se justifica quando o Sprint D
(expansão de Providers) trouxer volume de importação que realmente precise disso.
Sigo com a especificação porque ela é barata e útil por si só (serve de contrato
para quem for implementar depois) — não estou propondo construir o validator agora.

---

## Perfil

- fabricante: obrigatório, não nulo.
- codigo_fabricante: obrigatório, único dentro do mesmo fabricante (não único
  globalmente — o mesmo código, ex: "SU-019", existe legitimamente em fabricantes
  diferentes, confirmado pelo caso real Alcoa/Vitral Sul).
- peso_kg_m: obrigatório; se não numericamente válido, marcar `peso_suspeito`
  (nunca descartar o registro, ver ADR-006/007 e o caso real Euroshow).
- categoria: obrigatória antes do estado "Curado" no fluxo de vida (Volume 3) —
  pode ficar em aberto em "Extraído"/"Normalizado".
- familia_mercado_id: opcional; se ausente, não impede nenhuma etapa do fluxo de
  vida.

## GeometriaPadrao

- contorno_mm: obrigatório; deve ser um polígono fechado (primeiro ponto = último
  ponto, ou fechamento implícito consistente).
- unidade: sempre milímetros — nunca outra unidade sem conversão explícita na
  entrada.
- versao: obrigatória, incremental.
- status: obrigatório (bruto_aproximado | homologado) — só pode ser referenciada
  por um Perfil em produção quando `homologado`.
- svg_bruto_ref: opcional, mas recomendado (auditoria/proveniência).

## PerfilGeometria

- perfil_id e geometria_padrao_id: ambos obrigatórios, referência deve existir.
- só pode apontar para uma GeometriaPadrao com status `homologado` (nota do Claude:
  isso não estava explícito antes — a prova de conceito usou `bruto_aproximado`
  deliberadamente para provar o pipeline; em produção real essa regra deve ser
  respeitada de fato, o exemplo já implementado é uma exceção documentada, não o
  padrão).
- responsavel_homologacao: obrigatório.
- nivel_de_confianca: obrigatório, um de um conjunto fechado (ex: alto/médio/baixo)
  — nunca texto livre, para permitir filtragem/relatório.

## FamíliaMercado

- nome_canonico: obrigatório, único.
- aliases_conhecidos: cada alias deve referenciar um fabricante existente; sem
  duplicidade de (fabricante, prefixo_codigo).

## Componente

- categoria: obrigatória.
- orientação: obrigatória, um de (vertical | horizontal | ambos).

## Tipo

- regra_aplicada: obrigatória (mesmo que hoje seja texto livre — ver observação no
  Volume 3 sobre "Regra" ainda não ser entidade formal).
- componentes: lista não pode ser vazia.

## Cena Técnica

- toda instância deve referenciar um componente_id existente — nunca dado
  embutido (é a regra mais importante deste Volume, ela é o que torna o ADR-001 e
  ADR-002 verificáveis por código, não só por convenção).
- posicao_mm, rotacao_graus, comprimento_mm: obrigatórios e numéricos.

## Vista

- cena_id: obrigatório, deve referenciar Cena Técnica existente.
- tipo_projecao: obrigatório, um de um conjunto fechado (frontal | isometrica |
  explodida | corte).

## Índice de qualidade por Perfil — formalizado como Value Object `QualidadePerfil`

**Nota do Claude:** o ChatGPT sugeriu virar entidade própria; concordo com a
substância (evita espalhar essa lógica em cada Provider) mas ajusto a forma —
`QualidadePerfil` é um **Value Object embutido no Perfil**, não uma entidade com
identidade e ciclo de vida próprios. Diferença prática: não tem `id`, não é
referenciada por outras entidades, existe só como atributo composto do Perfil que
a contém. Isso mantém a régua já aplicada às observações de Aggregate
Root/Value Objects no Volume 3 (só formalizar quando houver necessidade concreta) —
aqui a necessidade já existe (múltiplos Providers vão calcular a mesma coisa), o
que diferencia este caso dos ainda especulativos.

```
QualidadePerfil (Value Object, sem identidade própria)
  - codigo_valido: bool
  - peso_valido: bool
  - vetor_encontrado: bool
  - descricao_encontrada: bool
  - escala_identificada: bool
  - indice: int (0-5, soma dos campos acima)
  - prioridade_revisao: string (derivada do índice, ex: "revisar_primeiro" se
    indice <= 2) — nota do Claude: renomeado de "status" após observação correta
    do ChatGPT de que o Perfil já tem um status no fluxo de vida (Volume 3); dois
    campos chamados "status" com significados diferentes seria fonte de confusão
```

Cada Perfil extraído possui exatamente um `QualidadePerfil`. Índice baixo prioriza
revisão humana.

**Nota do Claude:** não proponho fórmula de peso diferenciado por indicador (ex:
"peso vale mais que descrição") — isso é decisão de produto/domínio que só Bruno
deveria calibrar depois de ver o índice funcionando contra volume real de dados.
Registrar aqui como pergunta em aberto, não decisão pendente de mais discussão de
arquitetura: a fórmula simples (soma) é suficiente para começar.

## Modelo de Erros (especificação, não implementação)

**Nota do Claude:** o ChatGPT apontou corretamente uma lacuna real — Validação
(Volume 9, acima) previne estado inválido; Erro é o que acontece quando algo já
falhou em tempo de execução. São conceitos diferentes e este Volume só cobria o
primeiro. Adicionando agora, como lista fechada de tipos esperados (não como
hierarquia de exceções em código — isso é implementação, fora de escopo deste
Volume):

- `GeometryNotFound` — PerfilGeometria aponta para GeometriaPadrao inexistente.
- `InvalidProfile` — Perfil falha nas validações estruturais acima.
- `InvalidFamily` — FamíliaMercado referenciada não existe.
- `MissingComponent` — Cena Técnica referencia Componente inexistente (o erro que
  torna o ADR-001 verificável em runtime, não só em revisão de código).
- `ProviderFailure` — Provider não conseguiu extrair dado da fonte (ex: OCR falhou).
- `PipelineFailure` — **categoria residual**: exclusivamente para falhas de
  orquestração não enquadradas em nenhuma das categorias anteriores. Não usar como
  atalho genérico — se uma falha se repete e tem causa identificável, ela merece
  categoria própria.
- `RendererFailure` — Renderer não conseguiu produzir imagem a partir da Vista.

## Sobre "Modelo de Eventos" (não adotado — já coberto)

**Nota do Claude:** o ChatGPT também sugeriu documentar o Pipeline como eventos
(`PerfilExtraido`, `PerfilNormalizado`, `GeometriaHomologada`...). Considero isso já
coberto pelo "Fluxo de vida do Perfil" no Volume 3 (`Extraído → Normalizado →
Curado → Homologado → Disponível → Obsoleto`) — são a mesma informação, só que
descrita como estados em vez de eventos discretos. Não vejo motivo para duplicar em
dois formatos diferentes sem uma necessidade concreta (ex: fila de mensagens, event
sourcing real) que hoje não existe. Se o Pipeline evoluir para arquitetura orientada
a eventos de fato, este Volume é o lugar certo para essa mudança — não antes.

---

## Próxima ação concreta

Sprint C (Volume 10 — Testes), usando os Invariantes do Domínio (Volume 3) e as
validações acima como especificação direta dos casos de teste unitário. Sigo para
esse rascunho já no próximo arquivo, sem esperar aprovação intermediária, salvo se
o Bruno ou o ChatGPT sinalizarem discordância de algum ponto acima.
