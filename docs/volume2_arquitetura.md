# Volume 2 — Arquitetura

---
**Versão:** 1.0.0
**Status:** Estável
**Sprint de origem:** Sprint A
**Última atualização:** 2026-07-08
**ADRs relacionados:** ADR-001, ADR-002, ADR-003, ADR-006, ADR-007
**Implementação correspondente:** Core Engine (Fase 0), Pipeline de Aquisição
(Fases 1-4)
**Dependências:** Volume 1 (Visão Geral), Volume 3 (Modelo de Domínio)
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** 6, 7, 11
---

## Visão geral do fluxo completo

```
PDF (ou outra fonte — Provider)
     ↓
Pipeline de Aquisição de Dados
     ↓ (extrai: perfis, ferragens, compatibilidades, regras, usinagens, metadados)
     ↓
Curadoria (humana) → GeometriaPadrao homologada, PerfilGeometria associada
     ↓
Perfil (dados por fabricante) + Componente (categoria/orientação/aplicação)
     ↓
Tipo (composição segundo Regra)
     ↓
Cena Técnica (posicionamento espacial, por referência)
     ↓
Vista (parâmetros de apresentação)
     ↓
Renderer (motor de renderização — hoje matplotlib, futuramente Three.js)
     ↓
Imagem (derivada, nunca fonte de verdade)
```

## Dois blocos independentes

O EsquadriaCore é composto por dois grandes blocos, com uma fronteira estrita entre
eles (ADR-002, ADR-006):

**1. Pipeline de Aquisição de Dados** — descobre conhecimento a partir de fontes
externas (catálogos de fabricantes). Não sabe nada sobre como esse conhecimento
será desenhado ou apresentado.

**2. Core Engine** — interpreta e apresenta o conhecimento já estruturado (Perfil,
Componente, Tipo, Cena Técnica, Vista, Renderer). Não sabe nada sobre PDFs, OCR, ou
qualquer detalhe de como o dado chegou até ele.

A ponte entre os dois blocos é o **Modelo de Domínio** (Volume 3) — a saída do
Pipeline é exatamente a entrada do Core Engine, sem camada de tradução adicional.

## Limites entre módulos (o que cada um nunca faz)

| Módulo | Nunca faz |
|---|---|
| Provider | Nunca interpreta significado — só extrai dado bruto/normalizado |
| Pipeline de Aquisição | Nunca decide regra de montagem ou classificação final — prepara para curadoria |
| Curadoria (humana) | Nunca é substituída por inferência automática de FamíliaMercado |
| Core Engine | Nunca sabe de onde veio o dado (PDF, OCR, cadastro manual) |
| Renderer | Nunca conhece regra de engenharia, fabricante, ou montagem (ADR-002) |

## Quatro blocos de agrupamento (mapa de orientação, não fronteira de módulo nova)

**Nota do Claude:** o ChatGPT sugeriu isso sem formalizar como "Bounded Context"
(DDD), e mantenho a mesma cautela — isto é um mapa de orientação visual para quem
está chegando agora, não uma nova fronteira de módulo com enforcement de código. A
fronteira real que já existe e é aplicada (monólito modular, ver seção abaixo) não
muda.

```
Aquisição          Domínio              Representação        Conhecimento
─────────          ───────              ─────────────        ────────────
Pipeline           Perfil               Cena Técnica          Biblioteca (futura)
Provider           FamíliaMercado       Vista                 Compatibilidades (futura)
(OCR futuro)       GeometriaPadrao      Renderer               Regras (futura)
                   Componente
                   Tipo
```

## Dependências proibidas (explícitas, decorrentes do ADR-002 e ADR-003)

- Renderer nunca importa Pipeline.
- Renderer nunca importa Provider.
- Provider nunca importa Core Engine.
- Pipeline nunca importa Renderer ou Vista.

Isso não é regra nova — é o ADR-002/ADR-003 tornado explícito em termos de
dependência de código, para que uma violação de import seja detectável em revisão
de código sem precisar reler o ADR toda vez.

## Dependências entre Volumes

```
Volume 1 (Visão Geral)
     ↓
Volume 3 (Modelo de Domínio) ←── Volume 4 (ADRs, fundamenta as decisões)
     ↓
Volume 2 (este documento — Arquitetura, une Pipeline + Core Engine)
     ↓
Volume 6 (Pipeline em detalhe)     Volume 7 (Core Engine em detalhe)
     ↓                                   ↓
Volume 9 (Validações)              Volume 8 (Biblioteca de Conhecimento)
     ↓
Volume 10 (Testes)
```

## Providers — abstração de origem de dados (detalhe em Volume 5)

Já validados/testados na prática: **PDF com texto e vetor nativo** (Centenário,
Tamboré). Casos reais documentados que motivam Providers futuros: PDF com vetor sem
texto (Alcoa), PDF com texto e defeito de dado (Euroshow), PDF com desenho raster
embutido (Vitral Sul). Nenhum desses Providers adicionais está implementado — apenas
identificados como necessidade real (ADR-003, ADR-007).

## Por que não há microsserviços (decisão registrada)

Na fase atual, o EsquadriaCore é um monólito modular: módulos internos bem
separados (Pipeline, Core Engine, cada um com submódulos), rodando no mesmo
processo/deploy. Microsserviços seriam over-engineering para o estágio e a escala
atuais — não há ainda gargalo de carga identificado que justifique a complexidade
operacional adicional. Decisão revisitável apenas quando um módulo específico
precisar escalar de forma independente e comprovada.
