"""
EsquadriaCore — testes aditivos do pipeline de aquisição raster (Sprint E.4B)
============================================================================
Cobrem o pipeline oficial (curadoria/aquisicao/*) sem depender dos PDFs reais:

  sintéticos    — retângulo com furo desenhado em memória → topologia/dims/F1
  determinismo  — mesma entrada ⇒ mesmos hashes (máscara e contorno)
  assinatura    — probes detectam selagem de fresta e solidificação
  transacional  — operação que quebra a assinatura é revertida (rollback)
  proteção      — pontos em zona protegida não são alterados pela limpeza
  governança    — cv2 isolado em curadoria/aquisicao; pipeline não escreve em
                  dados/ domain/ contrato/ VERSION/ CHANGELOG
  regressão     — se os artefatos SU-040/041/056 existirem, revalida-os
  recorte       — gate que recusa ROI que corta o perfil (defeito do SU-009)
  gabaritos     — escovinha Suprema × Gold separadas, com alias legado
  correção local— a aba do SU-009 foi restaurada sem tocar no resto

Rodar:  pytest tests/test_aquisicao_contornos.py -v
"""
from pathlib import Path

import json
import cv2                    # sintéticos de motivo; tests/ fica fora do gate
import numpy as np
import pytest
from PIL import Image
from shapely.geometry import Polygon

from curadoria.aquisicao.extrair_contorno_raster import (
    extrair, f1_tolerante_seguro, rasterizar_vetor)
from curadoria.aquisicao import assinatura_topologica, gabaritos, motivos
from curadoria.aquisicao.limpar_contorno_comercial import (
    limpar, op_snap_eixos, op_estender_aba_truncada, _transacao, EstadoLimpeza)

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = json.loads(
    (RAIZ / "curadoria/aquisicao/configs/e4b_suprema.json").read_text())


# ---------------------------------------------------------------------------
# Fixtures sintéticas (desenhadas em memória, sem PDF)
# ---------------------------------------------------------------------------

@pytest.fixture
def card_retangulo_furo():
    """Retângulo preto com furo central branco. Material = 320x220 px
    (cols 40:360, rows 40:260) ⇒ 32.0 x 22.0 mm a 10 px/mm."""
    arr = np.full((300, 400), 255, np.uint8)
    arr[40:260, 40:360] = 0            # material (preto)
    arr[110:190, 150:250] = 255        # furo (branco)
    return Image.fromarray(arr).convert("RGB"), 32.0, 22.0


# ---------------------------------------------------------------------------
# Sintéticos
# ---------------------------------------------------------------------------

def test_extrai_retangulo_com_furo(card_retangulo_furo):
    card, L, A = card_retangulo_furo
    r = extrair("SINT-01", card, L, A, vazios_esperados=1, threshold=128)
    m = r.metricas
    assert m["estado"] == "AQUISICAO_BRUTA_OK"
    assert m["vazios_detectados"] == 1
    assert m["f1_tolerante"]["f1"] >= 0.99
    assert m["erro_relativo_aspecto"] <= 0.0075


def test_topologia_reprova_contagem_errada(card_retangulo_furo):
    card, L, A = card_retangulo_furo
    r = extrair("SINT-02", card, L, A, vazios_esperados=2, threshold=128)
    assert r.metricas["estado"].startswith("BLOQUEADO")
    assert any(f.codigo == "TOPOLOGIA" for f in r.falhas)


def test_contorno_orientacao_e_pontos(card_retangulo_furo):
    card, L, A = card_retangulo_furo
    r = extrair("SINT-03", card, L, A, vazios_esperados=1, threshold=128)
    poly = Polygon([tuple(p) for p in r.contorno_externo],
                   [[tuple(p) for p in v] for v in r.vazios_internos])
    assert poly.is_valid
    assert poly.area > 0


# ---------------------------------------------------------------------------
# Determinismo
# ---------------------------------------------------------------------------

def test_determinismo_hashes(card_retangulo_furo):
    card, L, A = card_retangulo_furo
    a = extrair("DET", card, L, A, 1, threshold=128).metricas
    b = extrair("DET", card, L, A, 1, threshold=128).metricas
    assert a["hash_mascara"] == b["hash_mascara"]
    assert a["hash_contorno"] == b["hash_contorno"]


# ---------------------------------------------------------------------------
# F1 tolerante — caso degenerado protegido
# ---------------------------------------------------------------------------

def test_f1_tolerante_mascara_vazia_nao_quebra():
    vazio = np.zeros((50, 50), np.uint8)
    cheio = np.ones((50, 50), np.uint8)
    assert f1_tolerante_seguro(vazio, vazio, 2.0)["f1"] >= 0.0
    r = f1_tolerante_seguro(vazio, cheio, 2.0)
    assert 0.0 <= r["f1"] <= 1.0


# ---------------------------------------------------------------------------
# Assinatura topológica
# ---------------------------------------------------------------------------

def _perfil_C_aberto():
    """Perfil em C (fresta aberta à direita) 20 x 20 mm, sem vazio fechado."""
    ext = [[0, 0], [20, 0], [20, 6], [6, 6], [6, 14], [20, 14],
           [20, 20], [0, 20]]
    return ext, [], 20.0, 20.0


def test_assinatura_probe_exterior_ok_em_fresta_aberta():
    ext, vazios, L, A = _perfil_C_aberto()
    assin = {"vazios": 0, "probes_material": [[3, 10]],
             "probes_vazio": [], "probes_exterior_conectado": [[13, 10]]}
    assert assinatura_topologica.verificar(ext, vazios, assin, L, A) == []


