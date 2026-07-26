"""
EsquadriaCore — curadoria/aquisicao
====================================
Pipeline OFICIAL de aquisição de contornos por raster (diretriz v1.2 + pacote
de aprovação): PDF → PNG lossless → card → máscara → contorno bruto →
limpeza comercial transacional → validação → aprovação visual do Bruno.

Ferramenta de CURADORIA: nunca escreve em dados/, domain/, contrato/,
VERSION ou CHANGELOG. Depende de opencv-python-headless (ver
requirements-curadoria.txt) — dependência proibida fora deste pacote.
"""
