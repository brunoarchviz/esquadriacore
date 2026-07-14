"""
EsquadriaCore — contrato
========================
Fronteira de saída (leitura) da biblioteca homologada. Estabiliza como os
dados já existentes em dados/*.json são consumidos por qualquer aplicação
futura, sem criar entidade de domínio nova e sem alterar a fonte de verdade.

Ver docs/ADR-009_contrato_minimo_de_consumo.md e
docs/adendos/adendo_contrato_consumo.md.
"""
from contrato.consumo import (  # noqa: F401
    CONTRATO_CONSUMO_VERSAO,
    NIVEIS_RECONHECIDOS,
    NIVEIS_RENDERIZAVEIS,
    FONTE_NOVO,
    FONTE_LEGADO,
    BoundingBoxDTO,
    GeometriaConsumivel,
    AssociacaoConsumivel,
    BibliotecaConsumivel,
    ContratoInvalido,
    carregar_geometrias,
    carregar_associacoes,
    carregar_biblioteca,
)