def test_assinatura_detecta_solidificacao_da_fresta():
    # se a fresta for preenchida (retângulo cheio), o probe exterior vira sólido
    ext = [[0, 0], [20, 0], [20, 20], [0, 20]]
    assin = {"vazios": 0, "probes_material": [[3, 10]],
             "probes_vazio": [], "probes_exterior_conectado": [[13, 10]]}
    viol = assinatura_topologica.verificar(ext, [], assin, 20.0, 20.0)
    assert any("SOLIDIF" in v for v in viol)


def test_assinatura_detecta_vazio_a_mais():
    ext, vazios, L, A = _perfil_C_aberto()
    assin = {"vazios": 1}
    viol = assinatura_topologica.verificar(ext, vazios, assin, L, A)
    assert any("vazios" in v for v in viol)


# ---------------------------------------------------------------------------
# Transacional (rollback)
# ---------------------------------------------------------------------------

def test_transacao_reverte_operacao_que_quebra_assinatura():
    ext, vazios, L, A = _perfil_C_aberto()
    assin = {"vazios": 0, "probes_material": [],
             "probes_vazio": [], "probes_exterior_conectado": [[13, 10]]}
    estado = EstadoLimpeza(ext=[list(p) for p in ext], vazios=[])

    def op_sela_fresta(ext_, vazios_):
        # remove os pontos que formam a fresta ⇒ retângulo cheio (sela)
        novo = [[0, 0], [20, 0], [20, 20], [0, 20]]
        return novo, vazios_, "sela a fresta (deve reverter)"

    estado = _transacao(estado, "sela", op_sela_fresta, assin, L, A)
    assert estado.log[-1].aceita is False          # revertida
    assert len(estado.ext) == len(ext)             # estado inalterado


def test_limpeza_preserva_pontos_em_zona_protegida():
    ext, vazios, L, A = _perfil_C_aberto()
    # zona cobrindo o lábio superior da fresta (y ~ 6)
    zona = [[5.0, 5.0, 21.0, 7.0]]
    assin = {"vazios": 0, "probes_material": [],
             "probes_vazio": [], "probes_exterior_conectado": [[13, 10]]}
    est = limpar(ext, vazios, assin, L, A, zonas_protegidas=zona)
    # todos os pontos originais dentro da zona continuam presentes
    protegidos = [p for p in ext if 5.0 <= p[0] <= 21.0 and 5.0 <= p[1] <= 7.0]
    for p in protegidos:
        assert [float(p[0]), float(p[1])] in [[float(a), float(b)]
                                              for a, b in est.ext]


# ---------------------------------------------------------------------------
# Governança
# ---------------------------------------------------------------------------

def test_cv2_isolado_no_pacote_de_aquisicao():
    """cv2 só pode ser importado dentro de curadoria/aquisicao/."""
    ofensores = []
    for py in RAIZ.rglob("*.py"):
        rel = py.relative_to(RAIZ)
        partes = rel.parts
        if partes and partes[0] in ("curadoria",) and "aquisicao" in partes:
            continue
        if partes and partes[0] in (".venv", "tests"):
            continue
        texto = py.read_text(encoding="utf-8", errors="ignore")
        if "import cv2" in texto or "\ncv2." in texto:
            ofensores.append(str(rel))
    assert ofensores == [], f"cv2 vazou para: {ofensores}"


def test_pipeline_nao_referencia_caminhos_protegidos():
    """Os módulos de aquisição não devem escrever em áreas oficiais."""
    protegidos = ("dados/", "VERSION", "CHANGELOG", "contrato/")
    pacote = RAIZ / "curadoria" / "aquisicao"
    for py in pacote.rglob("*.py"):
        texto = py.read_text(encoding="utf-8", errors="ignore")
        for alvo in protegidos:
            # não pode haver escrita (open(...,"w")/write_text) a esses alvos
            assert f'"{alvo}' not in texto and f"'{alvo}" not in texto, (
                f"{py.name} referencia caminho protegido {alvo}")


def test_extrair_nao_escreve_em_disco(card_retangulo_furo, tmp_path):
    """extrair() é puro: não cria arquivos (só salvar_artefatos escreve)."""
    card, L, A = card_retangulo_furo
    antes = set(RAIZ.rglob("*"))
    extrair("PURO", card, L, A, 1, threshold=128)
    depois = set(RAIZ.rglob("*"))
    assert antes == depois


# ---------------------------------------------------------------------------
# Gate RECORTE — o defeito que encurtou a aba do SU-009
# ---------------------------------------------------------------------------

def test_gate_recorte_reprova_roi_que_corta_o_perfil():
    """Componente colado na borda do recorte ⇒ a ROI cortou o perfil."""
    arr = np.full((300, 400), 255, np.uint8)
    arr[0:260, 40:360] = 0          # encosta no topo (linha 0)
    card = Image.fromarray(arr).convert("RGB")
    r = extrair("CORTADO", card, 32.0, 26.0, 0, threshold=128,
                erro_aspecto_max=9.9, f1_min_bruto=0.0)
    assert r.metricas["estado"] == "BLOQUEADO_RECORTE"
    assert any(f.codigo == "RECORTE" for f in r.falhas)
    assert "topo" in next(f.mensagem for f in r.falhas if f.codigo == "RECORTE")


def test_gate_recorte_aprova_perfil_com_folga(card_retangulo_furo):
    card, L, A = card_retangulo_furo
    r = extrair("FOLGA", card, L, A, 1, threshold=128)
    assert not any(f.codigo == "RECORTE" for f in r.falhas)


# ---------------------------------------------------------------------------
# Motivos são OCORRÊNCIAS locais, não categorias do perfil
#
# Um perfil pode ter vários motivos ao mesmo tempo e várias ocorrências do
# mesmo motivo. A exclusividade existe só entre variantes do MESMO motivo.
# ---------------------------------------------------------------------------

