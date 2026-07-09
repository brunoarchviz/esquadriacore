# Volume 10 — Testes

---
**Versão:** 1.0.0
**Status:** Proposto
**Sprint de origem:** Sprint C
**Última atualização:** 2026-07-08
**ADRs relacionados:** ADR-001, ADR-002, ADR-003
**Implementação correspondente:** nenhuma ainda — este Volume é especificação;
código de teste é o próximo passo, fora do escopo deste documento
**Dependências:** Volume 3 (Modelo de Domínio), Volume 9 (Validações)
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** nenhum
---

## Objetivo

Especificar a suíte de testes (unitário, integração, regressão) que protege as
regras já registradas no Volume 9, antes de existir volume de dados que torne
erros silenciosos caros.

| Tipo | Objetivo |
|---|---|
| Unitário | Validar regras de cada entidade individualmente |
| Integração | Validar comunicação entre módulos (Provider → Pipeline → Core Engine) |
| Regressão | Garantir que catálogos conhecidos continuam funcionando após mudanças |

## Testes Unitários

Cobertura direta das validações do Volume 9 — um teste por regra, não um teste
genérico por entidade.

- `Perfil` sem `peso_kg_m` numericamente válido → deve resultar em
  `peso_suspeito=True`, nunca exceção nem descarte.
- `PerfilGeometria` apontando para `GeometriaPadrao` com `status=bruto_aproximado`
  → deve gerar aviso de exceção documentada, não erro silencioso.
- `Cena Técnica` com instância sem `componente_id` válido → deve falhar
  explicitamente (é o teste que torna o ADR-001 verificável em código, não só em
  convenção).

## Testes de Integração

Ponta a ponta: Provider → extração → normalização → Curadoria simulada → Core
Engine → imagem. Formaliza como suíte repetível a implementação de referência já
rodada manualmente (Fase 0 + Fase 1) — não constrói do zero.

## Testes de Regressão

Conjunto permanente de fixtures, usando os catálogos já processados:

| Catálogo | O que valida |
|---|---|
| Centenário (Linha 25) | Caso de referência — extração limpa, vetor+texto nativo |
| Centenário (Linha 30) | Generalização intra-fabricante sem alteração de código |
| Euroshow | Layout não-contíguo, defeito de dado (peso corrompido) |
| Alcoa (seção Suprema) | Ausência de texto extraível — caso que exige Provider futuro (OCR), marcado `xfail` até existir |
| Vitral Sul | Desenho raster embutido — outro caso que exige Provider futuro, marcado `xfail` até existir |

## Critério de Execução

- Unitários: a cada mudança de código, sempre.
- Integração: a cada mudança no Pipeline ou Core Engine.
- Regressão: antes de qualquer Sprint que toque Providers ou Pipeline (D, E).

---

## Notas (histórico e justificativas — separado do corpo normativo acima)

**Nota do Claude:** este Volume reorganizado após observação do ChatGPT — antes
misturava especificação de teste com histórico/justificativa no mesmo bloco;
agora o corpo acima é direto, e o histórico fica só aqui.

- Este Volume está em **Proposto**, não Validado — diferente dos Volumes
  anteriores, aqui não há evidência de execução real ainda, só especificação. Só
  sobe para Validado depois que ao menos os testes de regressão rodarem contra os
  catálogos reais uma vez.
- Exemplo real por trás do teste de `peso_suspeito`: Euroshow ES-002, peso gravado
  como `"0,95O Kg/m"` (letra "O" no lugar do dígito "0").
- Exemplo real por trás do teste de `PerfilGeometria`/`bruto_aproximado`:
  `GEO-SU-019`, usado deliberadamente com contorno aproximado na prova de conceito.
- Sobre os dois casos `xfail` (Alcoa, Vitral Sul): a intenção é que, no dia em que
  alguém implementar o Provider de OCR, o teste vire verde sozinho e sirva de
  prova objetiva de que funcionou — em vez de descobrir isso manualmente de novo.

## Próxima ação concreta

Nenhuma automática — este Volume fecha o escopo original do Sprint A→C. O próximo
passo de fato exige decisão do Bruno: seguir para Sprint D (Providers, incluindo o
OCR que os testes acima já preveem como pendente) ou pausar consolidação e voltar a
produto/implementação. Não vou presumir essa escolha no lugar dele.
