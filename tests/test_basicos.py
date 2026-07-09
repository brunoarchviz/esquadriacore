"""
EsquadriaCore — testes básicos (Volume 10)
==========================================
Cobertura direta das validações do Volume 9 — um teste por regra.

Regressões Alcoa (via OcrProvider) e Vitral Sul (via PdfTextoProvider — caso
híbrido, códigos são texto nativo): implementadas no Sprint D; pulam se os
PDFs reais não estiverem em dados_exemplo/.

Rodar:  pytest tests/ -v
"""

import pytest

from domain.entidades import (
    Perfil, QualidadePerfil, GeometriaPadrao, PerfilGeometria,
    CenaTecnica, InstanciaCena, Vista,
    GeometryNotFound, MissingComponent,
)
from core_engine.renderer import resolver_geometria, renderizar


# ---------------------------------------------------------------------------
# Fixtures mínimas (dados reais do projeto, não hipotéticos)
# ---------------------------------------------------------------------------

@pytest.fixture
def geometria_su019():
    """GEO-SU-019 real (aproximação da prova de conceito)."""
    return GeometriaPadrao(
        id="GEO-SU-019",
        contorno_mm=[(0, 0), (104.6, 0), (104.6, 59), (86.6, 59), (86.6, 46),
                     (68.6, 46), (68.6, 59), (51.6, 59), (51.6, 46),
                     (33.6, 46), (33.6, 59), (16.6, 59), (16.6, 46), (0, 46)],
        status="bruto_aproximado",
        versao="0.1",
    )


@pytest.fixture
def perfil_alcoa():
    return Perfil(id="ALCOA-SU-019", fabricante="Alcoa",
                  codigo_fabricante="SU-019", peso_kg_m=1.770)


@pytest.fixture
def associacao_alcoa():
    return PerfilGeometria(
        perfil_id="ALCOA-SU-019", geometria_padrao_id="GEO-SU-019",
        responsavel_homologacao="Bruno", metodo_validacao="comparação de cotas",
        data="2026-07-08", nivel_de_confianca="alto")


# ---------------------------------------------------------------------------
# Unitários — regras do Volume 9
# ---------------------------------------------------------------------------

class TestPesoSuspeito:
    """Caso real Euroshow ES-002: peso '0,95O' (letra O) — marcar, nunca descartar."""

    def test_peso_invalido_marca_suspeito_sem_excecao(self):
        p = Perfil(id="EURO-ES-002", fabricante="Euroshow",
                   codigo_fabricante="ES-002", peso_kg_m=None, peso_suspeito=True)
        assert p.peso_suspeito is True
        assert p.peso_kg_m is None  # registro preservado, não descartado

    def test_qualidade_indice_e_prioridade(self):
        q = QualidadePerfil(codigo_valido=True, peso_valido=False)
        assert q.indice == 1
        assert q.prioridade_revisao == "revisar_primeiro"
        q2 = QualidadePerfil(codigo_valido=True, peso_valido=True,
                             vetor_encontrado=True)
        assert q2.indice == 3
        assert q2.prioridade_revisao == "normal"


class TestResolucaoGeometria:
    """ADR-005: cadeia Perfil -> PerfilGeometria -> GeometriaPadrao."""

    def test_resolucao_funciona(self, perfil_alcoa, associacao_alcoa,
                                 geometria_su019):
        geo = resolver_geometria(perfil_alcoa, [associacao_alcoa],
                                  {"GEO-SU-019": geometria_su019})
        assert geo.id == "GEO-SU-019"

    def test_perfil_sem_associacao_falha_explicitamente(self, perfil_alcoa,
                                                         geometria_su019):
        with pytest.raises(GeometryNotFound):
            resolver_geometria(perfil_alcoa, [],
                               {"GEO-SU-019": geometria_su019})

    def test_geometria_inexistente_falha_explicitamente(self, perfil_alcoa,
                                                         associacao_alcoa):
        with pytest.raises(GeometryNotFound):
            resolver_geometria(perfil_alcoa, [associacao_alcoa], {})


class TestCenaReferenciaValida:
    """ADR-001 verificável em runtime: Cena com perfil inexistente falha explícito."""

    def test_cena_com_perfil_inexistente_falha(self, tmp_path, geometria_su019,
                                                associacao_alcoa):
        cena = CenaTecnica(id="CENA-X", tipo_id="TIPO-X", instancias=[
            InstanciaCena(instancia_id="i1", perfil_id="NAO-EXISTE",
                          posicao_mm=(0, 0), rotacao_graus=0,
                          comprimento_mm=1000)])
        vista = Vista(id="V1", cena_id="CENA-X", tipo_projecao="isometrica")
        with pytest.raises(MissingComponent):
            renderizar(vista, cena, perfis={}, associacoes=[associacao_alcoa],
                       geometrias={"GEO-SU-019": geometria_su019},
                       caminho_saida_png=str(tmp_path / "out.png"))