def test_perfil_com_olhal_e_escovinha_e_aceito():
    """SU-053: olhal + escovinha. Um não invalida o outro."""
    cod = "SU-053"
    for gab in ("GAB-OLHAL-01", "GAB-ESCOVINHA-SU-01"):
        assert gabaritos.ocorrencia_compativel(gab, cod), gab
    assert not gabaritos.conflita_com("GAB-OLHAL-01", "GAB-ESCOVINHA-SU-01")


def test_perfil_com_gancho_e_escovinha_e_aceito():
    """LG-004/LG-006: gancho J e escovinha convivem na linha Gold."""
    for gab in ("GAB-TRILHO-J-LG-01", "GAB-ESCOVINHA-LG-01", "GAB-OLHAL-01"):
        assert gabaritos.ocorrencia_compativel(gab, "LG-006"), gab
    assert not gabaritos.conflita_com("GAB-TRILHO-J-LG-01", "GAB-ESCOVINHA-LG-01")


def test_perfil_com_tres_motivos_independentes_e_aceito():
    trio = ("GAB-OLHAL-01", "GAB-ESCOVINHA-SU-01", "GAB-TRILHO-J-SU-01")
    for gab in trio:
        assert gabaritos.ocorrencia_compativel(gab, "SU-024"), gab
    for a in trio:
        for b in trio:
            if a != b:
                assert not gabaritos.conflita_com(a, b), (a, b)


def test_duas_ocorrencias_do_mesmo_motivo_sao_preservadas():
    """Duas escovinhas no mesmo perfil: cada uma com a sua zona."""
    motivos = [
        {"id": "GAB-ESCOVINHA-SU-01", "ocorrencia": 1,
         "zona_protegida": [8.1, 77.0, 14.2, 83.0]},
        {"id": "GAB-ESCOVINHA-SU-01", "ocorrencia": 2,
         "zona_protegida": [8.2, 28.3, 14.2, 34.3]},
        {"id": "GAB-OLHAL-01", "ocorrencia": 1, "zona_protegida": None},
    ]
    assert gabaritos.contagem_por_motivo(motivos)["GAB-ESCOVINHA-SU-01"] == 2
    zonas = gabaritos.zonas_protecao({"motivos": motivos})
    assert len(zonas) == 2, "cada ocorrência precisa da sua própria zona"
    assert zonas[0] != zonas[1]


def test_limpar_uma_ocorrencia_nao_altera_a_outra():
    """Duas câmaras-fechadura idênticas; proteger/limpar uma não mexe na outra."""
    ext = [[0, 0], [24, 0], [24, 30], [0, 30]]
    def canal(cy):
        return [[10.0, cy - 2.0], [14.0, cy - 2.0], [14.0, cy - 1.2],
                [15.0, cy - 0.4], [15.0, cy + 2.0], [9.0, cy + 2.0],
                [9.0, cy - 0.4], [10.0, cy - 1.2]]
    vazios = [canal(8.0), canal(22.0)]
    assin = {"vazios": 2, "probes_material": [[2, 15]],
             "probes_vazio": [[12.0, 8.5], [12.0, 22.5]],
             "probes_exterior_conectado": []}
    zonas = [[8.5, 5.5, 15.5, 10.5], [8.5, 19.5, 15.5, 24.5]]
    est = limpar(ext, vazios, assin, 24.0, 30.0, zonas_protegidas=zonas)
    assert assinatura_topologica.verificar(
        est.ext, est.vazios, assin, 24.0, 30.0) == []
    assert len(est.vazios) == 2, "uma das ocorrências desapareceu"
    for i, v in enumerate(est.vazios):
        assert v == vazios[i], f"ocorrência {i} foi alterada"


def test_politica_suprema_da_escovinha_nao_bloqueia_olhal():
    p = gabaritos.politica_limpeza("GAB-ESCOVINHA-SU-01", CONFIG, "SU-053")
    assert p["familia"] == "Suprema"
    # a escolha da variante da escovinha não diz nada sobre o olhal
    assert gabaritos.ocorrencia_compativel("GAB-OLHAL-01", "SU-053")
    assert not gabaritos.conflita_com("GAB-ESCOVINHA-SU-01", "GAB-OLHAL-01")


def test_politica_gold_da_escovinha_nao_bloqueia_gancho_j():
    p = gabaritos.politica_limpeza("GAB-ESCOVINHA-LG-01", CONFIG, "LG-006")
    assert p["familia"] == "Gold"
    assert gabaritos.ocorrencia_compativel("GAB-TRILHO-J-LG-01", "LG-004")
    assert not gabaritos.conflita_com("GAB-ESCOVINHA-LG-01", "GAB-TRILHO-J-LG-01")


def test_variante_errada_nao_e_aplicada_a_ocorrencia():
    """Exclusividade existe SÓ entre variantes do mesmo motivo base."""
    assert not gabaritos.ocorrencia_compativel("GAB-ESCOVINHA-LG-01", "SU-053")
    assert not gabaritos.ocorrencia_compativel("GAB-ESCOVINHA-SU-01", "LG-006")
    assert gabaritos.conflita_com("GAB-ESCOVINHA-SU-01", "GAB-ESCOVINHA-LG-01")
    assert gabaritos.conflita_com("GAB-TRILHO-J-SU-01", "GAB-TRILHO-J-LG-01")


