# Volume 3 — Modelo de Domínio

---
**Versão:** 1.0.0
**Status:** Estável
**Sprint de origem:** Sprint A
**Última atualização:** 2026-07-08
**ADRs relacionados:** ADR-001, ADR-002, ADR-004, ADR-005
**Implementação correspondente:** Core Engine (Fase 0), prova de conceito
GeometriaPadrao
**Dependências:** Volume 1 (Visão Geral), Volume 4 (ADRs)
**Responsável:** Bruno, Claude, ChatGPT
**Volumes dependentes:** 2, 6, 7, 8, 9, 11
---

## Visão geral das entidades

```
FamíliaMercado
     │ (vocabulário de mercado — sempre presente quando aplicável)
     ▼
Perfil ──── PerfilGeometria ────► GeometriaPadrao
  │                                (contorno vetorial, versão, homologação)
  │
  ▼
Componente (Perfil | Ferragem | Vidro)
  │
  ▼
Tipo (composição de Componentes segundo uma Regra)
  │
  ▼
Cena Técnica (instâncias posicionadas — aponta pra Componente, nunca copia)
  │
  ▼
Vista (parâmetros de apresentação — nunca dado físico)
  │
  ▼
Renderer (consome só Vistas)
  │
  ▼
Imagem (derivada, nunca armazenada como fonte de verdade)
```

---

## Diagrama de cardinalidades

```
FamíliaMercado
       │ 1:N
       ▼
    Perfil ──── 1:1 ──── PerfilGeometria ──── N:1 ──── GeometriaPadrao

    Perfil
       │ 1:1 (é-um)
       ▼
   Componente
       │ N:1
       ▼
      Tipo
       │ 1:N
       ▼
 Cena Técnica
       │ 1:N
       ▼
     Vista
       │ N:1
       ▼
   Renderer
```

Leitura: uma FamíliaMercado agrupa N Perfis de fabricantes diferentes; cada Perfil
associa-se a exatamente uma GeometriaPadrao por vez (via PerfilGeometria), mas uma
GeometriaPadrao pode ser referenciada por N Perfis (mecanismo de reaproveitamento
validado no ADR-005); um Tipo agrupa N Componentes; uma Cena Técnica pode ter N
Vistas (frontal, isométrica, explodida); um Renderer atende N Vistas.

## Diagrama de dependência inversa (como o Renderer resolve uma imagem)

**Nota do Claude:** o diagrama de cardinalidades acima mostra o fluxo de definição
do domínio (de cima pra baixo). Este mostra o fluxo de resolução em tempo de
renderização (de baixo pra cima) — útil pra quem for implementar o Renderer de
verdade, é literalmente a ordem de resolução de referências.

```
Renderer
   ↑ recebe
 Vista
   ↑ referencia
 Cena Técnica
   ↑ referencia (N instâncias)
 Tipo / Componente
   ↑ é-um
 Perfil
   ↑ resolve via PerfilGeometria
GeometriaPadrao
```

## Fluxo de vida do Perfil

Diferente do Estado documental (Proposto/Validado/Estável/Obsoleto, aplicável a
entidades e documentos), um Perfil individual percorre um ciclo de vida
operacional próprio dentro do Pipeline:

```
Extraído → Normalizado → Curado → Homologado → Disponível → Obsoleto
```

- **Extraído** — dado bruto retirado de um Provider (ex: código+peso do PDF).
- **Normalizado** — validado estruturalmente (Volume 9), pronto para curadoria.
- **Curado** — classificação funcional atribuída (categoria, orientação, aplicação).
- **Homologado** — geometria confirmada, associada a uma GeometriaPadrao via
  PerfilGeometria (ou geometria própria, se não compartilhada).
- **Disponível** — pronto para uso pelo Core Engine.
- **Obsoleto** — descontinuado pelo fabricante ou substituído, mantido por
  rastreabilidade.

Detalhamento operacional deste fluxo pertence ao Volume 6 (Pipeline de Aquisição).

---

## FamíliaMercado

**Estado:** Estável

**Persistência:** Persistente (cadastro de referência, raramente alterado)

