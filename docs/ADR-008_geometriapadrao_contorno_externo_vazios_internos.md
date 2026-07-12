# ADR-008 — GeometriaPadrao suporta contorno externo e vazios internos

## Status

Aceito.

> A validação do ADR-008 não implica homologação automática das geometrias individuais que utilizam esse modelo.

## Contexto

Durante a fase de Contornos Renderizáveis, o teste prático do `GEO-SU-005` mostrou uma limitação real do modelo anterior da entidade `GeometriaPadrao`.

O modelo legado representava a seção do perfil por meio de um único polígono preenchido:

```python
contorno_mm: list[tuple[float, float]]
```

Esse formato era suficiente para envelopes funcionais e representações muito simplificadas, mas não representa corretamente a natureza física de um perfil de alumínio extrudado.

Perfis de alumínio são ocos. Eles possuem:

- contorno externo;
- câmaras internas;
- vazios;
- paredes;
- ganchos;
- rebaixos;
- regiões abertas e fechadas.

Nas iterações iniciais do `GEO-SU-005`, o perfil era renderizado como uma massa preenchida, adequada apenas como envelope funcional. A iteração 11, após a adoção do modelo com contorno externo e vazios internos, passou a representar corretamente a natureza oca do perfil, com câmara superior vazada, paredes internas e ganchos inferiores reconhecíveis.

Essa evidência prática justificou a evolução do modelo.

## Decisão

A entidade `GeometriaPadrao` passa a suportar um modelo de seção composto por:

- `contorno_externo`;
- `vazios_internos`.

Todas as coordenadas são expressas em milímetros (a exemplo do campo legado `contorno_mm`); os nomes dos campos são exatamente os implementados no código.

O campo legado `contorno_mm` permanece temporariamente aceito por compatibilidade com geometrias ainda não refinadas.

## Modelo conceitual

Conforme implementado em `domain/entidades.py`:

```python
@dataclass
class GeometriaPadrao:
    id: str
    contorno_mm: list[tuple[float, float]]        # formato legado (coordenadas em mm)
    status: str
    versao: str
    # ...campos de curadoria existentes...

    # Formato novo preferencial (ADR-008; coordenadas em mm)
    contorno_externo: Optional[list] = None       # lista de (x, y) da silhueta externa
    vazios_internos: Optional[list] = None        # lista de listas de (x, y) — câmaras ocas
    nivel_contorno: str = "0_bruto_aproximado"    # escala de fidelidade (Sprint E.2)
```

Os campos de curadoria do contorno (`status_contorno`, `metodo_contorno`,
`evidencia_contorno`) são registrados no dado (`dados/geometrias.json`), não na
entidade — só serão promovidos a campos da entidade quando houver uso concreto
no código (regra geral do projeto: nenhum campo sem necessidade real).

## Regras de domínio

1. `contorno_externo` representa a silhueta externa da seção do perfil.
2. `vazios_internos` representa câmaras e vazios internos.
3. `vazios_internos` pode ser uma lista vazia.
4. `contorno_mm` continua válido apenas como formato legado.
5. O novo modelo não implica precisão CAD.
6. O novo modelo não autoriza uso para fabricação, usinagem, CNC ou metrologia.
7. O objetivo imediato é `renderizavel_comercial`, não `alta_fidelidade`.
8. Cada geometria continua exigindo validação visual própria antes de ser marcada como contorno aprovado.

## Consequências positivas

- Representa corretamente a natureza oca dos perfis de alumínio extrudado.
- Permite renderização técnica mais fiel.
- Melhora a leitura visual dos perfis sem exigir modelo CAD.
- Mantém compatibilidade com geometrias antigas.
- Evita copiar vetores exatos de catálogos de terceiros.
- Preserva a filosofia de modelo próprio simplificado.
- Permite evolução gradual das GeometriasPadrao já homologadas.

## Consequências negativas

- O Renderer precisa lidar com polígonos compostos com furos.
- O extrusor precisa considerar paredes internas e vazios.
- As validações de geometria ficam mais complexas.
- Os testes precisam cobrir formatos legados e novos.
- A curadoria visual passa a exigir validação específica do contorno, separada da homologação de equivalência.

## Decisões explicitamente não tomadas

Este ADR não cria agora:

- modelo CAD;
- precisão industrial;
- suporte a fabricação;
- entidade nova para detalhes visuais;
- cópia vetorial integral de catálogos;
- garantia de equivalência geométrica automática;
- homologação automática das demais geometrias.

Também não cria o campo `detalhes_visuais` neste momento.