def test_alias_sem_familia_nao_assume_gold():
    """O alias legado não pode classificar errado um artefato novo."""
    with pytest.raises(gabaritos.GabaritoAmbiguo):
        gabaritos.resolver_gabarito("GAB-ESCOVINHA-01")
    with pytest.raises(gabaritos.GabaritoAmbiguo):
        gabaritos.resolver_gabarito("GAB-ESCOVINHA-01", "XX-999")
    # com família, resolve para a variante daquela ocorrência
    assert gabaritos.resolver_gabarito("GAB-ESCOVINHA-01", "SU-053") == \
        "GAB-ESCOVINHA-SU-01"
    assert gabaritos.resolver_gabarito("GAB-ESCOVINHA-01", "LG-006") == \
        "GAB-ESCOVINHA-LG-01"
    # leitura de artefato antigo continua funcionando, sem inventar família
    assert gabaritos.resolver_gabarito(
        "GAB-ESCOVINHA-01", para_leitura=True) == "GAB-ESCOVINHA-01"


def test_config_lista_todos_os_motivos_de_cada_perfil():
    """Nenhum perfil é representado por um gabarito só quando tem vários."""
    multiplos = {"SU-041", "LG-004", "LG-006"}
    for cod, p in list(CONFIG["perfis"].items()) + [
            (c, v) for c, v in CONFIG["p4_reconhecimento"].items()
            if not c.startswith("_")]:
        motivos = p.get("motivos", [])
        assert motivos, f"{cod} sem lista de ocorrências"
        for m in motivos:
            assert m["id"] in gabaritos.GABARITOS_VALIDOS, (cod, m["id"])
            assert gabaritos.ocorrencia_compativel(m["id"], cod), (cod, m["id"])
            for o in m.get("orientacao", []):
                assert o in gabaritos.ORIENTACOES_VALIDAS, (cod, o)
        if cod in multiplos:
            assert len({m["id"] for m in motivos}) >= 2, \
                f"{cod} tem mais de um motivo confirmado e o config só lista um"


def test_assinatura_valida_cada_zona_protegida():
    """Cada zona de ocorrência guarda uma região real do perfil."""
    for cod, p in list(CONFIG["perfis"].items()) + [
            (c, v) for c, v in CONFIG["p4_reconhecimento"].items()
            if not c.startswith("_")]:
        for m in p.get("motivos", []):
            z = m.get("zona_protegida")
            if z is None:
                continue
            assert len(z) == 4 and z[0] < z[2] and z[1] < z[3], (cod, m["id"], z)


def _perfil_com_escovinha():
    """Canal tipo fechadura: boca estreita (2 mm) e interior largo (4 mm),
    com lábios de retenção — a forma que a limpeza não pode destruir."""
    ext = [[0, 0], [20, 0], [20, 20], [0, 20]]
    canal = [[9.0, 6.0], [11.0, 6.0], [11.0, 7.4], [12.0, 8.0], [12.0, 11.0],
             [8.0, 11.0], [8.0, 8.0], [9.0, 7.4]]
    return ext, [canal], 20.0, 20.0


def test_limpeza_preserva_canal_e_labios_da_escovinha():
    ext, vazios, L, A = _perfil_com_escovinha()
    assin = {"vazios": 1, "probes_material": [[2, 2]],
             "probes_vazio": [[10.0, 9.5]], "probes_exterior_conectado": []}
    zona = [[7.5, 5.5, 12.5, 11.5]]
    est = limpar(ext, vazios, assin, L, A, zonas_protegidas=zona)
    assert assinatura_topologica.verificar(
        est.ext, est.vazios, assin, L, A) == []
    assert len(est.vazios) == 1
    canal_depois = est.vazios[0]
    largura_boca = max(p[0] for p in canal_depois if p[1] <= 7.5) - \
        min(p[0] for p in canal_depois if p[1] <= 7.5)
    largura_interna = max(p[0] for p in canal_depois) - \
        min(p[0] for p in canal_depois)
    assert largura_interna > largura_boca, "o canal virou bloco: lábios sumiram"


def test_serrilha_simplifica_sem_fechar_o_canal():
    """Serrilha gráfica na parede pode ser simplificada; o canal continua
    aberto e com a boca estreita."""
    ext = [[0, 0], [20, 0], [20, 6]]
    # dentes de serra de 0.1 mm na aresta superior (serrilha gráfica)
    for i in range(20):
        ext += [[20 - i * 0.5, 6.1 if i % 2 else 6.0]]
    ext += [[10, 6], [10, 20], [0, 20]]
    canal = [[3.0, 2.0], [5.0, 2.0], [5.0, 2.6], [6.0, 3.2], [6.0, 4.6],
             [2.0, 4.6], [2.0, 3.2], [3.0, 2.6]]
    assin = {"vazios": 1, "probes_material": [[1, 10]],
             "probes_vazio": [[4.0, 3.8]], "probes_exterior_conectado": []}
    zona = [[1.5, 1.5, 6.5, 5.0]]
    est = limpar(ext, [canal], assin, 20.0, 20.0, zonas_protegidas=zona)
    assert assinatura_topologica.verificar(
        est.ext, est.vazios, assin, 20.0, 20.0) == []
    assert len(est.ext) < len(ext), "a serrilha não foi simplificada"
    assert len(est.vazios) == 1, "o canal fechou"


# ---------------------------------------------------------------------------
# Correção local da aba do SU-009
# ---------------------------------------------------------------------------

def test_estender_aba_recusa_juntas_incompativeis():
    """A operação não 'conserta' um perfil que de fato divergiu: as juntas
    do splice têm de coincidir com a fonte."""
    alvo = [[0, 0], [10, 0], [10, 5], [0, 5]]
    fonte = [[50, 0], [60, 0], [60, 6], [50, 6]]   # mesmo formato, outro lugar
    est = EstadoLimpeza(ext=[list(p) for p in alvo], vazios=[])
    est = _transacao(est, "estender", op_estender_aba_truncada(fonte, 4.5),
                     {"vazios": 0}, 10.0, 5.0)
    assert est.ext == alvo, "não podia ter alterado o contorno"
    assert "juntas não coincidem" in est.log[-1].detalhe


