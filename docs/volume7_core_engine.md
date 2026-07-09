# Volume 7 — Core Engine

---
**Versão:** 1.0.0
**Status:** Estável
**Sprint de origem:** Sprint A (consolidação); implementado na Fase 0
**Última atualização:** 2026-07-08
**ADRs relacionados:** ADR-001, ADR-002, ADR-005
**Implementação correspondente:** `/core_engine/src/renderer.py`, prova de conceito
GeometriaPadrao
**Dependências:** Volume 2 (Arquitetura), Volume 3 (Modelo de Domínio)
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** 8, 9, 10, 11
---

## Objetivo

Transformar geometria + composição em representações visuais (frontal, isométrica,
explodida) sem nunca gerar um sólido de fabricação (decisão consciente — ver "O que
o Core Engine não é" no Volume 1).

## Fluxo interno

```
Componente(s) resolvido(s) via GeometriaPadrao
     ↓
Composição em Tipo (regra de montagem)
     ↓
Cena Técnica (posição, rotação, comprimento por instância — referência, nunca cópia)
     ↓
Vista (ângulo, projeção, escala, estilo — nunca dado físico)
     ↓
Renderer (extrusão linear simples + sombreamento + projeção isométrica)
     ↓
Imagem (PNG/SVG)
```

## Domínio vs. Implementação (separação explícita)

**Nota do Claude:** o ChatGPT apontou, com razão, que este Volume misturava domínio
com biblioteca específica (matplotlib, Three.js) de forma que envelheceria mal.
Corrigindo agora — a separação abaixo garante que o Volume continue válido mesmo
que nenhuma dessas bibliotecas exista daqui a 5 anos.

**Domínio (nunca muda):** o Renderer recebe uma Vista e produz uma Imagem.

**Implementação atual:** `RendererMatplotlib` — extrusão linear + sombreamento
lambertiano + projeção isométrica via matplotlib/numpy.

**Implementação futura (planejada, não construída):** `RendererThreeJS` — mesma
interface (recebe Vista, produz Imagem), motor trocado por restrição de ambiente já
documentada (Volume 7, seção seguinte).

## Renderer — implementação atual (RendererMatplotlib)

Extrusão linear do contorno 2D do perfil (sem operação booleana / kernel CAD),
sombreamento lambertiano simples por normal de face, projeção isométrica via
matplotlib/numpy. Implementação validada com dados manuais (Fase 0) e dados reais
(SU-019, Alcoa/Vitral Sul via GeometriaPadrao).

**Nota de ambiente:** a implementação atual usa matplotlib por restrição de rede do
ambiente de prototipagem (sem acesso para instalar Node/Puppeteer/Three.js). A
arquitetura já isola o Renderer atrás da Vista especificamente para permitir essa
troca sem alterar mais nada — decisão pendente de ambiente com rede disponível, não
de arquitetura.

## Por que extrusão simples, não CAD completo (decisão registrada)

Decisão consciente de escopo: o objetivo do produto é gerar imagem técnica e
comercial de alta qualidade visual, não sólido preciso para fabricação/CNC. Isso
elimina a necessidade de kernel CAD (OpenCascade/CadQuery), operações booleanas de
sólidos, e exportação STEP — trade-off que fecha a porta (por ora) para
configurador de fabricação real, aceito conscientemente dado o objetivo atual do
produto.

## Bug real encontrado e corrigido (registrado por valor histórico)

Na primeira versão da função de extrusão, perfis horizontais (marco) descartavam a
dimensão de profundidade do contorno, resultando em peça "achatada" sem volume real.
Corrigido mapeando corretamente os dois eixos do contorno 2D para os eixos globais
conforme a direção de extrusão. Exemplo do valor de ter ido direto a um protótipo
funcional em vez de permanecer só em design — esse tipo de erro só aparece com
código rodando.

## Testes de integração já realizados

- Fase 0: dados manuais (4 perfis de teste, 1 Tipo de janela de correr).
- Prova de conceito GeometriaPadrao: `ALCOA-SU-019` e `VITRALSUL-SU-019`, dois
  Perfis de fabricantes distintos resolvidos para a mesma geometria — confirmado
  por contagem de pixel que o Renderer produz imagens idênticas, sem nunca "saber"
  que eram fabricantes diferentes (validação direta do ADR-002 e ADR-005).