**O que é:** o vocabulário usado pelo mercado para se referir a uma linha de
esquadria (ex: "Suprema", "Gold"), independente de qual fabricante a produz.

**O que possui (atributos próprios):** nome canônico, origem histórica, bitola,
descrição, lista de aliases por fabricante (prefixo de código, nome local usado).

**O que referencia (relação):** nenhuma entidade — é referenciada pelo Perfil, não
o contrário.

**O que nunca conhece:** geometria, fabricante específico como "dono", ou
intercambiabilidade técnica.

**Quem depende dela:** Pipeline de Aquisição (marcação de Perfil), interfaces de
busca/relatório.

**Exemplo real:** SUPREMA — origem Alcoa, início dos anos 90, bitola 25mm; aliases:
Alcoa (SU), Tamboré/Centenário (TMS), Vitral Sul (SU, "Nobile 2.5 - Suprema"), ASA
(MG25, "Mega 25").

---

## GeometriaPadrao

**Estado:** Validado (implementado e testado com GEO-SU-019; ainda não em escala)

**Persistência:** Persistente (ativo de engenharia, versionado)

**O que é:** um ativo de engenharia reutilizável — o contorno vetorial curado e
homologado de um perfil, independente de qual fabricante o implementa.

**O que possui (atributos próprios):** contorno em mm (polígono), versão, status
de homologação (bruto/homologado), referência ao SVG bruto de origem (auditoria).

**O que referencia (relação):** nenhuma entidade — é referenciada por N Perfis via
PerfilGeometria, não o contrário.

**O que nunca conhece:** peso, fabricante, preço, disponibilidade — esses são do
Perfil.

**Quem depende dela:** Renderer, Curadoria Geométrica, PerfilGeometria.

**Quem pode usá-la:** Renderer (via resolução Perfil → PerfilGeometria →
GeometriaPadrao), processo de Curadoria Geométrica.

**Exemplo real:** GEO-SU-019, compartilhada entre `ALCOA-SU-019` e
`VITRALSUL-SU-019` — testado e confirmado: ambos os Perfis geram imagem com
geometria idêntica.

---

## PerfilGeometria

**Estado:** Validado

**Persistência:** Persistente (registro de auditoria — nunca descartável, ver
ADR-005)

**O que é:** entidade de associação auditável entre um Perfil e uma GeometriaPadrao.
A decisão de compartilhar geometria é **sempre curadoria humana caso a caso**, nunca
inferida automaticamente pela FamíliaMercado.

**O que possui (atributos próprios):** nível de confiança, responsável pela
homologação, método de validação, data, observações.

**O que referencia (relação):** um Perfil (perfil_id) e uma GeometriaPadrao
(geometria_padrao_id).

**O que nunca conhece:** regra de negócio de quando reaproveitar geometria — essa
decisão vem de fora, de quem homologa.

**Quem depende dela:** Perfil (via referência), Renderer (indiretamente, ao
resolver a cadeia).

---

## Perfil

**Estado:** Estável

**Persistência:** Persistente

**O que é:** a implementação de um fabricante específico de um item de catálogo.

**O que possui (atributos próprios):** fabricante, código local, peso, acabamento,
liga.

**O que referencia (relação):** FamíliaMercado (opcional), geometria via
PerfilGeometria (nunca geometria embutida diretamente).

**O que nunca conhece:** como é renderizado, ou regra de montagem de um Tipo.

**Quem depende dele:** Componente, Cena Técnica (por referência).

---

## Componente

**Estado:** Estável

**Persistência:** Persistente (geralmente derivado de um Perfil/Ferragem/Vidro já
persistente)

**O que é:** abstração comum sobre Perfil, Ferragem e Vidro — qualquer peça que
compõe um Tipo.

**O que possui (atributos próprios):** categoria (função: marco, folha, montante,
trilho...), orientação (vertical/horizontal/ambos), aplicação (porta, janela,
box...).

**O que referencia (relação):** o Perfil/Ferragem/Vidro concreto que implementa.

---

## Tipo

**Estado:** Estável

**Persistência:** Persistente

**O que é:** uma composição de Componentes segundo uma Regra de montagem (ex:
"Janela de Correr Simples").