def test_estender_aba_sem_trecho_truncado_e_no_op():
    """Sem run identificável acima do corte, não faz nada (não inventa)."""
    alvo = [[0, 0], [10, 0], [10, 5], [0, 5]]
    est = EstadoLimpeza(ext=[list(p) for p in alvo], vazios=[])
    est = _transacao(est, "estender",
                     op_estender_aba_truncada([[50, 50], [60, 58]], 4.5),
                     {"vazios": 0}, 10.0, 5.0)
    assert est.ext == alvo
    assert "não identificado" in est.log[-1].detalhe


def test_su009_correcao_local_preservou_olhais_e_topologia():
    """A aba foi restaurada; olhais, câmara e demais pontos ficaram intactos."""
    p = RAIZ / "curadoria/contornos/SU-009"
    met = p / "SU-009_metricas_corrigidas.json"
    if not met.exists():
        pytest.skip("correção do SU-009 ausente")
    d = json.loads(met.read_text())
    loc = d["localidade"]
    assert loc["vazios_identicos"] is True
    assert loc["iou_abaixo_do_corte"] >= 0.999, "mexeu abaixo do corte"
    assert all(pt[1] >= 42.0 for pt in loc["pontos_removidos"]), \
        "removeu ponto fora da aba"
    assert all(pt[1] >= 42.0 for pt in loc["pontos_novos"]), \
        "acrescentou ponto fora da aba"
    assert d["topologia"]["violacoes_assinatura"] == []
    assert d["depois"]["f1_vs_fonte"] > d["antes"]["f1_vs_fonte"]
    assert d["determinismo"]["hash_repetido"] is True


def test_su009_artefato_reflete_altura_corrigida():
    art = RAIZ / "curadoria/contornos/SU-009/30_contorno_recon.json"
    if not art.exists():
        pytest.skip("artefato SU-009 ausente")
    d = json.loads(art.read_text())
    assert abs(d["dimensoes_mm"]["altura"] - 49.27) < 0.05
    poly = Polygon([tuple(q) for q in d["contorno_externo"]],
                   [[tuple(q) for q in v] for v in d["vazios_internos"]])
    assert poly.is_valid


# ---------------------------------------------------------------------------
# Regressão dos pilotos (se os artefatos existirem)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("codigo", ["SU-040", "SU-041", "SU-056"])
def test_regressao_piloto_valido(codigo):
    art = RAIZ / "curadoria" / "contornos" / codigo / "30_contorno_comercial.json"
    if not art.exists():
        pytest.skip(f"artefato {codigo} ausente")
    d = json.loads(art.read_text())
    L = d["dimensoes_mm"]["largura"]; A = d["dimensoes_mm"]["altura"]
    ext, vazios = d["contorno_externo"], d["vazios_internos"]
    poly = Polygon([tuple(p) for p in ext],
                   [[tuple(p) for p in v] for v in vazios])
    assert poly.is_valid and poly.geom_type == "Polygon"
    # assinatura homologada preservada
    viol = assinatura_topologica.verificar(
        ext, vazios, d["assinatura_topologica"], L, A)
    assert viol == [], f"{codigo}: {viol}"
    # dimensões dentro de 0.10 mm
    xs = [p[0] for p in ext]; ys = [p[1] for p in ext]
    assert abs((max(xs) - min(xs)) - L) <= 0.10
    assert abs((max(ys) - min(ys)) - A) <= 0.10


# ---------------------------------------------------------------------------
# OLHAL ≠ CANAL DE ESCOVINHA
#
# Correção crítica do Bruno (25/07/2026): um detector genérico de "bolso"
# localizou OLHAIS e os rotulou escovinha. Na seção, olhal é câmara
# arredondada (aloja parafuso); escovinha é bolso longitudinal atrás de boca
# estreita, com lábios de retenção.
# ---------------------------------------------------------------------------

def _banda(px_mm=24.0, lado_mm=12.0, topo_mm=2.0, base_mm=9.0):
    """Banda horizontal de material com espaço livre acima e abaixo."""
    lado = int(lado_mm * px_mm)
    solid = np.zeros((lado, lado), np.uint8)
    solid[int(topo_mm * px_mm):int(base_mm * px_mm), :] = 1
    return solid, lado, int(base_mm * px_mm)


def _bolso_olhal(px_mm=24.0, d_mm=3.6, boca_mm=1.6):
    """Câmara circular com fenda até a face — alojamento de parafuso."""
    solid, lado, y_base = _banda(px_mm)
    cx = lado // 2
    cy = int(5.0 * px_mm)
    cv2.circle(solid, (cx, cy), int(d_mm / 2 * px_mm), 0, -1)
    meia = max(1, int(boca_mm / 2 * px_mm))
    solid[cy:y_base, cx - meia:cx + meia] = 0          # fenda do "C"
    return solid, px_mm


def _bolso_escovinha(px_mm=24.0, larg_mm=4.4, prof_mm=2.0, boca_mm=1.6):
    """Bolso longitudinal (retangular em seção) atrás de boca estreita, com
    lábios de retenção — o degrau boca→bolso é o que segura a escova."""
    solid, lado, y_base = _banda(px_mm)
    cx = lado // 2
    cy = int(5.0 * px_mm)
    hw = int(larg_mm / 2 * px_mm)
    hp = int(prof_mm / 2 * px_mm)
    solid[cy - hp:cy + hp, cx - hw:cx + hw] = 0        # bolso retangular
    meia = max(1, int(boca_mm / 2 * px_mm))
    solid[cy + hp:y_base, cx - meia:cx + meia] = 0     # boca estreita
    return solid, px_mm