Se algum detalhe for necessário para reconhecer o perfil, ele deve ser incorporado ao `contorno_externo` ou a um item de `vazios_internos`.

Detalhes puramente estéticos ficam para decisão futura, somente se houver demanda real.

## Compatibilidade

Durante a transição, o sistema deve aceitar dois formatos.

### Formato legado

```python
contorno_mm
```

Usado para geometrias ainda em estado `bruto_aproximado` ou `envelope_funcional`.

### Formato novo

```python
contorno_externo
vazios_internos
```

Usado para geometrias em estado `renderizavel_comercial` ou superior.

O Renderer deve preferir o formato novo quando ele existir.

## Impacto no Core Engine

O Renderer deve renderizar o novo formato como polígono composto com furos.

Implementações possíveis:

- SVG: `fill-rule: evenodd`;
- Matplotlib: `Path` composto;
- Three.js futuro: shape com holes.

Implementação atual: `extrudar_com_furos` em `core_engine/renderer.py` (paredes
do contorno externo e de cada vazio + tampas em grade que respeitam os furos),
na mesma convenção de eixos do `extrudar_perfil` legado. `renderizar` escolhe o
extrusor pela presença de `contorno_externo`.

O Renderer continua sem decidir equivalência, função, família ou compatibilidade. Ele apenas consome a `GeometriaPadrao` já curada.

## Impacto nas validações

Adicionar validações para o novo formato:

1. Pelo menos um formato deve existir:
   - `contorno_mm`; ou
   - `contorno_externo`.

2. Se `contorno_externo` existir:
   - deve ser polígono fechado;
   - deve ter pelo menos 3 pontos;
   - não deve se auto-intersectar.

3. Cada item de `vazios_internos`:
   - deve ser polígono fechado;
   - deve ter pelo menos 3 pontos;
   - deve estar contido dentro de `contorno_externo`;
   - não deve se auto-intersectar.

4. Vazios internos:
   - não devem se cruzar entre si;
   - não devem ultrapassar o contorno externo;
   - podem ser lista vazia.

5. Se `contorno_mm` e `contorno_externo` existirem ao mesmo tempo:
   - o formato novo é preferencial;
   - `contorno_mm` deve ser tratado como legado.

## Impacto nos testes

Adicionar testes para:

1. Geometria com `contorno_externo` e `vazios_internos`.
2. Geometria com `vazios_internos` vazio.
3. Geometria legada com apenas `contorno_mm`.
4. Geometria inválida sem `contorno_mm` e sem `contorno_externo`.
5. Vazio fora do contorno externo.
6. Vazio intersectando outro vazio.
7. Renderer preservando vazios internos.
8. Regressão de DADOS do `GEO-SU-005` iteração 11 (número de vazios, contagem
   de pontos, áreas e contenção dos vazios — nunca comparação de imagem pixel a
   pixel, que é frágil a versões de biblioteca, fontes e DPI).

## Evidência prática

Primeira evidência oficial do novo modelo:

- Geometria: `GEO-SU-005`;
- FamíliaMercado: `SUPREMA`;
- Perfil de referência: `SU-005`;
- Status anterior: representação maciça / envelope funcional;
- Status após iteração 11: seção 2D com câmara superior vazada, paredes internas e ganchos inferiores reconhecíveis;
- Nível de contorno: `2_renderizavel_comercial`;
- Método: contorno externo + vazios internos;
- Validação: visual, por Bruno;
- Evidência: `curadoria/contornos/SU-005_lado_a_lado_iter11.png`.

## Adendos documentais

A documentação v1.0 permanece congelada. Portanto, os Volumes originais não devem ser editados diretamente.

Adendos criados em `docs/adendos/` (a partir deste ADR):

- `adendo_volume3_geometriapadrao_perfil_oco.md` — Volume 3, Modelo de Domínio;
- `adendo_volume7_renderer_vazios_internos.md` — Volume 7, Core Engine / Renderer;
- `adendo_volume9_validacoes_contornos_com_vazios.md` — Volume 9, Validações;
- `adendo_volume10_testes_perfil_oco.md` — Volume 10, Testes.

## Procedimento de curadoria fina

O processo usado no `GEO-SU-005` também validou um método de curadoria fina, mas isso não é parte do ADR. Está registrado em `docs/plano_de_curadoria.md`.

## Conclusão

O ADR-008 é aceito porque foi motivado por evidência concreta, resolve uma limitação real do modelo e respeita a Regra 1: evidência antes de arquitetura.

A decisão valida o modelo `contorno_externo + vazios_internos`, mas não homologa automaticamente nenhuma geometria individual.
