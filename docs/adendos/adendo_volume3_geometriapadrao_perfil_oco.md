# Adendo ao Volume 3 — GeometriaPadrao com contorno externo e vazios internos

Este adendo complementa o Volume 3 da documentação v1.0 (congelada) sem alterá-lo.
Origem: ADR-008.

## Evolução da entidade GeometriaPadrao

A entidade ganhou três campos opcionais (coordenadas em milímetros), coexistindo
com o formato legado `contorno_mm`:

```python
contorno_externo: Optional[list] = None   # lista de (x, y) da silhueta externa
vazios_internos: Optional[list] = None    # lista de listas de (x, y) — câmaras ocas
nivel_contorno: str = "0_bruto_aproximado"
```

Regras de domínio (resumo do ADR-008):

- `contorno_externo` é a silhueta externa da seção; `vazios_internos` são as
  câmaras ocas (pode ser lista vazia).
- `contorno_mm` permanece válido apenas como formato legado (polígono único
  preenchido); quando os dois formatos coexistem, o novo é preferencial.
- O modelo não implica precisão CAD e não autoriza uso para fabricação/CNC.
- `nivel_contorno` é a escala de fidelidade do Sprint E.2 (metadado, não
  entidade nova): `0_bruto_aproximado` → `1_envelope_funcional` →
  `2_renderizavel_comercial` → `3_vetorial_validado` → `4_alta_fidelidade`.
- Campos de curadoria do contorno (`status_contorno`, `metodo_contorno`,
  `evidencia_contorno`) vivem no dado (`dados/geometrias.json`), não na entidade.
- Homologação de equivalência (eixo da curadoria de mercado) e validação de
  contorno (eixo de fidelidade geométrica) são independentes: uma geometria pode
  estar `homologada` com contorno ainda `bruto_aproximado`.
