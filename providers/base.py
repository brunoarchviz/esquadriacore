"""
EsquadriaCore — providers/base
==============================
Contrato Provider (ADR-003), isolado de qualquer implementação concreta.

Correção I-1 da auditoria arquitetural do Sprint 3.5: o contrato vivia dentro de
pdf_texto.py (uma implementação), o que forçaria o futuro OCRProvider a importar
de dentro do arquivo de PDF. Agora contrato e implementações moram em lugares
separados — pipeline e cada provider importam o contrato daqui.
"""

from abc import ABC, abstractmethod

from domain.entidades import Perfil


class Provider(ABC):
    """Contrato de aquisição: qualquer fonte (PDF, OCR, DXF, API, cadastro
    manual) implementa extrair_perfis() e devolve Perfis normalizados.

    O Pipeline depende apenas deste contrato, nunca de uma implementação
    concreta (ADR-003)."""

    @abstractmethod
    def extrair_perfis(self) -> list[Perfil]:
        ...