def test_olhal_nao_e_classificado_como_escovinha():
    solid, px = _bolso_olhal()
    cands = motivos.candidatos_de_motivo(solid, px, 12.0, 12.0)
    assert cands, "nenhum bolso detectado no sintético do olhal"
    principal = max(cands, key=lambda c: c["area_mm2"])
    assert principal["classe_candidata"] != "escovinha", principal["justificativa"]
    assert principal["forma"]["circularidade"] > 0.55


def test_escovinha_nao_e_classificada_como_olhal():
    solid, px = _bolso_escovinha()
    cands = motivos.candidatos_de_motivo(solid, px, 12.0, 12.0)
    assert cands, "nenhum bolso detectado no sintético da escovinha"
    principal = max(cands, key=lambda c: c["area_mm2"])
    assert principal["classe_candidata"] != "olhal", principal["justificativa"]
    assert principal["forma"]["retangularidade"] > principal["forma"]["circularidade"]


def test_bolso_circular_isolado_nao_confirma_escovinha():
    """Circularidade/área/orientação sozinhas não podem confirmar escovinha."""
    solid, px = _bolso_olhal(d_mm=5.0, boca_mm=2.0)
    for c in motivos.candidatos_de_motivo(solid, px, 12.0, 12.0):
        if c["forma"]["circularidade"] >= 0.62 and c["forma"]["alongamento"] <= 1.6:
            assert c["classe_candidata"] == "olhal", c["justificativa"]


