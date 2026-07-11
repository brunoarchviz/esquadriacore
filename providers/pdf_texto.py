"""
EsquadriaCore — providers
=========================
Contrato Provider (ADR-003) e implementação PdfTextoProvider.

Consolidação do Sprint 3.5: os parsers da Linha 25 e da Linha 30 eram código
quase idêntico duplicado entre protótipos — aqui viram UMA implementação
parametrizada por intervalo de páginas. Zero funcionalidade nova.

Casos reais conhecidos que este Provider NÃO cobre (ver Volume 6):
- Alcoa (seção Suprema): vetor sem texto extraível -> exige Provider OCR (futuro)
- Vitral Sul: desenho raster embutido -> exige Provider OCR (futuro)
"""

import re
import subprocess
from dataclasses import dataclass

from domain.entidades import Perfil, QualidadePerfil, ProviderFailure
from providers.base import Provider


# ---------------------------------------------------------------------------
# Implementação: PDF com texto extraível (caso Centenário/Tamboré/Euroshow)
# ---------------------------------------------------------------------------

@dataclass
class PalavraPosicionada:
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    texto: str


PADRAO_CODIGO = re.compile(r"^[A-Z]{1,4}-\d{2,4}$")
PADRAO_PESO = re.compile(r"^[\d]+[,\.][\d]+$")


class PdfTextoProvider(Provider):
    """Extrai código+peso por POSIÇÃO real das palavras na página (não regex em
    texto corrido — necessário para layouts em grade de 2-3 colunas, aprendizado
    real da Fase 1)."""

    def __init__(self, caminho_pdf: str, pagina_inicio: int, pagina_fim: int,
                 fabricante: str, prefixo_id: str = "",
                 padrao_codigo: re.Pattern | None = None):
        self.caminho_pdf = caminho_pdf
        self.pagina_inicio = pagina_inicio
        self.pagina_fim = pagina_fim
        self.fabricante = fabricante
        self.prefixo_id = prefixo_id or fabricante.upper().replace(" ", "")
        # catálogos da era Hydro grafam código sem hífen ("LG159") — quem
        # precisar passa um padrão próprio; o default preserva o comportamento
        # validado nos 5 catálogos da Suprema
        self.padrao_codigo = padrao_codigo or PADRAO_CODIGO

    # -- infra -------------------------------------------------------------

    def _palavras_da_pagina(self, pagina: int) -> list[PalavraPosicionada]:
        try:
            out = subprocess.run(
                ["pdftotext", "-bbox", "-f", str(pagina), "-l", str(pagina),
                 self.caminho_pdf, "-"],
                capture_output=True, text=True, check=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise ProviderFailure(
                f"pdftotext falhou na página {pagina} de {self.caminho_pdf}: {e}"
            ) from e

        palavras = []
        for m in re.finditer(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
            r'yMax="([\d.]+)">([^<]*)</word>', out,
        ):
            xmin, ymin, xmax, ymax, texto = m.groups()
            palavras.append(PalavraPosicionada(
                float(xmin), float(ymin), float(xmax), float(ymax), texto))
        return palavras

    # -- extração ----------------------------------------------------------

    def extrair_perfis(self) -> list[Perfil]:
        perfis: list[Perfil] = []
        for pagina in range(self.pagina_inicio, self.pagina_fim + 1):
            palavras = self._palavras_da_pagina(pagina)
            for p in palavras:
                if not self.padrao_codigo.match(p.texto):
                    continue
                peso_texto = self._buscar_peso_abaixo(p, palavras)
                peso_valido = peso_texto is not None
                perfil = Perfil(
                    id=f"{self.prefixo_id}-{p.texto}",
                    fabricante=self.fabricante,
                    codigo_fabricante=p.texto,
                    peso_kg_m=(float(peso_texto.replace(",", "."))
                               if peso_valido else None),
                    peso_suspeito=not peso_valido,   # regra do Volume 9 (caso Euroshow)
                    fonte=f"{self.caminho_pdf}, página {pagina}",
                    qualidade=QualidadePerfil(
                        codigo_valido=True,
                        peso_valido=peso_valido,
                        # vetor/descrição/escala: preenchidos por etapas
                        # posteriores do Pipeline (recorte SVG etc.)
                    ),
                    estado_ciclo_vida="extraido",
                )
                perfis.append(perfil)
        return perfis

    @staticmethod
    def _buscar_peso_abaixo(codigo: PalavraPosicionada,
                            palavras: list[PalavraPosicionada]) -> str | None:
        """Peso = primeiro número decimal logo abaixo do código (janela de 45pt,
        calibrada nas Fases 1-2 com Centenário e validada na Euroshow)."""
        candidatos = sorted(
            (q for q in palavras
             if codigo.ymin + 3 < q.ymin < codigo.ymin + 45),
            key=lambda q: q.ymin,
        )
        for q in candidatos:
            if PADRAO_PESO.match(q.texto):
                return q.texto
        return None
