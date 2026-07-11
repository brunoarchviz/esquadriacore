# ADR-008 — GeometriaPadrao suporta contorno externo + vazios internos

**Status: Validado por evidência técnica, aguardando revisão de governança**
(revisão do ChatGPT, a pedido do Bruno; este é o tipo de decisão de
entidade+módulo que ele designou para revisão externa). Quando aprovado,
integrar ao Volume 4 na próxima revisão da documentação.

> A validação do modelo de representação e extrusão NÃO implica homologação
> automática das geometrias individuais que o utilizam. Cada seção traçada
> com este modelo passa pela revisão geométrica e validação visual do
> especialista antes de ser considerada homologada.

## Contexto
Perfil de alumínio extrudado é OCO — contorno externo com câmaras vazadas.
O modelo original (`contorno_mm` = polígono único preenchido) não representa
essa natureza: renderiza seções sólidas, visualmente incorretas para o alvo
"renderizável comercial" do Sprint E.2.

## Decisão
Dois campos opcionais em GeometriaPadrao, coexistindo com `contorno_mm`:

```
contorno_externo: [pontos]       # silhueta de fora
vazios_internos: [[pontos],...]  # câmaras ocas (zero ou mais)
nivel_contorno: str              # escala de fidelidade (metadado, Sprint E.2)
```

Compatibilidade preservada: geometrias antigas com apenas `contorno_mm`
continuam válidas (polígono preenchido simples). O formato novo é opcional.

## Consequências
- Renderer ganha `extrudar_com_furos` (paredes do externo + paredes de cada
  vazio + tampas em grade que respeitam os furos). `renderizar` escolhe o
  extrusor pela presença de `contorno_externo`; o caminho antigo permanece.
- Nível de fidelidade do contorno vira metadado (`nivel_contorno`), não
  entidade nova — consistente com a regra geral do projeto.
- Nota de implementação: o protótipo externo validou o algoritmo em frame
  próprio (x, y, z=comprimento); a implementação no core_engine porta o
  algoritmo para a convenção de eixos do `extrudar_perfil` (rotacao/posicao),
  preservando a correção do bug de achatamento da Fase 0.

## Alternativas consideradas
- Entidade nova "GeometriaOca": rejeitada — viola a regra "nenhuma entidade
  nova sem evidência prática"; os campos opcionais resolvem.
- Substituir `contorno_mm` de vez: rejeitada — quebraria as 46 geometrias
  registradas e os testes de regressão; migração pode ser gradual via
  `nivel_contorno`.
