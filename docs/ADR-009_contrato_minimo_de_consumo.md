# ADR-009 — Contrato Mínimo de Consumo da Biblioteca

Status: **Aceito** (2026-07-13, Sprint E.3)

## Contexto

A biblioteca homologada (`dados/geometrias.json`, `dados/perfil_geometria.json`)
já é lida por vários consumidores (testes, renderer, ferramentas de curadoria),
cada um abrindo o JSON na mão e assumindo convenções implícitas. Antes de
escalar os 36 contornos restantes e antes de qualquer aplicação externa
consumir a biblioteca, é preciso estabilizar a **fronteira de saída** dos dados
que já existem — sem criar produto novo, entidade de domínio nova nem alterar a
fonte de verdade.

Este ADR NÃO cria API, GeradorDeTipos, endpoint ou sistema de montagem. Define
apenas a convenção estável pela qual os dados existentes são expostos.

## Decisão

Introduzir a camada `contrato/` (`contrato/consumo.py`), um carregador/adaptador
puro (sem dependências externas, sem frontend) que lê os JSONs oficiais e
devolve DTOs imutáveis (`GeometriaConsumivel`, `AssociacaoConsumivel`,
`BibliotecaConsumivel`) segundo as regras abaixo.

### 1. Separação entre dado armazenado e dado normalizado para consumo

Toda normalização (orientação, resolução de nível, fechamento, unificação de
legado) acontece **somente no DTO de saída**. Os pontos gravados em
`dados/geometrias.json` **não são reordenados nem modificados**. O contrato
adapta os dados para uma convenção estável de consumo, mas preserva a evidência
homologada original intacta.

### 2. Orientação dos anéis

- contorno externo: **anti-horário (CCW)**;
- vazios internos: **horário (CW)**.

A normalização é feita no carregador (via sinal da área — shoelace). Inverter a
ordem dos pontos de um anel **não altera forma geométrica, coordenadas, escala
ou posição** — altera apenas o sentido de percurso do anel. Por isso a
normalização é segura e não descaracteriza a geometria homologada.

### 3. Referencial e eixos

Campos do DTO (nomes estáveis, deliberados):

- `unidade = "mm"` — sempre milímetros (nunca pixels ou unidades relativas);
- `referencial = "local_do_perfil"` — cada perfil tem seu próprio sistema; **não
  existe, nesta versão, um referencial canônico compartilhado**. `referencial`
  **não** é uma coordenada nem um ponto de origem — é a declaração de que o
  sistema é local. (Evita-se de propósito o nome `origem`, que sugeriria um
  ponto/coordenada.)
- `eixo_x = "positivo_para_direita"`;
- `eixo_y = "positivo_para_cima"` (convenção matemática, não SVG);
- as geometrias **não são transladadas**. O contrato expõe o **bounding-box**
  calculado como objeto de campos nomeados
  (`{min_x, min_y, max_x, max_y, largura, altura}`, em mm; `null` quando não há
  contorno), sem modificar as coordenadas originais.

### 4. Fechamento dos anéis

Fechamento **implícito**: o último ponto não repete o primeiro. Coerente com
`domain.validar_contornos` (ADR-008).

### 5. Formato legado (`contorno_mm`) — apenas fallback de entrada

A saída pública v1.0 tem **uma única forma geométrica**: `contorno_externo` +
`vazios_internos`, com a procedência indicada por `fonte_contorno`.
`contorno_mm` é **exclusivamente fallback de ENTRADA** e **não** é um campo do
DTO de saída. Regras:

1. se existir `contorno_externo`, ele é utilizado
   (`fonte_contorno = "contorno_externo_vazios_internos"`);
2. se não existir `contorno_externo` mas existir `contorno_mm`, seu conteúdo é
   apresentado em `contorno_externo`, com `vazios_internos = ()` e
   `fonte_contorno = "contorno_mm_legado"`;
3. se nenhum existir, `contorno_externo = None` e `fonte_contorno = None`;
4. quando o formato novo existe, ele prevalece.

Nenhuma geometria atual usa o legado — o caso é coberto por teste sintético
para garantir compatibilidade futura.

### 6. Versionamento do contrato

`CONTRATO_CONSUMO_VERSAO = "1.0"`, exposto no campo `versao_schema` de cada DTO
e na serialização. **Vive no código do contrato, não é gravado nos JSONs.** Os
arquivos de dados permanecem intocados; a evolução do contrato (novos campos,
novas convenções) acontece sem alterar a fonte de verdade.

### 7. Geometrias ainda não renderizáveis

- a chave `nivel_contorno` **ausente** equivale a `0_bruto_aproximado` (não é
  erro); essa normalização ocorre só no DTO;
