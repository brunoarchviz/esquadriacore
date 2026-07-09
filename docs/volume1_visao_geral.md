# Volume 1 — Visão Geral

---
**Versão:** 1.0.0
**Status:** Estável
**Sprint de origem:** Sprint A
**Última atualização:** 2026-07-08
**ADRs relacionados:** ADR-001, ADR-006
**Implementação correspondente:** N/A (documento de visão, não de código)
**Dependências:** Constituição da Documentação v1.0.0
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** 2, 11
---

## Objetivo da Plataforma

O EsquadriaCore transforma o conhecimento técnico fragmentado da indústria de
esquadrias de alumínio — hoje disperso em catálogos PDF de dezenas de fabricantes,
cada um com sua própria convenção — em um domínio estruturado, reutilizável e
independente de fabricante. A partir desse domínio, a plataforma gera automaticamente
representações técnicas e comerciais (imagens, vistas, planilhas) para uso em
orçamento, documentação e apresentação.

## O que o EsquadriaCore não é

Esclarecimentos negativos, registrados porque cada um foi uma decisão explícita
tomada ao longo do projeto, não uma omissão:

- **Não é um sistema CAD de fabricação.** Não gera sólidos precisos para manufatura,
  não exporta STEP para CNC. Gera representação visual técnica e comercial.
- **Não é um leitor de PDF genérico.** PDF é um dos Providers possíveis de aquisição
  de dados, não o núcleo do sistema.
- **Não é apenas um gerador de imagens.** A imagem é a saída visível, mas o ativo
  real é o conhecimento estruturado por trás dela (geometria homologada,
  compatibilidades, regras de montagem, famílias de mercado).

## Anti-objetivos (consolidado — nota do Claude)

O ChatGPT sugeriu reunir num único lugar tudo que o projeto explicitamente evita,
hoje espalhado em ADRs e Volumes diferentes. Consolidando aqui, com referência
cruzada para não duplicar a justificativa:

- Substituir CAD / gerar STEP / gerar CNC — ver seção acima e Volume 7.
- Armazenar imagem como fonte de verdade — ADR-001.
- Depender exclusivamente de PDF — ADR-003.
- Assumir compatibilidade técnica só por pertencer à mesma FamíliaMercado — ADR-004.
- Inferir geometria automaticamente sem curadoria humana — ADR-005.
- Automatizar isolamento de contorno ou classificação funcional antes de haver
  volume de dados que justifique — Volume 11, seção "O que NÃO fazer".
- Construir Aggregate Roots/Value Objects/entidade Regra sem evidência de
  necessidade real — Volume 3, observações registradas.

## Filosofia

Três decisões filosóficas atravessam toda a plataforma:

1. **Evidência antes de arquitetura.** Nenhuma entidade de domínio existe porque
   parecia elegante — toda entidade hoje no domínio nasceu de um problema real
   encontrado em dados reais (catálogos de Centenário, Euroshow, Alcoa, Vitral Sul).
2. **Geometria é a única fonte de verdade.** Nenhuma imagem é armazenada; toda
   imagem é derivada de geometria.
3. **Separação entre conhecimento e implementação.** Existe uma arquitetura do
   software (Core Engine, Renderer, Pipeline) e uma arquitetura do conhecimento
   (FamíliaMercado, GeometriaPadrao, Compatibilidades) — paralelas, não misturadas.

## Escopo atual (o que já existe, validado)

- Core Engine funcional: `Perfil → Componente → Tipo → Cena Técnica → Vista →
  Renderer → Imagem`.
- Pipeline de Aquisição de Dados testado em 4 catálogos reais de fabricantes
  distintos (Centenário, Euroshow, Alcoa, Vitral Sul), com 3 tipos de desafio de
  extração já identificados e documentados.
- Modelo de domínio com FamíliaMercado, GeometriaPadrao e PerfilGeometria,
  implementado e testado com um caso real (SU-019, Alcoa/Vitral Sul).

## Escopo futuro (registrado, não implementado)

- Providers além de PDF com texto (OCR, DXF, DWG, API de fabricante).
- Biblioteca de Conhecimento em escala (compatibilidades, regras de montagem,
  usinagens).
- Integração comercial com sistema de orçamento existente do Bruno.

## Princípios fundamentais (referência resumida — detalhamento no Volume 4, ADRs)