def test_canal_sem_labios_nao_confirma_escovinha():
    """Sem o degrau boca→bolso não há retenção: não pode virar escovinha."""
    px = 24.0
    lado = int(12 * px)
    solid = np.ones((lado, lado), np.uint8)
    cx = lado // 2
    larg = int(2.0 * px)
    solid[lado // 2:, cx - larg // 2:cx + larg // 2] = 0   # canal reto, sem lábios
    for c in motivos.candidatos_de_motivo(solid, px, 12.0, 12.0):
        assert c["classe_candidata"] != "escovinha", c["justificativa"]


def test_perfil_aceita_olhal_e_escovinha_simultaneamente():
    for gab in ("GAB-OLHAL-01", "GAB-ESCOVINHA-SU-01"):
        assert gabaritos.ocorrencia_compativel(gab, "SU-053")
    assert not gabaritos.conflita_com("GAB-OLHAL-01", "GAB-ESCOVINHA-SU-01")


def test_cada_ocorrencia_usa_roi_propria():
    motivos_cfg = [
        {"id": "GAB-OLHAL-01", "ocorrencia": 1, "zona_protegida": [1.0, 1.0, 5.0, 5.0]},
        {"id": "GAB-ESCOVINHA-SU-01", "ocorrencia": 1,
         "zona_protegida": [10.0, 1.0, 14.0, 5.0]},
    ]
    zonas = gabaritos.zonas_protecao({"motivos": motivos_cfg})
    assert len(zonas) == 2 and zonas[0] != zonas[1]


def test_duas_ocorrencias_nao_compartilham_a_mesma_roi():
    for grupo in ("perfis", "p4_reconhecimento"):
        for cod, perfil in CONFIG[grupo].items():
            if cod.startswith("_"):
                continue
            zonas = [tuple(m["zona_protegida"]) for m in perfil.get("motivos", [])
                     if m.get("zona_protegida")]
            assert len(zonas) == len(set(zonas)), f"{cod}: ROIs repetidas"


def test_motivo_pendente_nao_entra_como_confirmado():
    """Enquanto a atribuição automática estiver desativada, nenhuma escovinha
    pode ter geometria atribuída."""
    assert CONFIG["gabaritos"]["_atribuicao_automatica_escovinha"]["habilitada"] is False
    for grupo in ("perfis", "p4_reconhecimento"):
        for cod, perfil in CONFIG[grupo].items():
            if cod.startswith("_"):
                continue
            for m in perfil.get("motivos", []):
                if m["id"].startswith("GAB-ESCOVINHA"):
                    assert m["zona_protegida"] is None, (cod, m["id"])
                    assert m["atribuicao_geometrica"] == "pendente_arbitragem"


def test_metricas_de_olhal_nao_alimentam_politica_de_escovinha():
    """O que importa é o invariante: nenhuma medição de escovinha é utilizável
    enquanto não for refeita sobre o ground truth arbitrado pelo Bruno."""
    NAO_UTILIZAVEIS = {"INVALIDADAS", "A_REFAZER_SOBRE_GROUND_TRUTH"}
    for gid in ("GAB-ESCOVINHA-SU-01", "GAB-ESCOVINHA-LG-01"):
        g = CONFIG["gabaritos"][gid]
        assert g["medicoes"]["estado"] in NAO_UTILIZAVEIS
        assert g["medicoes"]["geometria_confirmada"] is None
        assert g["comparacao_suprema_x_gold"]["estado"] == "SUSPENSA"
        assert "orientacoes_observadas" not in g, \
            "orientação medida sobre olhal não pode reaparecer como prova"


def test_su009_permanece_intacto():
    """A aba do SU-009 foi aprovada: os artefatos não podem mudar."""
    esperado = {
        "20_contorno_bruto.json":
            "69cadfe9f74d370044199bf4f621f617e28fce9781ac1fe8f958866ea4d57654",
        "30_contorno_recon.json":
            "32e84cd725aef673502d40ceef637d82509b65cb0803559b40d9c37fff3f036f",
        "SU-009_metricas_corrigidas.json":
            "90af9803aa87052bc0141427db37efd93282106da98f8a2e5a2c49afd5260725",
        "SU-009_operacoes_limpeza_corrigidas.json":
            "e796811c8ea9ccf52ba812f8f93b22564b6573f2ba7da6428a23c6f08bbc5fc8",
    }
    import hashlib
    pasta = RAIZ / "curadoria/contornos/SU-009"
    if not pasta.exists():
        pytest.skip("artefatos do SU-009 ausentes")
    for nome, sha in esperado.items():
        alvo = pasta / nome
        assert alvo.exists(), nome
        atual = hashlib.sha256(alvo.read_bytes()).hexdigest()
        assert atual == sha, f"{nome} mudou: {atual[:16]} ≠ {sha[:16]}"


# ---------------------------------------------------------------------------
# ARBITRAGEM OFICIAL DO BRUNO (25/07/2026)
#
# Classificação humana sobre o painel numerado. Prevalece sobre qualquer
# inferência automática. Motivos são locais e coexistem: olhal + escovinha +
# os DOIS lados do encaixe do baguete, que trabalham em paralelo.
# ---------------------------------------------------------------------------

ARB = CONFIG["arbitragem_bruno"]["perfis"]
BAG_INT = gabaritos.ENCAIXE_BAGUETE_INTERNO
BAG_EXT = gabaritos.ENCAIXE_BAGUETE_EXTERNO


def _confirmadas(cod):
    return [o for o in ARB[cod]["ocorrencias"] if o["estado"] == "confirmado_bruno"]


def test_su053_tem_duas_escovinhas_e_um_olhal():
    c = ARB["SU-053"]["contagem"]
    assert c["GAB-ESCOVINHA-SU-01"] == 2
    assert c["GAB-OLHAL-01"] == 1
    nums = {o["candidato"]: o["id"] for o in _confirmadas("SU-053")}
    assert nums[1] == "GAB-ESCOVINHA-SU-01" and nums[5] == "GAB-ESCOVINHA-SU-01"
    assert nums[3] == "GAB-OLHAL-01"


def test_su053_tem_encaixe_interno_e_externo_do_baguete():
    nums = {o["candidato"]: o["id"] for o in _confirmadas("SU-053")}
    assert nums[2] == BAG_INT
    assert nums[4] == BAG_EXT
    c = ARB["SU-053"]["contagem"]
    assert c[BAG_INT] == 1 and c[BAG_EXT] == 1


def test_su225_interface_nao_finge_delimitacao_concluida():
    """#3 marca a REGIÃO de interface: a linha fina é do SU-102, e a superfície
    correspondente do SU-225 ainda não foi delimitada."""
    tres = next(o for o in ARB["SU-225"]["ocorrencias"] if o["candidato"] == 3)
    assert tres["id"] == gabaritos.INTERFACE_BAGUETE_REPRESENTADA
    assert gabaritos.eh_marcacao_de_evidencia(tres["id"])
    assert tres["roi_geometria_perfil_base"] == "pendente_de_delimitacao"
    assert tres["zona"] is None, "interface não pode fingir ROI geométrica"
    assert tres["baguete_referencia"] == "SU-102"
    # a marcação de evidência não conta como motivo do perfil-base
    assert tres["id"] not in ARB["SU-225"]["contagem"]


def test_roi_de_motivo_nao_fica_dentro_do_contorno_de_referencia():
    """Nenhum motivo do SU-225 pode ter ROI herdada da região do baguete
    desenhado — ou a ROI é do perfil-base, ou fica pendente."""
    for o in ARB["SU-225"]["ocorrencias"]:
        if o["id"] and not gabaritos.eh_marcacao_de_evidencia(o["id"]):
            if o["estado"] == "confirmado_bruno":
                assert o.get("zona") is not None, o["id"]
            else:
                assert o.get("zona") is None, \
                    f"{o['id']} não confirmado não pode ter ROI"


def test_linha_fina_de_outro_perfil_nao_vira_motivo():
    """O contorno de referência é evidência, nunca motivo do perfil-base."""
    for marc in (gabaritos.INTERFACE_BAGUETE_REPRESENTADA,
                 gabaritos.CONTORNO_DE_REFERENCIA):
        assert gabaritos.eh_marcacao_de_evidencia(marc)
        assert marc not in gabaritos.GABARITOS_VALIDOS
    for cod in ("SU-053", "SU-225", "LG-006"):
        for gid in ARB[cod]["contagem"]:
            assert not gabaritos.eh_marcacao_de_evidencia(gid), (cod, gid)


def test_encaixe_interno_e_externo_do_su225_seguem_distintos():
    ids = [o["id"] for o in ARB["SU-225"]["ocorrencias"] if o["id"]]
    assert BAG_INT in ids and BAG_EXT in ids
    assert not gabaritos.conflita_com(BAG_INT, BAG_EXT)
    assert ARB["SU-225"]["contagem"][BAG_INT] == 1
    assert ARB["SU-225"]["contagem"][BAG_EXT] == 1


def test_nao_evidenciado_nao_vira_confirmado_por_proximidade():
    """Presença esperada não autoriza promover por vizinhança."""
    for o in ARB["SU-225"]["ocorrencias"]:
        if o["id"] in (BAG_INT, BAG_EXT):
            assert o["estado"] == "nao_evidenciado"
            assert o["zona"] is None
            assert o.get("roi_geometria_perfil_base") == "pendente_de_delimitacao" \
                or "não evidenciado" in o.get("_nota", "").lower() \
                or "nao evidenciado" in o.get("_nota", "").lower()
    sep = ARB["SU-225"]["_separacao_de_contornos"]
    assert sep["linha_fina_mm"] < sep["mediana_perfil_mm"] / 5


def test_su225_tem_dois_olhais_e_duas_escovinhas():
    c = ARB["SU-225"]["contagem"]
    assert c["GAB-OLHAL-01"] == 2
    assert c["GAB-ESCOVINHA-SU-01"] == 2
    nums = {o["candidato"]: o["id"] for o in _confirmadas("SU-225")}
    assert nums[1] == nums[2] == "GAB-OLHAL-01"
    assert nums[4] == nums[5] == "GAB-ESCOVINHA-SU-01"


def test_su225_nao_conclui_ausencia_do_encaixe_externo():
    """Não evidenciado ≠ ausente."""
    ext = [o for o in ARB["SU-225"]["ocorrencias"] if o["id"] == BAG_EXT]
    assert ext, "o encaixe externo sumiu do registro do SU-225"
    assert ext[0]["estado"] in ("nao_focado", "nao_evidenciado")
    assert ARB["SU-225"]["contagem"][BAG_EXT] == 1


def test_su225_ponta_do_baguete_nao_vira_encaixe_externo():
    """#8 é a ponta do SU-102 DESENHADO no card, não um encaixe do SU-225."""
    oito = next(o for o in ARB["SU-225"]["ocorrencias"] if o["candidato"] == 8)
    assert oito["id"] is None, "#8 foi promovido indevidamente"
    assert oito["estado"] == "sem_motivo"
    assert oito.get("_classe") == "representacao_de_outro_perfil"
    assert "SU-102" in oito["_nota"]


def test_su225_partes_internas_nao_viram_motivo():
    """#6 e #7 são só parte interna do perfil; #11 é a parte externa do olhal."""
    for num in (6, 7, 11):
        o = next(x for x in ARB["SU-225"]["ocorrencias"] if x["candidato"] == num)
        assert o["id"] is None and o["estado"] == "sem_motivo", num


def test_regra_de_representacao_de_outro_perfil_registrada():
    """Card com baguete desenhado junto: não promover automaticamente."""
    r = CONFIG["arbitragem_bruno"]["_complemento"]
    assert "não promover" in r["regra_representacao"].lower() or \
           "nao promover" in r["regra_representacao"].lower()
    ev = r["evidencia_tambore"]
    assert ev["perfil"] == "TMS-102" and ev["pagina_pdf"] == 108
    assert "espelhado" in ev["leitura"].lower()


def test_lg006_tem_um_olhal_e_duas_escovinhas():
    c = ARB["LG-006"]["contagem"]
    assert c["GAB-OLHAL-01"] == 1
    assert c["GAB-ESCOVINHA-LG-01"] == 2
    nums = {o["candidato"]: o["id"] for o in _confirmadas("LG-006")}
    assert nums[1] == "GAB-OLHAL-01"
    assert nums[2] == nums[3] == "GAB-ESCOVINHA-LG-01"


def test_lg006_candidato_4_nao_vira_motivo():
    """#4 é o ângulo de 90° do apoio do vidro — região examinada e descartada."""
    quatro = next(o for o in ARB["LG-006"]["ocorrencias"] if o["candidato"] == 4)
    assert quatro["id"] is None
    assert quatro["estado"] == "sem_motivo"
    assert BAG_EXT not in str(quatro.get("_nota", ""))
    for gid in ARB["LG-006"]["contagem"]:
        assert gid is not None


def test_lg006_encaixe_externo_promovido_no_candidato_6():
    """Arbitragem complementar: LG-006 #6 É o encaixe externo do baguete."""
    seis = next(o for o in ARB["LG-006"]["ocorrencias"] if o["candidato"] == 6)
    assert seis["id"] == BAG_EXT
    assert seis["estado"] == "confirmado_bruno"
    assert seis["zona"] is not None, "o externo precisa da sua própria ROI"
    interno = next(o for o in ARB["LG-006"]["ocorrencias"] if o["id"] == BAG_INT)
    assert tuple(interno["zona"]) != tuple(seis["zona"])
    assert ARB["LG-006"]["contagem"][BAG_EXT] == 1


def test_encaixe_interno_e_externo_sao_ocorrencias_distintas():
    assert BAG_INT != BAG_EXT
    assert gabaritos.MOTIVO_BASE[BAG_INT] != gabaritos.MOTIVO_BASE[BAG_EXT]
    assert not gabaritos.conflita_com(BAG_INT, BAG_EXT)
    for cod in ("SU-053", "SU-225", "LG-006"):
        zonas = [tuple(o["zona"]) for o in ARB[cod]["ocorrencias"]
                 if o["id"] in (BAG_INT, BAG_EXT) and o.get("zona")]
        assert len(zonas) == len(set(zonas)), f"{cod}: interno e externo com ROI igual"


def test_perfil_aceita_todos_esses_motivos_simultaneamente():
    for cod in ("SU-053", "SU-225", "LG-006"):
        # Todos os motivos REGISTRADOS, não só os já delimitados: a coexistência
        # independe de a geometria estar delimitada. Marcações de evidência
        # (interface, contorno de referência) ficam fora.
        ids = {o["id"] for o in ARB[cod]["ocorrencias"]
               if o["id"] and not gabaritos.eh_marcacao_de_evidencia(o["id"])}
        assert len(ids) >= 3, f"{cod} deveria ter 3+ motivos distintos: {ids}"
        for gid in ids:
            assert gid in gabaritos.GABARITOS_VALIDOS, gid
            assert gabaritos.ocorrencia_compativel(gid, cod), (cod, gid)
            for outro in ids:
                if outro != gid:
                    assert not gabaritos.conflita_com(gid, outro), (gid, outro)


def test_classificacao_do_bruno_prevalece_sobre_inferencia_automatica():
    """O detector chamou SU-053 #1 de 'indeterminado'; o Bruno disse escovinha."""
    assert gabaritos.classificacao_humana_prevalece("indeterminado",
                                                    "GAB-ESCOVINHA-SU-01") == \
        "GAB-ESCOVINHA-SU-01"
    assert gabaritos.classificacao_humana_prevalece("olhal", None) == "olhal"
    for cod in ("SU-053", "SU-225", "LG-006"):
        for o in _confirmadas(cod):
            assert o["origem"].startswith("confirmado pelo Bruno")