- os níveis reconhecidos são uma **enumeração fechada**
  (`0_bruto_aproximado`, `1_envelope_funcional`, `2_renderizavel_comercial`,
  `3_vetorial_validado`, `4_alta_fidelidade`). **Esta escala não é criada aqui**
  — já está formalmente registrada em `docs/plano_de_curadoria.md` (Sprint E.2),
  no default `nivel_contorno = "0_bruto_aproximado"` de `domain/entidades.py`,
  em `docs/ADR-008` e no `docs/adendos/adendo_volume3_*`. O contrato apenas a
  reutiliza;
- um valor **presente porém desconhecido** (erro de digitação, nível não
  previsto) é **erro explícito** (`ContratoInvalido`), nunca tratado
  silenciosamente como válido;
- `renderizavel = True` somente para níveis formalmente reconhecidos como
  renderizáveis (`2_`, `3_`, `4_`), por **enumeração** — não por comparação
  textual "nível atual ou superior";
- geometrias brutas carregam sem erro: `contorno_externo = None`,
  `vazios_internos = ()` (tupla vazia, nunca `None`), e não passam por
  `domain.validar_contornos` (não há contorno a validar).

### 8. Associações (PerfilGeometria)

O contrato também estabiliza a leitura das associações (ADR-005), sem criar
entidade nova. `AssociacaoConsumivel` preserva os sete campos armazenados em
`dados/perfil_geometria.json` (`perfil_id`, `geometria_padrao_id`,
`responsavel_homologacao`, `metodo_validacao`, `data`, `nivel_de_confianca`,
`observacoes`) e acrescenta os campos de contrato `versao_schema` e
`fabricante_derivado`. A associação **referencia** a geometria
por id e **nunca embute os pontos**. `carregar_biblioteca` verifica a
integridade referencial: toda associação aponta para uma geometria carregada.

O campo **`fabricante` não existe** em `dados/perfil_geometria.json`. O contrato
o expõe como `fabricante_derivado` (nome que deixa a natureza inferida
explícita), **inferido do prefixo de `perfil_id`** pela tabela:

| prefixo | fabricante_derivado |
|---|---|
| `ALCOA` | Alcoa |
| `HYDRO` | Hydro |
| `VITRALSUL` | Vitral Sul |
| `TAMBORE` | Tamboré |
| `CENTENARIO` | Centenário |
| `ASA` | ASA |

- prefixo **desconhecido → `None`** (nunca um palpite);
- `fabricante_derivado` **não substitui** um eventual fabricante armazenado no
  domínio (o `Perfil` do Volume 3 tem seu próprio `fabricante`);
- a inferência **não estabelece intercambiabilidade** entre perfis ou
  fabricantes (ADR-004: FamíliaMercado/nome é vocabulário, não equivalência).

### 9. Imutabilidade e dependências

- os DTOs são `dataclass(frozen=True)` **com coordenadas em tuplas de tuplas** —
  uma frozen dataclass contendo listas ainda permitiria mutar as listas
  internas, o que enfraqueceria a promessa do contrato;
- a serialização de fronteira (`para_dict`) converte tuplas em arrays;
- a validação geométrica é **delegada a `domain.validar_contornos`** (ADR-008);
  `contrato/consumo.py` não reimplementa nem duplica operações de engenharia;
- o schema de máquina (`contrato/schemas/biblioteca_consumo.schema.json`) é
  publicado como artefato, mas **ainda não é validado por uma implementação
  oficial de JSON Schema**. A biblioteca `jsonschema` **não** é adotada (ausente
  no ambiente): não se adiciona dependência apenas para fechar este sprint. Os
  testes usam uma **validação estrutural limitada** própria, que cobre somente
  as palavras-chave `type`, `required`, `properties`, `items`, `enum`, `anyOf`,
  `$ref` — **não** implementa `oneOf`/`allOf`/`not`, `patternProperties`,
  `format`, `additionalProperties`, limites numéricos etc. Ela **não substitui**
  `jsonschema` nem prova conformidade com o padrão. A adoção de `jsonschema`
  fica adiada até haver uso além deste teste, com justificativa registrada.

## Consequências

- Qualquer aplicação futura consome a biblioteca por uma fronteira única e
  documentada, sem reabrir os JSONs nem reinventar convenções.
- A fonte de verdade permanece intocada; a evolução do consumo não pressiona o
  formato de armazenamento.
- Salvaguarda mantida (coerente com ADR-008): validar/consumir o modelo não
  homologa nem altera geometria individual.
- Fica pendente (fora do escopo do E.3) a migração dos consumidores atuais
  (renderer, testes legados, curadoria) para o carregador — para não misturar
  refatoração com a definição do contrato.

Este ADR não altera nenhum volume congelado da documentação v1.0.
