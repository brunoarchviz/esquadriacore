# Adendo — Contrato Mínimo de Consumo da Biblioteca

Este adendo complementa a documentação v1.0 (congelada) sem alterá-la.
Origem: ADR-009. É a especificação legível (face humana) do contrato cuja face
de máquina é `contrato/schemas/biblioteca_consumo.schema.json`.

## Objetivo

Descrever como consumir as geometrias e associações já homologadas por uma
fronteira estável, independente de frontend, GeradorDeTipos ou qualquer módulo
específico.

## Como carregar

```python
from contrato import carregar_biblioteca

bib = carregar_biblioteca()             # lê dados/geometrias.json + perfil_geometria.json
bib.geometrias                          # tupla de GeometriaConsumivel (46)
bib.associacoes                         # tupla de AssociacaoConsumivel (245)
bib.renderizaveis()                     # só as renderizáveis (10)
g = bib.geometria("GEO-SU-005")         # busca por código
g.para_dict()                           # dict serializável (arrays em vez de tuplas)
```

Também há `carregar_geometrias()` e `carregar_associacoes()` avulsos.

## Formato de saída — GeometriaConsumivel

| campo | tipo | observação |
|---|---|---|
| `codigo` | str | ex.: `GEO-SU-005` |
| `familia_mercado` | str/null | ex.: `SUPREMA`, `GOLD` |
| `descricao` | str/null | função do perfil |
| `unidade` | str | sempre `"mm"` |
| `referencial` | str | `"local_do_perfil"` — sistema próprio de cada perfil; não é uma coordenada |
| `eixo_x` | str | `"positivo_para_direita"` |
| `eixo_y` | str | `"positivo_para_cima"` |
| `nivel_contorno` | str | enumeração fechada (ver abaixo) |
| `renderizavel` | bool | `True` só para níveis `2_`/`3_`/`4_` |
| `contorno_externo` | lista de `[x,y]` / null | **CCW**; `null` quando ainda não há contorno. É a forma geométrica única de saída (inclusive quando a origem é o legado) |
| `vazios_internos` | lista de anéis | cada anel **CW**; **sempre lista** (vazia é válida, nunca `null`) |
| `fonte_contorno` | str/null | `"contorno_externo_vazios_internos"` / `"contorno_mm_legado"` / `null` |
| `bounding_box` | objeto `{min_x,min_y,max_x,max_y,largura,altura}` / null | campos nomeados, em mm; `null` sem contorno; não translada o dado |
| `status_contorno` | str/null | ex.: `validado_visualmente` |
| `metodo_contorno` | str/null | ex.: `contorno_externo_vazios_internos` |
| `evidencia_contorno` | str/null | caminho da imagem de evidência |
| `versao_schema` | str | `"1.0"` |

Propriedades derivadas: `largura_mm` e `altura_mm` (do bounding-box).

## Formato de saída — AssociacaoConsumivel

Preserva os sete campos armazenados em `dados/perfil_geometria.json` e
acrescenta os campos de contrato `versao_schema` e `fabricante_derivado`.
Referencia a geometria por id; nunca embute pontos.

| campo | tipo | observação |
|---|---|---|
| `perfil_id` | str | obrigatório, não vazio |
| `geometria_padrao_id` | str | obrigatório; aponta para uma geometria carregada |
| `responsavel_homologacao` | str | auditoria |
| `metodo_validacao` | str | auditoria |
| `data` | str | auditoria |
| `nivel_de_confianca` | str | `alto` / `medio` / `baixo` |
| `observacoes` | str/null | auditoria |
| `fabricante_derivado` | str/null | **inferido** do prefixo de `perfil_id`; `None` se prefixo desconhecido — não é dado armazenado, não estabelece intercambiabilidade |
| `versao_schema` | str | `"1.0"` |

## Regras explícitas

1. **Unidade**: sempre milímetros.
2. **Eixos**: cartesiano 2D, `eixo_x` positivo à direita, `eixo_y` positivo para
   cima.
3. **Referencial**: `referencial = "local_do_perfil"` — sistema próprio de cada
   geometria; não há referencial canônico compartilhado nesta versão.
   `referencial` não é uma coordenada/ponto de origem. Use `bounding_box` como
   referência; as coordenadas não são transladadas.
4. **Orientação**: externo CCW, vazios CW (normalizado na saída). O JSON
   armazenado não é reordenado. Inverter a ordem de um anel não muda forma,
   coordenadas, escala ou posição — só o sentido de percurso.
5. **Fechamento implícito**: o último ponto não repete o primeiro.
6. **Forma geométrica única e legado**: a saída pública v1.0 tem uma só forma —
   `contorno_externo` + `vazios_internos` — indicada por `fonte_contorno`.
   `contorno_mm` é **apenas fallback de ENTRADA** e **não** pertence ao DTO de
   saída. Regras:
   - se existir `contorno_externo`, ele prevalece (`fonte_contorno =
     "contorno_externo_vazios_internos"`);
   - se só existir `contorno_mm`, seu conteúdo é apresentado em
     `contorno_externo`, com `vazios_internos = ()` e `fonte_contorno =
     "contorno_mm_legado"`;
   - se nenhum existir, `contorno_externo = null` e `fonte_contorno = null`.
7. **Níveis reconhecidos** (enumeração fechada, definida em
   `docs/plano_de_curadoria.md` / `domain/entidades.py` / ADR-008, reutilizada
   aqui): `0_bruto_aproximado`, `1_envelope_funcional`,
   `2_renderizavel_comercial`, `3_vetorial_validado`, `4_alta_fidelidade`.
   - chave ausente ≡ `0_bruto_aproximado` (não é erro);
   - valor presente e desconhecido ≡ erro (`ContratoInvalido`);
   - `renderizavel` só para `2_`/`3_`/`4_` (por enumeração, não ordenação).
8. **Brutas**: `contorno_externo = null`, `vazios_internos = []`; o consumidor
   deve tratar. Campos de equivalência/auditoria continuam válidos.
9. **`versao_schema`**: obrigatório, para evolução futura sem quebrar
   consumidores. Não é gravado nos JSONs — vive no contrato.

## Validação de schema

`contrato/schemas/biblioteca_consumo.schema.json` é a face de máquina
(JSON Schema draft-07), publicada como artefato. **Ela ainda não é validada por
uma implementação oficial de JSON Schema.** O ambiente não tem a biblioteca
`jsonschema` e ela não foi adotada só para este sprint. Os testes usam uma
**validação estrutural limitada** própria, que cobre apenas as palavras-chave
`type`, `required`, `properties`, `items`, `enum`, `anyOf`, `$ref` — não
implementa `oneOf`/`allOf`/`not`, `patternProperties`, `format`,
`additionalProperties`, limites numéricos etc. Não substitui `jsonschema` nem
prova conformidade com o padrão. Adoção adiada até uso concreto além do teste
(ADR-009, seção 9).
