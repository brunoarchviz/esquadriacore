# EsquadriaCore — E.4B etapa 10: lote 2, o quadro da janela

Documento autocontido.

---

## 0. Estado

| perfil | situação |
|---|---|
| SU-039 · SU-024 | concluídos, commitados em `258509d` |
| SU-009 | reenquadrado, commitado |
| SU-053 | `CANDIDATO_GEOMETRICO_APROVADO`, commitado |
| SU-102 | forma aprovada, escala aguardando medição física |
| **SU-001 · SU-002 · SU-003** | **`CANDIDATO_GEOMETRICO_APROVADO`** — revisão visual aprovada |

---

## 1. Fonte

Os três perfis vêm do mesmo card: **Centenário, página 211 do PDF**. São o quadro da
janela — trilho superior, trilho inferior e marco lateral.

| perfil | ROI | função |
|---|---|---|
| SU-001 | `[0.285, 0.098, 0.755, 0.325]` | trilho superior 2 planos |
| SU-002 | `[0.255, 0.395, 0.745, 0.615]` | trilho inferior 2 planos |
| SU-003 | `[0.255, 0.675, 0.725, 0.865]` | marco lateral com mata-junta |

---

## 2. A decisão do SU-002

O parâmetro recebido era `35 × 47 mm`. A aquisição reprovou com **102,51 %** de erro de
aspecto.

Causa: no card, a cota **35 mede o vão entre os dois trilhos**, não a largura externa. O
perfil se estende bem além dos dois lados. É o mesmo padrão do SU-102, onde as cotas 10 e
11 também são segmentos internos.

Evidência da largura correta:

```
escala derivada da altura cotada (47 mm) : 23,745 px/mm
bbox raster                              : 1683 × 1116 px
largura implicada                        : 70,88 mm

hipótese 71 × 47 → aspecto 1,5106 vs medido 1,5081 → erro 0,17 %   PASSA
```

Três reforços independentes:

1. **71 mm é a largura do SU-001 e do SU-003** — os três formam o mesmo quadro e
   compartilham a largura de marco.
2. As escalas dos três cards batem: 23,818 / 23,745 / 23,846 px/mm.
3. O card do **SU-001 cota 71 e 33 diretamente**, e traz o mesmo "35" embaixo — o vão
   entre trilhos é padrão do quadro, não dimensão de perfil.

Registrado como evidência composta, com a origem de cada eixo declarada:

```yaml
fonte_dimensional_primaria:
  tipo: evidencia_composta
  altura:  {valor_mm: 47.0, origem: cota_visual_do_card}
  largura: {valor_mm: 71.0, origem: derivacao_validada}

cotas_internas:
  - {valor_mm: 35.0, funcao: vao_entre_trilhos, usar_como_envelope: false}
  - {valor_mm: 16.0, funcao: altura_do_trilho,  usar_como_envelope: false}
  - {valor_mm: 13.0, funcao: aba_esquerda,      usar_como_envelope: false}
```

A procedência diz explicitamente que **71 não aparece como cota no card do SU-002**.

---

## 3. Resultados

| perfil | dimensões | aspecto medido | esperado | erro | pontos | comp. | vazios | F1 |
|---|---|---|---|---|---|---|---|---|
| SU-001 | 71,00 × 33,00 | 2,1425 | 2,1515 | **0,42 %** | 187 | 1 | 0 | 1,0000 |
| SU-002 | 71,00 × 47,00 | 1,5081 | 1,5106 | **0,17 %** | 163 | 1 | 0 | 1,0000 |
| SU-003 | 71,00 × 26,00 | 2,7145 | 2,7308 | **0,60 %** | 83 | 1 | 0 | 1,0000 |

Tolerância de 0,75 % preservada — não foi afrouxada.

### Contaminação: nenhuma

O gate retornou `None` nos três. Sem linha de cota conectada, sem seta aderida, sem
perfil de referência incorporado. As ROIs não tocam nenhuma borda. Estratégia registrada:
`LIMPO` — nenhuma remoção local foi necessária.

### Sobre os 83 pontos do SU-003

Chamou atenção por ser menos da metade dos outros. Conferido contra o card: o perfil é
geometricamente simples mesmo — alma horizontal, duas paredes de topo e duas aletas finas
do mata-junta. A máscara reproduz o desenho. E o card dele **cota 71 e 26 diretamente**.

### Vazios

Zero nos três. As seções são abertas: os bolsos dos trilhos são "C" abertos, não câmaras
fechadas. Mesma distinção já estabelecida no SU-053 — câmara funcional não é sinônimo de
ciclo fechado no contorno 2D.

---

## 4. Reprodutibilidade

Dezoito artefatos, seis por perfil, com hashes idênticos entre execução no destino e em
diretório temporário. JSONs semanticamente equivalentes.