| Princípio | ADR |
|---|---|
| Geometria é a única fonte de verdade | ADR-001 |
| Renderer nunca conhece regras de engenharia | ADR-002 |
| Provider abstrai a origem dos dados | ADR-003 |
| FamíliaMercado representa linguagem do mercado | ADR-004 |
| GeometriaPadrao é ativo de engenharia compartilhado | ADR-005 |
| Pipeline é extrator de conhecimento técnico, não só de perfis | ADR-006 |
| Todo conhecimento estrutural é preservado, mesmo sem modelo ainda | ADR-007 |

## Estado Atual do Projeto

Situação nesta versão (2026-07-08):

✓ Core Engine validado (Fase 0, dados manuais e reais)
✓ Pipeline de Aquisição de Dados validado em 4 fabricantes distintos
✓ Modelo de Domínio consolidado (FamíliaMercado, GeometriaPadrao, PerfilGeometria)
✓ Constituição da Documentação aprovada (v1.0.0)

Em andamento:
• Consolidação da documentação oficial (Sprint A)

Próxima etapa:
• Volume 3 — Modelo de Domínio, Volume 11 — Roadmap

## Índice de Maturidade

```
Arquitetura   ██████████ (estável)
Domínio       ██████████ (estável)
Pipeline      █████████░ (validado em 4 fabricantes, Providers adicionais pendentes)
Providers     █████░░░░░ (só PDF-com-texto implementado)
Testes        ██░░░░░░░░ (Sprint C ainda não iniciado)
Renderer      ██████░░░░ (funcional via matplotlib, Three.js pendente de ambiente com rede)
```

## Convenção editorial de nomenclatura

Entidades oficiais do domínio são sempre escritas exatamente como definidas,
independente da posição na frase: Pipeline, Provider, Renderer, Vista, Cena Técnica,
Perfil, Componente, Tipo, Core Engine, GeometriaPadrao, FamíliaMercado,
PerfilGeometria. Isso evita ambiguidade entre o termo do domínio e o uso comum da
palavra.



## A Tese do EsquadriaCore

**Nota do Claude:** o ChatGPT propôs isto como um "manifesto" curto, distinto do
objetivo técnico já descrito acima — citando que projetos duradouros (Kubernetes,
React, Linux, PostgreSQL) costumam ter um documento assim. Concordo que é barato e
vale a pena; é texto, não arquitetura.

> A indústria de esquadrias desperdiça conhecimento porque cada fabricante o
> publica de forma isolada, usando convenções próprias. O EsquadriaCore separa
> conhecimento técnico da representação comercial, criando um domínio comum capaz
> de sobreviver às tecnologias, fabricantes e formatos de origem que o alimentam.

## Camadas de valor (visão estratégica, não arquitetura nova)

**Nota do Claude:** o ChatGPT observou que a documentação tende a parecer que o
projeto "termina no Renderer" — quando na prática o Renderer é só mais um
consumidor do domínio. Concordo que vale registrar essa visão, deixando claro que
isso NÃO é uma nova camada arquitetural (não muda o Volume 2), é uma lente
estratégica sobre o que já existe:

```
Mercado (vocabulário, convenções, fabricantes)
      │
      ▼
Conhecimento (FamíliaMercado, GeometriaPadrao, Compatibilidades, Regras — o
               patrimônio que continua válido independente de tecnologia)
      │
      ▼
Pipeline (extrai conhecimento bruto de fontes externas)
      │
      ▼
Modelo de Domínio (estrutura o conhecimento)
      │
      ▼
Core Engine (interpreta e representa)
      │
      ▼
Produtos (orçamento, configurador, catálogo, API, app — hoje só o Core Engine
           está implementado; os demais são escopo futuro já registrado)
```

Isso não compromete a produtos que não existem ainda — é só deixar explícito que
o domínio foi desenhado para ser reutilizável por múltiplas aplicações, não
apenas pelo Renderer atual.

## Missão (síntese aprovada por Bruno, Claude e ChatGPT)

> "Transformar o conhecimento técnico fragmentado da indústria de esquadrias em um
> domínio estruturado, reutilizável e independente de fabricantes."

Essa missão permanece válida mesmo que, no futuro, múltiplas aplicações diferentes
(orçamento, catálogo comercial, configurador) venham a consumir a mesma plataforma.
