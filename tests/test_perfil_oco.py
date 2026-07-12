"""
EsquadriaCore — testes do modelo de perfil oco (ADR-008)
=========================================================
Cobre validações do formato contorno_externo + vazios_internos, a
compatibilidade com o formato legado e a regressão de DADOS do GEO-SU-005
(iteração 11) — nunca comparação de imagem pixel a pixel.

Rodar:  pytest tests/ -v
"""

import json
import os

import pytest

from domain.entidades import (
    GeometriaPadrao, ContornoInvalido, validar_contornos, _area_poligono,
    _ponto_no_poligono,
)
from core_engine.renderer import extrudar_com_furos


QUADRADO = [(0, 0), (10, 0), (10, 10), (0, 10)]
FURO_CENTRAL = [(3, 3), (7, 3), (7, 7), (3, 7)]


def geo(**kwargs):
    base = dict(id="GEO-TESTE", contorno_mm=[], status="bruto_aproximado",
                versao="1.0")
    base.update(kwargs)
    return GeometriaPadrao(**base)


# ---------------------------------------------------------------------------
# Validações do ADR-008 (adendo ao Volume 9)
# ---------------------------------------------------------------------------

class TestValidacoesContorno:
    def test_contorno_externo_com_vazios_valido(self):
        validar_contornos(geo(contorno_externo=QUADRADO,
                              vazios_internos=[FURO_CENTRAL]))

    def test_vazios_internos_vazio_e_valido(self):
        validar_contornos(geo(contorno_externo=QUADRADO, vazios_internos=[]))

    def test_legado_apenas_contorno_mm_continua_valido(self):
        validar_contornos(geo(contorno_mm=QUADRADO))

    def test_sem_nenhum_formato_falha_explicitamente(self):
        with pytest.raises(ContornoInvalido):
            validar_contornos(geo())

    def test_vazio_fora_do_contorno_falha(self):
        with pytest.raises(ContornoInvalido):
            validar_contornos(geo(contorno_externo=QUADRADO,
                                  vazios_internos=[[(12, 12), (15, 12),
                                                    (15, 15), (12, 15)]]))

    def test_vazios_que_se_cruzam_falham(self):
        with pytest.raises(ContornoInvalido):
            validar_contornos(geo(
                contorno_externo=QUADRADO,
                vazios_internos=[FURO_CENTRAL,
                                 [(5, 5), (9, 5), (9, 9), (5, 9)]]))

    def test_contorno_autointersectante_falha(self):
        borboleta = [(0, 0), (10, 10), (10, 0), (0, 10)]
        with pytest.raises(ContornoInvalido):
            validar_contornos(geo(contorno_externo=borboleta))

    def test_menos_de_tres_pontos_falha(self):
        with pytest.raises(ContornoInvalido):
            validar_contornos(geo(contorno_externo=[(0, 0), (10, 10)]))


# ---------------------------------------------------------------------------
# Renderer preserva vazios (adendo ao Volume 7)
# ---------------------------------------------------------------------------

class TestExtrusaoComFuros:
    def test_tampas_respeitam_o_furo(self):
        faces = extrudar_com_furos(QUADRADO, [FURO_CENTRAL],
                                   comprimento_mm=100,
                                   rotacao_graus=0, posicao_mm=(0, 0))
        # células de tampa: faces com coordenada de extrusão (x) constante;
        # na convenção rotacao=0, a seção mapeia (a, b) -> (z, y)
        celulas_dentro_do_furo = 0
        for f in faces:
            xs = {round(v[0], 6) for v in f}
            if len(xs) == 1 and len(f) == 4:   # tampa
                cy = sum(v[1] for v in f) / 4
                cz = sum(v[2] for v in f) / 4
                if _ponto_no_poligono((cz, cy), FURO_CENTRAL):
                    celulas_dentro_do_furo += 1
        assert celulas_dentro_do_furo == 0

    def test_paredes_do_furo_sao_geradas(self):
        com_furo = extrudar_com_furos(QUADRADO, [FURO_CENTRAL], 100, 0, (0, 0))
        sem_furo = extrudar_com_furos(QUADRADO, [], 100, 0, (0, 0))
        # o furo adiciona 4 paredes internas (uma por aresta do furo)
        paredes_com = [f for f in com_furo if len({round(v[0], 6) for v in f}) > 1]
        paredes_sem = [f for f in sem_furo if len({round(v[0], 6) for v in f}) > 1]
        assert len(paredes_com) == len(paredes_sem) + len(FURO_CENTRAL)


# ---------------------------------------------------------------------------
# Regressão de DADOS — GEO-SU-005 iteração 11 (aprovada pelo Bruno em 2026-07-12)
# ---------------------------------------------------------------------------

BIBLIOTECA = "dados/geometrias.json"


@pytest.mark.skipif(not os.path.exists(BIBLIOTECA),
                    reason="biblioteca de geometrias não presente")
class TestRegressaoGeoSu005:
    @pytest.fixture
    def su005(self):
        with open(BIBLIOTECA) as f:
            dados = json.load(f)
        g = next(g for g in dados["geometrias"] if g["id"] == "GEO-SU-005")
        return g

    def test_formato_novo_gravado(self, su005):
        assert su005["nivel_contorno"] == "2_renderizavel_comercial"
        assert su005["status_contorno"] == "validado_visualmente"
        assert su005["metodo_contorno"] == "contorno_externo_vazios_internos"
        assert os.path.exists(su005["evidencia_contorno"])

    def test_estrutura_do_contorno(self, su005):
        externo = [tuple(p) for p in su005["contorno_externo"]]
        vazios = [[tuple(p) for p in v] for v in su005["vazios_internos"]]
        assert len(vazios) == 1              # câmara superior (bandeira)
        assert len(externo) >= 80            # seção rica (ganchos, raios)
        assert len(vazios[0]) >= 4

    def test_cotas_e_areas(self, su005):
        externo = [tuple(p) for p in su005["contorno_externo"]]
        vazios = [[tuple(p) for p in v] for v in su005["vazios_internos"]]
        xs = [p[0] for p in externo]
        ys = [p[1] for p in externo]
        assert max(xs) - min(xs) == pytest.approx(69.6, abs=0.2)   # largura
        assert max(ys) - min(ys) == pytest.approx(46.0, abs=0.2)   # altura
        area_material = _area_poligono(externo) - sum(
            _area_poligono(v) for v in vazios)
        assert 400 < area_material < 480     # medido: ~438 mm²

    def test_contorno_passa_nas_validacoes_de_dominio(self, su005):
        validar_contornos(geo(
            id="GEO-SU-005",
            contorno_externo=[tuple(p) for p in su005["contorno_externo"]],
            vazios_internos=[[tuple(p) for p in v]
                             for v in su005["vazios_internos"]]))
