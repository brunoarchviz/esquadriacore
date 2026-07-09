"""
EsquadriaCore — providers/ocr
==============================
OcrProvider: extrai perfis de PDFs onde o texto não é extraível diretamente.

Estratégia:
1. Rasterizar cada página com pdftoppm (alta resolução)
2. Rodar Tesseract sobre a imagem
3. Aplicar os mesmos padrões de código/peso do PdfTextoProvider

Caso real que motivou este Provider (ADR-003, Sprint D):
- Alcoa (seção Suprema, págs 170-183): vetores sem texto extraível
"""

import re
import subprocess
import tempfile
from pathlib import Path

from domain.entidades import Perfil, QualidadePerfil, ProviderFailure
from providers.base import Provider

PADRAO_CODIGO = re.compile(r"\b([A-Z]{1,4}-\d{2,4})\b")
# "kg/mt" (com t) aparece em dado real: catálogo Vitral Sul
PADRAO_PESO   = re.compile(r"\b(\d+[,\.]\d+)\s*[Kk][Gg]/[Mm][Tt]?\b")


class OcrProvider(Provider):
    """Extrai perfis via OCR (pdftoppm + Tesseract).
    Usa as mesmas regras de código/peso do PdfTextoProvider — só a origem
    do texto muda (imagem em vez de camada de texto nativa)."""

    def __init__(self, caminho_pdf: str, pagina_inicio: int, pagina_fim: int,
                 fabricante: str, prefixo_id: str = "", dpi: int = 300):
        self.caminho_pdf   = caminho_pdf
        self.pagina_inicio = pagina_inicio
        self.pagina_fim    = pagina_fim
        self.fabricante    = fabricante
        self.prefixo_id    = prefixo_id or fabricante.upper().replace(" ", "")
        self.dpi           = dpi

    def extrair_perfis(self) -> list[Perfil]:
        perfis: list[Perfil] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for pagina in range(self.pagina_inicio, self.pagina_fim + 1):
                texto = self._ocr_pagina(pagina, tmpdir)
                perfis.extend(self._extrair_da_pagina(texto, pagina))
        return perfis

    def _ocr_pagina(self, pagina: int, tmpdir: str) -> str:
        """Rasteriza a página e extrai texto via Tesseract."""
        prefixo = str(Path(tmpdir) / f"pag{pagina:04d}")
        try:
            subprocess.run(
                ["pdftoppm", "-jpeg", "-r", str(self.dpi),
                 "-f", str(pagina), "-l", str(pagina),
                 self.caminho_pdf, prefixo],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise ProviderFailure(f"pdftoppm falhou na página {pagina}: {e}") from e

        imagens = sorted(Path(tmpdir).glob(f"pag{pagina:04d}*.jpg"))
        if not imagens:
            raise ProviderFailure(f"pdftoppm não gerou imagem para página {pagina}")

        try:
            resultado = subprocess.run(
                ["tesseract", str(imagens[0]), "stdout",
                 "-l", "por+eng", "--psm", "6"],
                capture_output=True, text=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise ProviderFailure(f"Tesseract falhou na página {pagina}: {e}") from e

        return resultado.stdout

    def _extrair_da_pagina(self, texto: str, pagina: int) -> list[Perfil]:
        """Aplica os mesmos padrões de código/peso do PdfTextoProvider."""
        perfis = []
        linhas = texto.splitlines()
        for i, linha in enumerate(linhas):
            m_codigo = PADRAO_CODIGO.search(linha)
            if not m_codigo:
                continue
            codigo = m_codigo.group(1)

            # busca peso nas próximas 5 linhas (OCR pode separar código e peso)
            peso_txt = None
            janela = " ".join(linhas[i:i+5])
            m_peso = PADRAO_PESO.search(janela)
            if m_peso:
                peso_txt = m_peso.group(1)

            peso_valido = peso_txt is not None
            perfis.append(Perfil(
                id=f"{self.prefixo_id}-{codigo}",
                fabricante=self.fabricante,
                codigo_fabricante=codigo,
                peso_kg_m=(float(peso_txt.replace(",", ".")) if peso_valido else None),
                peso_suspeito=not peso_valido,
                fonte=f"{self.caminho_pdf}, página {pagina} (OCR)",
                qualidade=QualidadePerfil(
                    codigo_valido=True,
                    peso_valido=peso_valido,
                ),
                estado_ciclo_vida="extraido",
            ))
        return perfis
