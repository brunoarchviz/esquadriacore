# Volume 6 — Pipeline de Aquisição de Dados

---
**Versão:** 1.0.0
**Status:** Estável (núcleo validado); Providers adicionais em Proposto
**Sprint de origem:** Sprint A (consolidação); implementado nas Fases 1-4
**Última atualização:** 2026-07-08
**ADRs relacionados:** ADR-003, ADR-006, ADR-007
**Implementação correspondente:** parsers Linha 25/30 (Centenário), teste Euroshow,
diagnóstico Alcoa/Vitral Sul
**Dependências:** Volume 2 (Arquitetura), Volume 3 (Modelo de Domínio)
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** 8, 9, 10, 11
---

## Objetivo

Transformar catálogos de fabricantes (hoje: PDF) em dados estruturados e
normalizados — código, peso, geometria vetorial, e qualquer conhecimento estrutural
adicional (compatibilidades, regras de montagem) — prontos para Curadoria e consumo
pelo Core Engine.

## Etapas do Pipeline

1. **Descoberta de página/seção** — localizar onde, no documento, está o conteúdo
   técnico relevante. Testado com dois métodos: intervalo fixo de página (funciona
   quando o catálogo organiza por blocos contíguos, ex: Centenário) e varredura por
   padrão de código em todo o documento (necessário quando o catálogo intercala
   conteúdos, ex: Euroshow).
2. **Extração de dado textual** — código, peso, descrição, via posição real das
   palavras na página (não regex ingênuo em texto corrido — necessário para lidar
   com layouts em grade de múltiplas colunas).
3. **Extração de geometria vetorial** — isolamento dos paths SVG correspondentes à
   região de cada perfil, com filtro de tamanho para excluir elementos de
   fundo/watermark.
4. **Validação de qualidade por campo** — código válido, peso válido (numérico),
   vetor encontrado, descrição encontrada, escala identificada. Cada perfil recebe
   um indicador de confiabilidade (detalhe em Volume 9).
5. **Saída normalizada** — JSON estruturado + planilha Excel técnica + arquivo
   vetorial (SVG) por perfil.
6. **Curadoria (humana)** — homologação da geometria (Curadoria Geométrica),
   associação a GeometriaPadrao quando aplicável, classificação funcional
   (categoria/orientação/aplicação).

## Casos reais de extração já testados (base do ADR-003)

| Fabricante | Texto extraível? | Vetor nativo? | Desafio específico |
|---|---|---|---|
| Centenário/Tamboré | Sim | Sim | Nenhum — caso de referência |
| Euroshow | Sim | Sim | Defeito pontual de dado (dígito "0"→"O" corrompido) |
| Alcoa (seção testada) | Não | Sim (sem texto) | Fonte convertida em contorno — precisa OCR |
| Vitral Sul | Não (na região do desenho) | Não (raster embutido) | Desenho é imagem JPEG — precisa OCR sobre imagem |

## Regra de validação de peso (decorrente do caso Euroshow)

Todo perfil sem peso numericamente válido é marcado como `peso_suspeito` (não
apenas `peso_ausente`) — sinaliza defeito de dado de origem para revisão humana, em
vez de tentar "consertar" a extração para aceitar formatos inválidos.

## O que o Pipeline nunca faz

- Nunca decide regra de montagem definitiva — no máximo preserva texto bruto de
  seções que parecem descrever conexões (ADR-007), para estruturação futura.
- Nunca infere compatibilidade entre fabricantes automaticamente — mesmo quando
  encontra o mesmo código em catálogos diferentes (ex: SU-019), a associação via
  GeometriaPadrao exige curadoria humana explícita.
- Nunca redistribui a arte original do fabricante como artefato de produto — o SVG
  extraído é Material de Referência interno (auditoria), não saída comercial.

## Casos de teste de referência (para a futura suíte automatizada, Sprint C)

Centenário (Linha 25, Linha 30), Euroshow, Alcoa (seção Suprema), Vitral Sul (Nobile
2.5) — mantidos como conjunto permanente de regressão.