**O que possui (atributos próprios):** a Regra aplicada (hoje texto/parâmetro, ver
observação abaixo), dimensões gerais.

**O que referencia (relação):** a lista de Componentes que participam.

**O que nunca conhece:** como será desenhado — isso é responsabilidade da Cena
Técnica e da Vista.

**Quem depende dele:** Cena Técnica.

---

## Cena Técnica

**Estado:** Estável

**Persistência:** Transitória (gerada por Tipo, descartável e regerável)

**O que é:** o posicionamento espacial de instâncias de Componentes para um Tipo
específico.

**O que possui (atributos próprios):** posição, rotação, comprimento por
instância.

**O que referencia (relação):** o Componente/Perfil de cada instância — nunca
copia dado físico dele.

**O que nunca conhece:** peso, espessura ou qualquer dado físico do Componente —
ela referencia, nunca copia (validado no ADR-001 e testado na Fase 0).

**Quem depende dela:** Vista.

---

## Vista

**Estado:** Estável

**Persistência:** Transitória (parâmetro de renderização, descartável)

**O que é:** os parâmetros de apresentação de uma Cena Técnica — como ela deve ser
desenhada.

**O que possui (atributos próprios):** ângulo, tipo de projeção, escala, estilo
visual, nível de detalhe, estilo de sombreamento, cores/estilo de material.

**O que referencia (relação):** exatamente uma Cena Técnica.

**O que nunca conhece:** dado físico real (espessura, liga) — se precisar, pergunta
à Cena/Componente, nunca guarda cópia (ADR-001, ADR-002).

**Quem depende dela:** Renderer.

---

## Renderer

**Estado:** Estável (detalhe de motor de renderização — matplotlib vs. Three.js —
pertence ao Volume 7, não ao domínio; nota do Claude: corrigido após observação do
ChatGPT de que Volume 3 deve sobreviver a qualquer troca de tecnologia)

**Persistência:** N/A — Renderer é código/serviço, não dado.

**O que é:** o motor que transforma uma Vista em imagem.

**O que possui (atributos próprios):** nenhum estado persistente — é motor de
execução, não dado.

**O que referencia (relação):** a Vista recebida como entrada, no momento da
renderização.

**O que nunca conhece:** regra de engenharia, regra de montagem, ou fabricante
(ADR-002) — comprovado ao renderizar Perfis de fabricantes diferentes sem
distinção.

**Quem depende dele:** Exportador de imagem (PNG/SVG), futuras Vistas adicionais
(explodida, corte).

---

---

## Invariantes do Domínio

Regras que devem ser sempre verdadeiras, independente de implementação — base para
a futura suíte de testes (Sprint C):

- Todo Perfil pertence exatamente a um Fabricante.
- Todo Perfil associa-se a no máximo uma GeometriaPadrao por vez (via PerfilGeometria).
- Toda GeometriaPadrao pode ter zero, um ou múltiplos Perfis associados.
- Toda associação Perfil↔GeometriaPadrao é auditável (responsável, método, data).
- FamíliaMercado nunca implica intercambiabilidade técnica entre Perfis.
- Toda Vista referencia exatamente uma Cena Técnica.
- Toda Cena Técnica referencia Componentes por identificador, nunca copia seus dados físicos.
- Renderer nunca referencia Perfil diretamente — sempre via Vista → Cena → Componente.
- Todo Tipo é uma composição de Componentes segundo uma Regra — nunca um desenho fixo armazenado.
- Renderer nunca altera dado — apenas lê e produz imagem (somente leitura).
- Pipeline de Aquisição nunca cria uma FamíliaMercado nova por conta própria — associação a uma FamíliaMercado existente é automatizável, criação de uma nova é decisão humana.
- Vista nunca modifica a Cena Técnica que referencia — leitura apenas.
- GeometriaPadrao nunca conhece qual fabricante a utiliza — isso é papel do Perfil/PerfilGeometria.

---

## Observação registrada — conceito de "Regra" ainda não formalizado

