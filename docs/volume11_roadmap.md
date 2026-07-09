# Volume 11 — Roadmap

---
**Versão:** 1.0.0
**Status:** Estável (atualizado incrementalmente conforme Sprints avançam)
**Sprint de origem:** originado nas fases de planejamento inicial, consolidado no
Sprint A
**Última atualização:** 2026-07-08
**ADRs relacionados:** todos
**Implementação correspondente:** Fases 0-4 já concluídas; Sprints A-F em andamento
**Dependências:** Volume 1 (Visão Geral), Volume 3 (Modelo de Domínio)
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** nenhum (Volume consolidador, topo da árvore)
---

## Situação em uma linha

**Nota do Claude:** corrigido após observação real do ChatGPT — este quadro estava
desatualizado (dizia Sprint B/C pendentes quando os Volumes 9 e 10 já existiam).

| Situação | Status |
|---|---|
| Fases Técnicas (0-4) | Concluídas |
| Sprint Atual | Sprint C concluído — aguardando decisão sobre Sprint D |
| Próximo Sprint | Sprint D (Providers) |
| Estado Geral | Consolidação documental concluída; implementação retomando |

## Estado Geral (indicador visual)

**Nota do Claude:** separado Documentação de Implementação — antes uma única
barra escondia que Volumes 9 e 10 já estão escritos mesmo sem código
correspondente ainda.

```
                     Documentação   Implementação
Arquitetura          ██████████     ██████████
Pipeline             ██████████     ██████████
Domínio              ██████████     ██████████
Providers            ██████░░░░     █░░░░░░░░░
Validações           ██████████     ░░░░░░░░░░
Testes               ██████████     ░░░░░░░░░░
Renderer Comercial   ███░░░░░░░     ███░░░░░░░
```

# Roadmap Técnico

## Eixo histórico — Fases de validação técnica (concluídas)

| Fase | Objetivo | Status |
|---|---|---|
| Fase 0 | Core Engine com dados manuais (prova de conceito do pipeline completo) | ✓ Concluída |
| Fase 1 | Parser real conectado à Linha 25 (Centenário) | ✓ Concluída |
| Fase 2 | Teste do parser sem modificação na Linha 30 (mesmo fabricante) | ✓ Concluída |
| Fase 3 (Sprint 4) | Teste em fabricante diferente (Euroshow) + relatório comparativo | ✓ Concluída |
| Sprint de Intercambiabilidade | Confirmação da hipótese de Linha-Padrão (Alcoa, Vitral Sul) | ✓ Concluída |

## Eixo atual — Sprints de consolidação (em andamento)

| Sprint | Objetivo | Volumes afetados | Status |
|---|---|---|---|
| Sprint 0 | Constituição da Documentação | — | ✓ Concluído |
| Sprint A | Documentação oficial | 1, 2, 3, 4, 6, 7, 11 | ✓ Concluído |
| Sprint B | Validações de domínio | 9 | ✓ Concluído |
| Sprint C | Testes automatizados | 10 | ✓ Concluído |
| Sprint D | Expansão dos Providers | 5 | Próximo — aguardando decisão do Bruno |
| Sprint E | Biblioteca Oficial de Geometrias | 8 | Pendente |
| Sprint F | Integração com Renderer real e sistema comercial | — | Pendente |

# Roadmap Comercial

## Fases de produto (visão de médio prazo, registradas no plano original)

- **MVP:** Core Engine + 1 linha de 1 fabricante funcionando ponta a ponta —
  concluído nas Fases 0-1.
- **Alpha:** múltiplas linhas, múltiplos fabricantes, classificação assistida por
  IA com revisão humana, Vista explodida — em andamento (Sprints D, E).
- **Beta:** multi-fabricante maduro, compatibilidades como entidade completa,
  integração com sistema de orçamento existente, Renderer com qualidade visual de
  produção (Three.js) — depende de ambiente com acesso à rede para implementar o
  motor de renderização definitivo.
- **Comercial:** robustez, performance, parcerias formais com fabricantes (ver nota
  legal abaixo), avaliação de exportação técnica real (DXF preciso, STEP) apenas se
  a demanda aparecer.

## Nota registrada sobre uso de material de fabricantes (relevante para Beta/Comercial)

Distinção arquitetural em vigor: **Material de Referência** (PDF original, SVG
extraído, layout, textos) existe apenas para alimentar o Pipeline de Aquisição e
para auditoria técnica — nunca é distribuído ao cliente final. O produto comercial
trabalha exclusivamente com o **Modelo Paramétrico Próprio** (geometria homologada,
propriedades, regras, compatibilidades), do qual são derivadas todas as
imagens/vistas/documentação. Antes do lançamento comercial, recomenda-se consulta
formal com advogado de propriedade industrial, e busca-se priorizar parcerias
diretas com fabricantes.

## O que NÃO fazer nas próximas fases (disciplina já estabelecida)

- Não introduzir novas entidades de arquitetura sem evidência concreta (Constituição
  da Documentação, Regra 1).
- Não implementar kernel CAD/STEP — decisão consciente já tomada, fora de escopo
  atual.
- Não construir Providers (OCR, DXF, DWG) sem demanda real de um fabricante que
  exija especificamente aquele formato.
- Não automatizar classificação funcional ou isolamento de contorno antes de ter
  volume de dados que justifique o investimento (ver Sprint de Intercambiabilidade).

## Evolução futura registrada (não criada agora)

- **Volume 12 — Estudos de Caso:** cada grande descoberta (Centenário, Euroshow,
  Alcoa, Vitral Sul) documentada como estudo de caso (problema, hipótese,
  investigação, decisão, ADR originado). Transformaria a documentação numa base de
  conhecimento da indústria, não só do software. Registrado como possibilidade
  futura, não criado nesta versão — aguarda material suficiente acumulado.

## Próxima ação concreta

Iniciar o Sprint D (Providers — OCR para os casos Alcoa/Vitral Sul já mapeados)
quando houver decisão do Bruno de retomar implementação. A documentação v1.0 está
congelada como baseline; próximas alterações documentais só por evidência de
implementação (novos ADRs) ou pelos itens do backlog quando alguém precisar deles.