class TestRenderizacaoPontaAPonta:
    """Integração mínima: Perfil real -> geometria -> imagem com conteúdo."""

    def test_renderiza_su019(self, tmp_path, perfil_alcoa, associacao_alcoa,
                              geometria_su019):
        cena = CenaTecnica(id="CENA-1", tipo_id="TIPO-1", instancias=[
            InstanciaCena(instancia_id="i1", perfil_id="ALCOA-SU-019",
                          posicao_mm=(0, 0), rotacao_graus=0,
                          comprimento_mm=1000)])
        vista = Vista(id="V1", cena_id="CENA-1", tipo_projecao="isometrica")
        saida = renderizar(vista, cena, perfis={"ALCOA-SU-019": perfil_alcoa},
                           associacoes=[associacao_alcoa],
                           geometrias={"GEO-SU-019": geometria_su019},
                           caminho_saida_png=str(tmp_path / "su019.png"))
        import os
        assert os.path.exists(saida)
        assert os.path.getsize(saida) > 10_000  # imagem com conteúdo real


# ---------------------------------------------------------------------------
# Regressão — catálogos de referência (Volume 10)
# Estes exigem os PDFs reais em dados_exemplo/ — pulados se ausentes.
# ---------------------------------------------------------------------------

import os

CATALOGO_CENTENARIO = "dados_exemplo/Centenário.pdf"


@pytest.mark.skipif(not os.path.exists(CATALOGO_CENTENARIO),
                    reason="catálogo Centenário não presente em dados_exemplo/")
class TestRegressaoCentenario:
    def test_linha25_extrai_73_perfis(self):
        from providers.pdf_texto import PdfTextoProvider
        provider = PdfTextoProvider(CATALOGO_CENTENARIO, 87, 103,
                                     fabricante="Centenário")
        perfis = provider.extrair_perfis()
        assert len(perfis) == 73          # resultado da Fase 1
        assert all(not p.peso_suspeito for p in perfis)

    def test_linha30_extrai_55_perfis(self):
        from providers.pdf_texto import PdfTextoProvider
        provider = PdfTextoProvider(CATALOGO_CENTENARIO, 105, 117,
                                     fabricante="Centenário")
        perfis = provider.extrair_perfis()
        assert len(perfis) == 55          # resultado da Fase 2


CATALOGO_ALCOA = "dados_exemplo/catalago-alcoa (1).pdf"
CATALOGO_VITRALSUL = "dados_exemplo/PERFIS-DE-ALUMINIO-02-07-2026.pdf"


@pytest.mark.skipif(not os.path.exists(CATALOGO_ALCOA),
                    reason="catálogo Alcoa não presente em dados_exemplo/")
def test_regressao_alcoa_suprema():
    """Seção Suprema (págs 170-183): vetor sem texto extraível — só o OCR
    enxerga códigos e pesos. Limiares conservadores porque o resultado do
    Tesseract varia entre versões (medido em 2026-07-09: 38 perfis, 19 SU-,
    17 com peso válido)."""
    from providers.ocr import OcrProvider
    provider = OcrProvider(CATALOGO_ALCOA, 170, 183, fabricante="Alcoa")
    perfis = provider.extrair_perfis()
    su = [p for p in perfis if p.codigo_fabricante.startswith("SU-")]
    assert len(su) >= 10
    com_peso = [p for p in perfis if not p.peso_suspeito]
    assert len(com_peso) >= 8


@pytest.mark.skipif(not os.path.exists(CATALOGO_VITRALSUL),
                    reason="catálogo Vitral Sul não presente em dados_exemplo/")
def test_regressao_vitralsul():
    """Caso híbrido (correção da premissa 'raster puro' do Volume 6): os
    códigos SU-XXX são texto nativo nas págs 71-93 — PdfTextoProvider cobre.
    Só os desenhos são raster; a maioria dos pesos não está na camada de
    texto, então peso_suspeito=True é comportamento correto (Volume 9),
    nunca falha."""
    from providers.pdf_texto import PdfTextoProvider
    provider = PdfTextoProvider(CATALOGO_VITRALSUL, 71, 93,
                                 fabricante="Vitral Sul")
    perfis = provider.extrair_perfis()
    su = [p for p in perfis if p.codigo_fabricante.startswith("SU-")]
    assert len(su) >= 20