O conceito de Regra (ex: "Janela de Correr 2 Folhas exige 2 folhas + 2 trilhos +
marco + fecho + encontro + vidro + limites/posições") aparece recorrentemente em
Tipo, mas ainda não é uma entidade própria do domínio — hoje é tratado como
parâmetro textual/implícito de Tipo. **Não será formalizado como entidade agora**,
por falta de evidência suficiente (poucos Tipos implementados até o momento). A
recorrência será reavaliada quando existirem múltiplos Tipos reais implementados
que revelem o padrão de forma inequívoca — mantendo a Regra 1 da Constituição.

## Observação registrada — Aggregate Roots e Value Objects (DDD) ainda não aplicados

Terminologia formal de DDD (Aggregate Root, Value Object) foi sugerida para o
domínio, mas não será adotada nesta versão: Aggregate Roots só ganham sentido
prático quando existir camada de persistência/transação real que precise de limite
de consistência explícito — isso ainda não foi implementado. Value Objects (Peso,
Bitola, Escala, Posição, Rotação, Cor, Material) são hoje campos tipados simples;
formalizá-los como categoria própria do domínio só se justifica quando um problema
real de modelagem aparecer (ex: necessidade de validação ou igualdade que
primitivos não resolvam). Ambos registrados como observação para reavaliação
futura — mesma régua aplicada à Regra acima.

---

## Evolução futura registrada (não aplicada agora)

Identificadores permanentes por entidade (ex: DOM-001 = FamíliaMercado, DOM-002 =
GeometriaPadrao, DOM-003 = Perfil, DOM-004 = PerfilGeometria...), permitindo que
ADRs e outros Volumes referenciem entidades sem depender da posição no texto (ex:
"Afeta: DOM-002, DOM-004"). Registrado como evolução natural quando o domínio
estabilizar ainda mais — não aplicado nesta versão para não adicionar uma camada de
indireção sem necessidade comprovada ainda.

---

## Camadas estáveis vs. em evolução

**Nota do Claude:** isso é apenas uma leitura agregada do campo Estado que cada
entidade já possui — não é informação nova, é uma vista de conveniência para quem
quer saber rápido "onde posso mexer com segurança" sem abrir cada seção.

| Praticamente estável | Ainda em evolução |
|---|---|
| FamíliaMercado | Pipeline (Providers novos ainda virão) |
| GeometriaPadrao | Provider (só 1 implementado) |
| Perfil | Biblioteca de Conhecimento (não existe em escala) |
| Componente | Compatibilidades (não formalizada) |
| Cena Técnica, Vista, Renderer | Regra (observação registrada, não é entidade ainda) |

---

## Resumo por entidade (leitura rápida)

| Entidade | Responsabilidade | Fonte da verdade |
|---|---|---|
| FamíliaMercado | Vocabulário de mercado | Domínio (curadoria humana) |
| GeometriaPadrao | Geometria homologada compartilhada | Biblioteca de Conhecimento |
| PerfilGeometria | Associação auditável Perfil↔Geometria | Curadoria |
| Perfil | Dados físicos por fabricante (peso, acabamento) | Fabricante (catálogo de origem) |
| Componente | Categoria/orientação/aplicação | Curadoria |
| Tipo | Composição de Componentes por Regra | Domínio |
| Cena Técnica | Posicionamento espacial | Core Engine (gerado) |
| Vista | Configuração visual | Core Engine (gerado) |
| Renderer | Execução da renderização | Core Engine (código) |

## Tabela-resumo de responsabilidades

| Entidade | Conhece | Nunca conhece |
|---|---|---|
| FamíliaMercado | vocabulário de mercado, aliases | geometria, fabricante "dono" |
| GeometriaPadrao | contorno, versão, homologação | peso, fabricante, preço |
| PerfilGeometria | associação Perfil↔Geometria, auditoria | regra automática de quando associar |
| Perfil | fabricante, código, peso, acabamento | renderização, regra de montagem |
| Componente | categoria, orientação, aplicação | posição espacial |
| Tipo | composição, regra aplicada | forma de desenho |
| Cena Técnica | posição/rotação/comprimento (por referência) | dado físico do Componente |
| Vista | ângulo, escala, estilo | dado físico real |
| Renderer | o que a Vista manda | regra de engenharia, fabricante |