| perfil | contorno_bruto | assinatura | metricas | svg |
|---|---|---|---|---|
| SU-001 | `709da5f136295e79` | `6d3aade2820bb532` | `8145b93870f82ba9` | `4d643adc691590c0` |
| SU-002 | `9e3f080a5ce18b38` | `2101f55044c7ed09` | `eec105159b424718` | `1f47ce9522b22ca0` |
| SU-003 | `2f9ae5527c88eaaa` | `c954a206a5ba8719` | `ef09de51ffabfbbd` | `a64e7ac7d05924e9` |

`operacoes_limpeza.json` é `ed644b44ced8717d` nos três — todos com o mesmo log de
aquisição limpa.

---

## 5. Validação de schema do config

Renomear chave quebrou testes três vezes nesta sprint, sempre pelo mesmo caminho: o erro
só aparecia quando um teste distante tentava ler a chave antiga.

Criado `curadoria/aquisicao/validar_config.py` — específico deste config, não framework
genérico. Valida por perfil: chaves obrigatórias, chaves depreciadas, coerência entre
estado e dimensões, integridade das fontes, e declaração de motivos.

Achados na primeira execução:

1. **`SU-002: fonte_dimensional` — chave depreciada.** Era inconsistência minha desta
   mesma rodada: nomeei `fonte_dimensional` enquanto o SU-053 usa
   `fonte_dimensional_primaria`. Corrigida — e a correção quebrou dois testes na hora,
   que era exatamente o ponto.

2. **Três idiomas de procedência de zona coexistem no config:**
   - `roi_status: CONFIRMADO_BRUNO` — selo novo, do SU-053
   - `atribuicao_geometrica: medida` — SU-009, SU-024
   - `atribuicao_geometrica: zona_curada` — SU-040, SU-056

   Os três são procedência humana legítima. O validador aceita todos.

3. **`SU-041` tem `zona_protegida` com `atribuicao_geometrica: pendente`** — zona existe,
   mas a atribuição está declarada pendente. É incoerência real, **não corrigida**: o
   SU-041 está congelado e mexer nele está fora do escopo. Fica registrada em
   `PENDENCIAS_CONHECIDAS` no teste, com um segundo teste que falha se ela sumir sem
   alguém atualizar a lista — para a pendência não virar lixo que esconde problema futuro.

---

## 6. Aprovação visual

Painel revisado e aprovado. Confirmado item a item:

**SU-001** — dois trilhos preservados; ganchos inferiores preservados; travessa superior
completa; montantes externos completos; nenhuma contaminação gráfica.

**SU-002** — dois trilhos superiores completos; ganchos preservados; base e extremidades
completas; 71 mm como envelope externo e 35 mm como vão interno entre trilhos; nenhuma
perda funcional no contorno comercial.

**SU-003** — alma horizontal preservada; paredes laterais preservadas; duas aletas
inclinadas preservadas; mata-junta completo; 83 pontos compatíveis com a simplicidade da
seção.

Os painéis de diferença mostram apenas ajustes controlados de simplificação das bordas,
sem perda de componentes e sem mudança topológica.

Os três passam a `CANDIDATO_GEOMETRICO_APROVADO` **somente na camada de curadoria**. Não
existe geometria oficial em `dados/`.

---

## 7. Suíte

```
pytest tests/test_aquisicao_contornos.py -q   ->  161 passed em 48,74 s   EXIT 0
pytest -q                                     ->  (relançada após a aprovação)
```

---

## 8. Arquivos

Modificados:

```
curadoria/aquisicao/configs/e4b_suprema.json   SU-001/002/003 + correção do SU-002
tests/test_aquisicao_contornos.py              +13 regressões
```

Novos:

```
curadoria/aquisicao/validar_config.py
curadoria/composicao/painel_lote2.py
curadoria/composicao/painel_lote2_su001_su002_su003.png
curadoria/contornos/SU-001/  SU-002/  SU-003/     18 artefatos
curadoria/handoffs/e4b/etapa_10_lote2_su001_su002_su003.md
```

`dados/`, `domain/`, `contrato/`, `docs/`, `VERSION`, `CHANGELOG.md` intactos.
SU-039, SU-024, SU-009, SU-053 e SU-102 não reabertos. SU-040 e SU-041 não tocados.

Commits `258509d` e `095ba09` preservados. **Nenhum commit novo, nenhum push.**

---

## 9. Próximo passo

Commits C (técnico) e D (evidências) do lote 2.

Depois deles, o E.4B fica com sete perfis fechados na curadoria — SU-039, SU-024, SU-009,
SU-053, SU-001, SU-002 e SU-003 — e um único pendente: o SU-102, aguardando medição
física da escala.
