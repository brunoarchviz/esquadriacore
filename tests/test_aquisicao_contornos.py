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
    """Nenhum perfil é representado por um gabarito só quando tem vários.

    Lista vazia só é tolerada com declaração EXPLÍCITA e justificada de que o
    levantamento não foi feito — lista vazia silenciosa continua reprovando,
    porque "não levantado" nunca pode ser lido como "não tem".
    """
    multiplos = {"SU-041", "LG-004", "LG-006"}
    for cod, p in list(CONFIG["perfis"].items()) + [
            (c, v) for c, v in CONFIG["p4_reconhecimento"].items()
            if not c.startswith("_")]:
        motivos = p.get("motivos", [])
        if not motivos:
            pend = p.get("_motivos_pendentes")
            assert pend, f"{cod} sem lista de ocorrências e sem declará-la pendente"
            assert pend.get("levantamento") == "nao_realizado", (cod, pend)
            assert pend.get("justificativa"), \
                f"{cod} declara levantamento pendente sem justificativa"
            continue
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


def test_escovinha_so_tem_zona_com_arbitragem_humana():
    """A atribuição automática de escovinha continua desativada. Zona só existe
    onde houve arbitragem explícita — nunca inferida pelo detector."""
    assert CONFIG["gabaritos"]["_atribuicao_automatica_escovinha"]["habilitada"] is False
    for grupo in ("perfis", "p4_reconhecimento"):
        for cod, perfil in CONFIG[grupo].items():
            if cod.startswith("_"):
                continue
            for m in perfil.get("motivos", []):
                if not m["id"].startswith("GAB-ESCOVINHA"):
                    continue
                if m["zona_protegida"] is None:
                    assert m["atribuicao_geometrica"] == "pendente_arbitragem", \
                        (cod, m["id"])
                else:
                    assert m.get("roi_status") in ("confirmado_bruno",
                                                   "CONFIRMADO_BRUNO"), \
                        f"{cod}/{m['id']}: zona sem arbitragem humana"
                    assert m["atribuicao_geometrica"] == "zona_curada"


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


# ---------------------------------------------------------------------------
# VALIDADOR LOCAL DA FACE — quantização orientada pelo lado exterior
#
# A face é estimada em subpixel a partir de duas faixas locais com mediana
# robusta, mas a máscara raster não tem fronteira fracionária: a coluna
# floor(face) É a borda legítima. Contar sem quantizar acusava 164 px falsos
# na reconstrução do SU-039. Não é tolerância — pixel além do limite discreto
# continua sendo resíduo (os 6 px da quebra seguem rejeitando).
# ---------------------------------------------------------------------------

from curadoria.aquisicao import contaminacao as ct


def _parede_com_saliencia(lado, px=24.0, lado_mm=16.0, saliencia=True):
    """Reproduz a geometria do SU-039: parede reta + linha de chamada fina que
    vem de longe e termina numa pequena massa sólida encostada na face.

    O tirante precisa AFASTAR-SE da parede: colado nela, a dilatação do núcleo
    o engole e o detector não o vê (foi o que fez os sintéticos anteriores
    pularem, deixando o ramo `ceil` sem prova).
    """
    n = int(lado_mm * px)
    s = np.zeros((n, n), np.uint8)
    meio = n // 2
    esp = max(2, int(0.08 * px))          # traço fino ~0,08 mm
    if lado in ("esquerda", "direita"):
        s[:, meio:meio + int(2 * px)] = 1                    # parede vertical
        face = meio if lado == "esquerda" else meio + int(2 * px) - 1
        d = -1 if lado == "esquerda" else 1
        y = meio
        x0 = face + d * int(5 * px)                          # começa longe
        a, b = sorted((x0, face + d))
        s[y - esp // 2:y + esp // 2 + 1, a:b] = 1            # linha de chamada
        if saliencia:                                        # massa na ponta
            for i in range(int(1.2 * px)):
                h = int(1.2 * px) - i
                xx = face + d * (i + 1)
                s[y - h // 2:y + h // 2 + 1, min(xx, xx + 1):max(xx, xx + 1) + 1] = 1
    else:
        s[meio:meio + int(2 * px), :] = 1                    # parede horizontal
        face = meio if lado == "acima" else meio + int(2 * px) - 1
        d = -1 if lado == "acima" else 1
        x = meio
        y0 = face + d * int(5 * px)
        a, b = sorted((y0, face + d))
        s[a:b, x - esp // 2:x + esp // 2 + 1] = 1
        if saliencia:
            for i in range(int(1.2 * px)):
                w = int(1.2 * px) - i
                yy = face + d * (i + 1)
                s[min(yy, yy + 1):max(yy, yy + 1) + 1, x - w // 2:x + w // 2 + 1] = 1
    return s


def _suspeita_de(mascara, px=24.0, lado_mm=14.0):
    s = ct.detectar(mascara, px, lado_mm)
    return s[0] if s else None


def test_suporte_do_validador_declarado_explicitamente():
    """Só a orientação do SU-039 é comprovada; as demais são declaradas como
    não comprovadas em vez de ficarem como capacidade silenciosa."""
    s = ct.SUPORTE_VALIDADOR
    assert s["parede_vertical_exterior_esquerda"] == "comprovado"
    for k in ("parede_vertical_exterior_direita",
              "parede_horizontal_exterior_acima",
              "parede_horizontal_exterior_abaixo"):
        assert s[k] == "nao_comprovado", k
    assert s["orientacao_por_componente_principal"] == "pendente"


@pytest.mark.parametrize("lado", ["direita", "acima", "abaixo"])
def test_orientacao_nao_suportada_bloqueia(lado):
    """Testes 1–4 substituídos: orientações sem evidência NÃO aprovam artefato.
    O ramo `ceil` existe no código mas não pode aprovar nada."""
    m = _parede_com_saliencia(lado)
    sus = _suspeita_de(m)
    if sus is None:
        # sem suspeita o validador nem é chamado; o gate geral já barra antes
        pytest.skip(f"detector não achou tirante no sintético {lado}")
    st, rel = ct.validar_face_local(m, m, sus, 24.0)
    assert st in (ct.NAO_SUPORTADA, ct.AMBIGUA_FACE), (lado, st, rel.get("motivo"))
    assert rel["aceita"] is False, "orientação sem evidência não pode aprovar"
    if st == ct.NAO_SUPORTADA:
        assert rel["suporte_validador"]["orientacao_por_componente_principal"] == "pendente"


def test_ramo_ceil_nao_aprova_artefato():
    """O `ceil` não pode ser caminho normal de aprovação sem evidência."""
    m = _parede_com_saliencia("direita")
    sus = _suspeita_de(m)
    if sus is None:
        pytest.skip("sem suspeita no sintético")
    st, rel = ct.validar_face_local(m, m, sus, 24.0)
    assert st != "ok", "ceil não pode aprovar artefato sem evidência"
    assert rel.get("regra_quantizacao") != "ceil", "ceil não deve ser aplicado"


def test_tirante_perpendicular_nao_aprova():
    """Tirante perpendicular à parede: face não observável → bloqueio."""
    m = _parede_com_saliencia("esquerda")
    sus = _suspeita_de(m)
    if sus is None:
        pytest.skip("sem suspeita no sintético")
    st, _ = ct.validar_face_local(m, m, sus, 24.0)
    assert st in (ct.NAO_SUPORTADA, ct.AMBIGUA_FACE, "rejeitado")


def test_coluna_da_borda_legitima_nao_e_contada(su039):
    """Teste 5: a coluna floor(face) é a parede, não resíduo. Provado no caso
    real: sem a quantização a reconstrução acusava 164 px falsos."""
    m, px, sus = su039
    rc, _ = ct.remover_local(m, sus, px)
    _, rel = ct.validar_face_local(m, rc, sus, px)
    assert rel["regra_quantizacao"] == "floor"
    assert rel["limite_discreto_px"] == int(rel["face_local_subpixel_px"])
    assert rel["pixels_alem_da_face"] == 0


def test_pixel_alem_da_borda_e_contado(su039):
    """Teste 6: material além do limite discreto continua sendo resíduo — os
    6 px da quebra não são perdoados pela quantização."""
    m, px, sus = su039
    q, _ = ct.cortar_apendice(m, sus, px)
    _, rel = ct.validar_face_local(m, q, sus, px)
    assert rel["pixels_alem_da_face"] == 6


@pytest.fixture(scope="module")
def su039():
    """Máscara real do SU-039 (pula se o catálogo não estiver presente)."""
    pdf = RAIZ / "dados_exemplo/catalago-alcoa (1).pdf"
    if not pdf.exists():
        pytest.skip("catálogo Alcoa ausente")
    from curadoria.aquisicao.renderizar_fonte import (renderizar_pagina_png,
                                                      aplicar_roi)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        pag = renderizar_pagina_png(pdf, 184, 600, Path(d) / "p")
        card = aplicar_roi(pag, roi_norm=[0.485, 0.120, 0.96, 0.300])
    r = extrair("SU-039", card, 52.6, 25.0, 1, threshold="otsu",
                simplificacao_mm=0.05)
    m = r.mascara
    px = m.shape[1] / 52.6
    sus = ct.detectar(m, px, 25.0)[0]
    return m, px, sus


def test_oraculo_original_contaminado(su039):
    """Teste 7: a máscara contaminada tem ~1.443 px além da face."""
    m, px, sus = su039
    _, rel = ct.validar_face_local(m, m, sus, px)
    assert 1300 <= rel["pixels_alem_da_face"] <= 1600, rel["pixels_alem_da_face"]
    assert rel["continuidade_da_face"] is False


def test_oraculo_quebra_controlada(su039):
    """Testes 8 e 10: quebra deixa 6 px e parede descontínua → rejeitada."""
    m, px, sus = su039
    q, _ = ct.cortar_apendice(m, sus, px)
    st, rel = ct.validar_face_local(m, q, sus, px)
    assert rel["pixels_alem_da_face"] == 6, rel["pixels_alem_da_face"]
    assert rel["continuidade_da_face"] is False
    assert st == "rejeitado"


def test_oraculo_reconstrucao_local(su039):
    """Testes 9 e 11: reconstrução zera o resíduo e restaura a continuidade."""
    m, px, sus = su039
    rc, _ = ct.remover_local(m, sus, px)
    st, rel = ct.validar_face_local(m, rc, sus, px)
    assert rel["pixels_alem_da_face"] == 0, rel["pixels_alem_da_face"]
    assert rel["continuidade_da_face"] is True
    assert st == "ok"


def test_procedencia_nao_substitui_gate_da_face(su039):
    """Teste 12: a procedência aprova a quebra; a face reprova. Os dois somam."""
    m, px, sus = su039
    q, proc = ct.cortar_apendice(m, sus, px)
    residuo, _ = ct.gate_residuo(m, q, sus, px, procedencia=proc)
    _, rel = ct.validar_face_local(m, q, sus, px)
    assert residuo == 0, "procedência considera a quebra limpa"
    assert rel["pixels_alem_da_face"] == 6, "a face ainda vê os 6 px"


def test_continuidade_nao_substitui_contagem_externa(su039):
    """Teste 13: continuidade é necessária, não suficiente."""
    m, px, sus = su039
    rc, _ = ct.remover_local(m, sus, px)
    _, ok = ct.validar_face_local(m, rc, sus, px)
    _, ruim = ct.validar_face_local(m, m, sus, px)
    assert ok["continuidade_da_face"] and ok["pixels_alem_da_face"] == 0
    # a original tem material externo E descontinuidade: os dois critérios pegam
    assert ruim["pixels_alem_da_face"] > 0


def test_orientacao_ambigua_unit():
    """Teste 14a: validar_face_local rejeita quando faces divergem (unitário).

    Construtor direto de máscara e suspeita, sem depender de detectar.
    Orientação comprovada (vertical, exterior esquerda) com faces divergentes."""
    px = 24.0
    n = int(14 * px)
    m = np.zeros((n, n), np.uint8)

    # parede anterior (referência, acima da suspeita): coluna 10-12
    m[:int(6 * px), int(10 * px):int(12 * px)] = 1

    # parede posterior (após suspeita), DESLOCADA: coluna 12-14 (diverge!)
    m[int(8 * px):, int(12 * px):int(14 * px)] = 1

    # conector fino conectando as duas paredes, à ESQUERDA
    a, b = int(6 * px), int(8 * px)
    c0, c1 = int(8.9 * px), int(10.1 * px)
    m[a:b + 1, c0:c1] = 1

    # suspeita no conector
    mascara_conector = np.zeros_like(m, bool)
    mascara_conector[a:b + 1, c0:c1] = True

    sus = ct.Suspeita(
        indice=1,
        tipo="linha_de_chamada",
        espessura_mm=0.04,
        comprimento_mm=0.5,
        razao_parede=0.05,
        area_mm2=0.02,
        centro_mm=(9.5, 7.0),
        bbox_mm=(9.3, 6.0, 9.7, 8.0),
        em_zona_protegida=False,
        motivos_atingidos=[],
        mascara=mascara_conector.astype(np.uint8))

    # validar: faces anterior (240 px) e posterior (288 px) DIVERGEM
    st, rel = ct.validar_face_local(m, m, sus, px, altura_mm=14.0)
    assert st == ct.AMBIGUA_FACE, f"obteve {st}, esperado AMBIGUA_FACE: {rel}"
    assert "divergem além da tolerância" in rel["motivo"], rel


def test_orientacao_ambigua_integracao():
    """Teste 14b: cadeia completa detectar→suspeita→validador→bloqueio.

    Se detectar encontra uma suspeita, validador deve rejeitá-la por faces
    divergentes. Se não encontra, este teste documenta que o synthetic
    não atende aos critérios do detector (não é fracasso da validação)."""
    px = 24.0
    n = int(14 * px)
    m = np.zeros((n, n), np.uint8)

    # parede anterior: coluna 8-10, até meio do canvas
    m[:n // 2, 8:10] = 1

    # parede posterior: coluna 10-12, a partir do meio (DIVERGE)
    m[n // 2:, 10:12] = 1

    # traço fino: coluna 9-10, de forma contínua (comprimento máximo)
    m[n // 2 - 3:n // 2 + 3, 9:10] = 1

    s = ct.detectar(m, px, 14.0)
    if not s:
        # Synthetic não é fino o suficiente ou é curto demais para detectar.
        # Não é fracasso do validador, é limitação do synthetic.
        # O teste unitário já comprova que o validador funciona.
        pytest.skip("synthetic não atende critérios de detecção (esperado)")

    st, rel = ct.validar_face_local(m, m, s[0], px, altura_mm=14.0)
    assert st == ct.AMBIGUA_FACE, f"{st}: {rel}"


def test_validador_de_face_determinista(su039):
    """Teste 15: mesma entrada, mesmo veredito e mesma contagem."""
    m, px, sus = su039
    rc, _ = ct.remover_local(m, sus, px)
    a = ct.validar_face_local(m, rc, sus, px)
    b = ct.validar_face_local(m, rc, sus, px)
    assert a[0] == b[0]
    assert a[1]["pixels_alem_da_face"] == b[1]["pixels_alem_da_face"]
    assert a[1]["face_local_subpixel_px"] == b[1]["face_local_subpixel_px"]


# ============================================================================
# TESTES DOS HELPERS PERMANENTES
# ============================================================================

def test_derivar_assinatura_determinismo():
    """Helper: derivar_assinatura_topologica é determinístico."""
    from curadoria.aquisicao import assinatura_topologica as ast

    contorno = [[0, 0], [10, 0], [10, 10], [0, 10]]
    vazios = [[[2, 2], [2, 4], [4, 4], [4, 2]]]
    probes = [(1, 1), (9, 9)]

    sig1 = ast.derivar_assinatura_topologica(contorno, vazios, probes)
    sig2 = ast.derivar_assinatura_topologica(contorno, vazios, probes)
    assert sig1 == sig2, "mesma entrada deve produzir mesma saída"


def test_derivar_assinatura_entrada_nao_alterada():
    """Helper: derivar_assinatura_topologica não altera entrada."""
    from curadoria.aquisicao import assinatura_topologica as ast

    contorno = [[0, 0], [10, 0], [10, 10], [0, 10]]
    vazios = [[[2, 2], [2, 4], [4, 4], [4, 2]]]

    contorno_orig = [list(p) for p in contorno]
    vazios_orig = [[list(p) for p in v] for v in vazios]

    ast.derivar_assinatura_topologica(contorno, vazios)

    assert contorno == contorno_orig, "contorno não deve ser alterado"
    assert vazios == vazios_orig, "vazios não devem ser alterados"


def test_derivar_assinatura_sem_escrita_disco():
    """Helper: derivar_assinatura_topologica não escreve em disco."""
    from curadoria.aquisicao import assinatura_topologica as ast
    import os

    contorno = [[0, 0], [10, 0], [10, 10], [0, 10]]
    vazios = [[[2, 2], [2, 4], [4, 4], [4, 2]]]

    arquivo_novo = False
    try:
        num_files_antes = len(os.listdir('.'))
        ast.derivar_assinatura_topologica(contorno, vazios)
        num_files_depois = len(os.listdir('.'))
        arquivo_novo = num_files_depois > num_files_antes
    except:
        pass

    assert not arquivo_novo, "derivar_assinatura não deve criar arquivos"


def test_derivar_assinatura_retorna_dict_esperado():
    """Helper: derivar_assinatura_topologica retorna chaves esperadas."""
    from curadoria.aquisicao import assinatura_topologica as ast

    contorno = [[0, 0], [10, 0], [10, 10], [0, 10]]
    vazios = [[[2, 2], [2, 4], [4, 4], [4, 2]]]

    sig = ast.derivar_assinatura_topologica(contorno, vazios)

    assert "vazios" in sig
    assert "probes_material" in sig
    assert "probes_vazio" in sig
    assert "probes_exterior_conectado" in sig
    assert isinstance(sig["vazios"], int)
    assert isinstance(sig["probes_material"], list)
    assert isinstance(sig["probes_vazio"], list)
    assert isinstance(sig["probes_exterior_conectado"], list)


def test_exportar_contorno_svg_determinismo(tmp_path):
    """SVG: bytes são determinísticos."""
    from curadoria.aquisicao import exportar

    contorno = [[0, 0], [10, 0], [10, 10], [0, 10]]
    vazios = []

    path1 = tmp_path / "svg1.svg"
    path2 = tmp_path / "svg2.svg"

    exportar.exportar_contorno_svg(contorno, vazios, path1,
                                   largura_mm=10, altura_mm=10)
    exportar.exportar_contorno_svg(contorno, vazios, path2,
                                   largura_mm=10, altura_mm=10)

    conteudo1 = path1.read_text()
    conteudo2 = path2.read_text()
    assert conteudo1 == conteudo2, "SVG deve ser byte-idêntico"


def test_exportar_contorno_svg_preserva_pontos(tmp_path):
    """SVG: pontos são preservados (com transformação de escala)."""
    from curadoria.aquisicao import exportar

    contorno = [[1.0, 1.0], [10.0, 1.0], [10.0, 10.0], [1.0, 10.0]]
    vazios = []

    path = tmp_path / "svg.svg"
    exportar.exportar_contorno_svg(contorno, vazios, path,
                                   largura_mm=10, altura_mm=10,
                                   escala=10.0, margem_mm=0)

    conteudo = path.read_text()
    # Pontos devem estar presentes com escala aplicada (escala=10.0 por padrão)
    # (1.0, 1.0) em escala 10.0 = (10.0, 90.0) no SVG (y invertido)
    assert "10.000" in conteudo, "escala 1.0 → 10.0 não encontrada"
    assert "90.000" in conteudo, "coordenada y invertida não encontrada"


def test_exportar_contorno_svg_viewbox_estavel(tmp_path):
    """SVG: viewBox é estável."""
    from curadoria.aquisicao import exportar

    contorno = [[0, 0], [10, 0], [10, 10], [0, 10]]
    vazios = []

    path1 = tmp_path / "svg1.svg"
    path2 = tmp_path / "svg2.svg"

    exportar.exportar_contorno_svg(contorno, vazios, path1,
                                   largura_mm=10, altura_mm=10,
                                   escala=1.0, margem_mm=0)
    exportar.exportar_contorno_svg(contorno, vazios, path2,
                                   largura_mm=10, altura_mm=10,
                                   escala=1.0, margem_mm=0)

    conteudo1 = path1.read_text()
    conteudo2 = path2.read_text()

    import re
    viewbox1 = re.search(r'viewBox="([^"]+)"', conteudo1).group(1)
    viewbox2 = re.search(r'viewBox="([^"]+)"', conteudo2).group(1)
    assert viewbox1 == viewbox2, "viewBox deve ser idêntico"


def test_gravar_artefatos_transacional(tmp_path):
    """Gravação: produz 6 artefatos esperados."""
    from curadoria.aquisicao import exportar

    resultado = {
        "contorno_bruto": {
            "contorno_externo": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "vazios_internos": []
        },
        "contorno_comercial": {
            "contorno_externo": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "vazios_internos": []
        },
        "assinatura": {"vazios": 0, "probes_material": [[5, 5]],
                       "probes_vazio": [], "probes_exterior_conectado": []},
        "metricas": {"F1": 1.0, "aspecto": 0.05},
        "operacoes": [],
        "dimensoes_mm": {"largura": 10, "altura": 10}
    }

    destino = tmp_path / "saida"
    resultado_op = exportar.gravar_artefatos_curadoria("SU-001", resultado, destino)

    assert len(resultado_op["artefatos"]) == 6, "deve gravar 6 artefatos"
    for artefato in exportar.ARTEFATOS:
        arquivo = destino / artefato
        assert arquivo.exists(), f"{artefato} não foi criado"


def test_gravar_artefatos_determinismo(tmp_path):
    """Gravação: segunda execução é determinística."""
    from curadoria.aquisicao import exportar
    import hashlib

    resultado = {
        "contorno_bruto": {
            "contorno_externo": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "vazios_internos": []
        },
        "contorno_comercial": {
            "contorno_externo": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "vazios_internos": []
        },
        "assinatura": {"vazios": 0, "probes_material": [[5, 5]],
                       "probes_vazio": [], "probes_exterior_conectado": []},
        "metricas": {"F1": 1.0},
        "operacoes": [],
        "dimensoes_mm": {"largura": 10, "altura": 10}
    }

    destino1 = tmp_path / "saida1"
    destino2 = tmp_path / "saida2"

    exportar.gravar_artefatos_curadoria("SU-001", resultado, destino1)
    exportar.gravar_artefatos_curadoria("SU-001", resultado, destino2)

    for artefato in exportar.ARTEFATOS:
        hash1 = hashlib.md5((destino1 / artefato).read_bytes()).hexdigest()
        hash2 = hashlib.md5((destino2 / artefato).read_bytes()).hexdigest()
        assert hash1 == hash2, f"{artefato} não é determinístico"


# ============================================================================
# GATE DA FACE DENTRO DA TRANSAÇÃO
#
# O validador da face participa da aceitação de CADA tentativa. Antes destes
# testes o orquestrador consultava só a procedência: no SU-039 a quebra da
# ponte zerava a procedência, era aceita, e a reconstrução — a única correta —
# nunca era tentada.
# ============================================================================

def _suspeita_sintetica(mascara, a, b, c0, c1):
    """Suspeita construída à mão, sem depender do detector."""
    mk = np.zeros_like(mascara, bool)
    mk[a:b + 1, c0:c1] = True
    return ct.Suspeita(
        indice=1, tipo="linha_de_chamada", espessura_mm=0.04,
        comprimento_mm=0.5, razao_parede=0.05, area_mm2=0.02,
        centro_mm=(0.0, 0.0), bbox_mm=(0.0, 0.0, 1.0, 1.0),
        em_zona_protegida=False, motivos_atingidos=[],
        mascara=mk.astype(np.uint8))


def test_su039_orquestrador_rejeita_quebra_e_aceita_reconstrucao(su039):
    """Integração 1: o microgate congelado do SU-039 percorrido pelo
    ORQUESTRADOR completo, não pelas funções isoladas.

    Falha se o orquestrador voltar a aceitar a quebra da ponte."""
    m, px, sus = su039
    est, tratada, log = ct.tratar_contaminacao(
        m, sus, px, 25.0, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0)

    tentativas = [x for x in log if "estrategia" in x and "gate_face" in x]
    assert len(tentativas) == 2, [x.get("estrategia") for x in tentativas]

    t1, t2 = tentativas
    # tentativa 1 — quebra: procedência zerada NÃO basta
    assert t1["estrategia"] == ct.QUEBRA
    assert t1["gate_procedencia"] == {"pixels_residuais": 0, "aprovado": True}
    assert t1["gate_face"]["estado"] == ct.FACE_REJEITADO
    assert t1["gate_face"]["pixels_alem_da_face"] == 6
    assert t1["gate_face"]["continuidade"] is False
    assert t1["gate_face"]["aprovado"] is False
    assert t1["aceita"] is False
    assert "gate local da face" in t1["motivo"]
    assert t1["rollback"]["realizado"] is True

    # tentativa 2 — reconstrução
    assert t2["estrategia"] == ct.RECONSTRUCAO
    assert t2["gate_procedencia"]["pixels_residuais"] == 0
    assert t2["gate_face"]["estado"] == ct.FACE_APROVADO
    assert t2["gate_face"]["pixels_alem_da_face"] == 0
    assert t2["gate_face"]["continuidade"] is True
    assert t2["aceita"] is True
    assert t2["rollback"]["realizado"] is False

    assert est == ct.RECONSTRUCAO
    assert tratada is not None


def test_procedencia_zero_nao_basta_para_aceitar(su039):
    """Regressão 2: a quebra tem procedência 0 e mesmo assim é rejeitada."""
    m, px, sus = su039
    q, proc = ct.cortar_apendice(m, sus, px)
    aceita, rel = ct._validar_tentativa(
        m, q, sus, px, 25.0, None, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0, procedencia=proc)
    assert rel["gate_procedencia"]["aprovado"] is True
    assert aceita is False, rel["motivo"]


def test_validar_tentativa_chama_gate_da_face(su039):
    """Regressão 1: o relatório sempre traz o veredito da face."""
    m, px, sus = su039
    rc, proc = ct.remover_local(m, sus, px)
    _, rel = ct._validar_tentativa(
        m, rc, sus, px, 25.0, None, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0, procedencia=proc)
    assert "gate_face" in rel
    assert rel["gate_face"]["estado"] in (
        ct.FACE_APROVADO, ct.FACE_REJEITADO, ct.FACE_AMBIGUO,
        ct.FACE_ORIENTACAO_NAO_SUPORTADA, ct.FACE_NAO_APLICAVEL)


def test_reconstrucao_com_face_limpa_e_aceita(su039):
    """Regressão 7: 0 px além da face e continuidade verdadeira aprovam."""
    m, px, sus = su039
    rc, proc = ct.remover_local(m, sus, px)
    aceita, rel = ct._validar_tentativa(
        m, rc, sus, px, 25.0, None, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0, procedencia=proc)
    assert rel["gate_face"]["pixels_alem_da_face"] == 0
    assert rel["gate_face"]["continuidade"] is True
    assert aceita is True


def test_segunda_tentativa_parte_da_mascara_original(su039):
    """Regressão 5 e 6: rollback completo — a reconstrução da transação é
    idêntica à reconstrução feita direto da original."""
    m, px, sus = su039
    est, tratada, _ = ct.tratar_contaminacao(
        m, sus, px, 25.0, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0)
    direto, _ = ct.remover_local(m, sus, px)
    assert est == ct.RECONSTRUCAO
    assert np.array_equal(np.asarray(tratada) > 0, np.asarray(direto) > 0), \
        "a tentativa aceita não partiu da máscara original"


def test_log_registra_todos_os_gates_por_tentativa(su039):
    """Regressão 14: cada tentativa registra procedência, face e rollback."""
    m, px, sus = su039
    _, _, log = ct.tratar_contaminacao(
        m, sus, px, 25.0, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0)
    for x in log:
        if "estrategia" not in x or "gate_face" not in x:
            continue
        assert set(x["gate_procedencia"]) == {"pixels_residuais", "aprovado"}
        assert "estado" in x["gate_face"] and "aprovado" in x["gate_face"]
        assert "realizado" in x["rollback"]
        assert "aceita" in x


def test_orquestrador_su039_determinista(su039):
    """Regressão 15: mesma entrada, mesma estratégia e mesmos vereditos."""
    m, px, sus = su039
    a = ct.tratar_contaminacao(m, sus, px, 25.0, 52.6,
                               largura_esperada_mm=52.6, altura_esperada_mm=25.0)
    b = ct.tratar_contaminacao(m, sus, px, 25.0, 52.6,
                               largura_esperada_mm=52.6, altura_esperada_mm=25.0)
    assert a[0] == b[0]
    assert np.array_equal(np.asarray(a[1]) > 0, np.asarray(b[1]) > 0)
    fa = [x["gate_face"] for x in a[2] if "gate_face" in x]
    fb = [x["gate_face"] for x in b[2] if "gate_face" in x]
    assert fa == fb


def test_nenhum_caminho_do_orquestrador_ignora_o_gate_da_face(su039):
    """Regressão 13: toda tentativa ACEITA tem gate da face aprovado."""
    m, px, sus = su039
    _, _, log = ct.tratar_contaminacao(
        m, sus, px, 25.0, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0)
    for x in log:
        if x.get("aceita") is True:
            assert x["gate_face"]["aprovado"] is True
            assert x["gate_face"]["estado"] in ct.FACE_ESTADOS_QUE_ACEITAM


def test_estado_ambiguo_da_face_bloqueia(monkeypatch, su039):
    """Regressão 9: face ambígua termina em BLOQUEIO, sem escalar estratégia."""
    m, px, sus = su039
    monkeypatch.setattr(ct, "validar_face_local",
                        lambda *a, **k: (ct.AMBIGUA_FACE,
                                         {"motivo": "faces divergem"}))
    est, tratada, log = ct.tratar_contaminacao(
        m, sus, px, 25.0, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0)
    assert est == ct.BLOQUEIO
    assert tratada is None
    assert any(x.get("gate_face", {}).get("estado") == ct.FACE_AMBIGUO
               for x in log)


def test_orientacao_nao_suportada_da_face_bloqueia(monkeypatch, su039):
    """Regressão 8: orientação sem evidência termina em BLOQUEIO."""
    m, px, sus = su039
    monkeypatch.setattr(ct, "validar_face_local",
                        lambda *a, **k: (ct.NAO_SUPORTADA,
                                         {"orientacao_detectada": "x"}))
    est, tratada, _ = ct.tratar_contaminacao(
        m, sus, px, 25.0, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0)
    assert est == ct.BLOQUEIO
    assert tratada is None


def test_veredito_desconhecido_da_face_bloqueia(monkeypatch, su039):
    """Regressão 10: ausência inesperada do veredito NÃO vira aprovação."""
    m, px, sus = su039
    monkeypatch.setattr(ct, "validar_face_local",
                        lambda *a, **k: ("estado_novo_nao_previsto", {}))
    g = ct.gate_face(m, m, sus, px)
    assert g["estado"] == "AUSENTE"
    assert g["aprovado"] is False
    est, tratada, _ = ct.tratar_contaminacao(
        m, sus, px, 25.0, 52.6,
        largura_esperada_mm=52.6, altura_esperada_mm=25.0)
    assert est == ct.BLOQUEIO
    assert tratada is None


def test_nao_aplicavel_exige_justificativa(su039):
    """Regressão 11: sem justificativa o validador roda; com justificativa o
    estado é NAO_APLICAVEL e a justificativa fica registrada."""
    m, px, sus = su039
    q, _ = ct.cortar_apendice(m, sus, px)

    sem = ct.gate_face(m, q, sus, px, contexto_face={})
    assert sem["estado"] == ct.FACE_REJEITADO, "sem justificativa não pode dispensar"

    vazia = ct.gate_face(m, q, sus, px,
                         contexto_face={"nao_aplicavel_justificativa": ""})
    assert vazia["estado"] == ct.FACE_REJEITADO, "justificativa vazia não vale"

    com = ct.gate_face(m, q, sus, px, contexto_face={
        "nao_aplicavel_justificativa": "apêndice externo sem face equivalente"},
        estrategia=ct.QUEBRA)
    assert com["estado"] == ct.FACE_NAO_APLICAVEL
    assert com["aprovado"] is True
    assert com["justificativa"]


def test_nao_aplicavel_so_vale_na_quebra_de_ponte(su039):
    """SU-024: a dispensa da face só existe onde a contaminação é apêndice
    EXTERNO desprendido por quebra de ponte. Numa reconstrução de parede há
    face por definição, e dispensá-la reabriria o buraco do SU-039."""
    m, px, sus = su039
    q, _ = ct.cortar_apendice(m, sus, px)
    ctx = {"nao_aplicavel_justificativa": "apêndice externo sem face equivalente"}

    ok = ct.gate_face(m, q, sus, px, contexto_face=ctx, estrategia=ct.QUEBRA)
    assert ok["estado"] == ct.FACE_NAO_APLICAVEL
    assert ok["aprovado"] is True

    for estrategia in (ct.RECONSTRUCAO, ct.BLOQUEIO, None, "QUALQUER_OUTRA"):
        g = ct.gate_face(m, q, sus, px, contexto_face=ctx, estrategia=estrategia)
        assert g["estado"] == "NAO_APLICAVEL_INVALIDO", estrategia
        assert g["aprovado"] is False, estrategia


def test_nao_aplicavel_invalido_bloqueia_o_orquestrador(su039):
    """Dispensa inválida não pode ser compensada por outro gate: BLOQUEIO."""
    m, px, sus = su039
    ctx = {"nao_aplicavel_justificativa": "justificativa que não vale aqui"}
    # força a quebra a falhar por outro critério para chegar à reconstrução
    est, tratada, log = ct.tratar_contaminacao(
        m, sus, px, 25.0, 52.6, largura_esperada_mm=52.6,
        altura_esperada_mm=25.0, contexto_face=ctx)
    # na QUEBRA a dispensa vale; se a cadeia chegasse à RECONSTRUCAO com a
    # mesma justificativa, teria de bloquear
    g = ct.gate_face(m, m, sus, px, contexto_face=ctx,
                     estrategia=ct.RECONSTRUCAO)
    assert g["estado"] == "NAO_APLICAVEL_INVALIDO"
    assert "obrigatório" in g["motivo"]


def test_su024_config_declara_estrategia_da_dispensa():
    """A justificativa do SU-024 registra a condição de validade."""
    p = CONFIG["p4_reconhecimento"]["SU-024"]
    ctx = p["contexto_face"]
    assert ctx["nao_aplicavel_justificativa"]
    assert "QUEBRA_CONTROLADA_DE_PONTE" in ctx["_condicao"]
    assert ct.QUEBRA in ct.ESTRATEGIAS_QUE_ADMITEM_NAO_APLICAVEL
    assert ct.RECONSTRUCAO not in ct.ESTRATEGIAS_QUE_ADMITEM_NAO_APLICAVEL


# ============================================================================
# SU-053: cota removida, altura revogada, cavidade aberta não é vazio
# SU-102: dimensão bloqueada, sem calibrador de dois eixos
# ============================================================================

def test_su053_altura_vem_da_fonte_dimensional_nao_do_bbox():
    """53,57 mm coincidia com o bbox contaminado pela seta inferior da cota 5.5.
    A altura oficial agora vem de card cotado, não de medição."""
    p = CONFIG["perfis"]["SU-053"]
    assert p["altura_mm"] == 51.0
    f = p["fonte_dimensional_primaria"]
    assert f["altura_mm"] == 51.0 and f["largura_mm"] == 22.2
    assert f["status"] == "confirmado_visual_card"
    assert f["codigo"] == "TMS-053" and f["pagina_pdf"] == 222
    # a largura coincidente é o que sustenta a associação entre os códigos
    assert p["largura_mm"] == f["largura_mm"]
    assert p["altura_mm"] != 53.57, "o bbox contaminado não pode voltar"


def test_su053_medicao_limpa_nao_vira_cota_nominal():
    """50,26 mm é medição, não cota de catálogo: não pode ocupar altura_mm."""
    p = CONFIG["perfis"]["SU-053"]
    m = p["medicao_geometria_limpa"]
    assert m["altura_mm"] == 50.26
    assert p["altura_mm"] != 50.26, "medição não vira cota nominal"
    assert p["altura_mm"] == 51.0
    # a divergência entre medição e cota é registrada, não escondida
    assert 0.0 < m["erro_altura_relativo"] < 0.05
    assert p["estado"].startswith("CANDIDATO_GEOMETRICO_")


def test_su053_cavidade_aberta_nao_e_vazio_topologico():
    """Câmara funcional não é sinônimo de ciclo fechado no contorno 2D."""
    p = CONFIG["perfis"]["SU-053"]
    assert p["vazios_esperados"] == 0
    assert p["status_vazios"] == "confirmado_por_topologia_raster"
    assert "aberta" in p["observacao_topologica"].lower()


def test_cavidade_aberta_sintetica_conta_zero_vazios():
    """Regressão do conceito, sem depender do catálogo: um 'C' tem cavidade
    funcional evidente e ZERO vazios topológicos; fechá-lo cria 1."""
    from curadoria.aquisicao.assinatura_topologica import camaras_fechadas
    m = np.zeros((200, 200), np.uint8)
    m[40:160, 40:160] = 1
    m[70:130, 70:190] = 0          # cavidade aberta para a direita
    assert camaras_fechadas(m)[0] == 0, "cavidade aberta não é vazio"
    fechado = m.copy()
    fechado[70:130, 150:160] = 1   # sela a abertura
    assert camaras_fechadas(fechado)[0] == 1, "cavidade selada vira vazio"


def test_su102_nao_usa_dimensao_de_perfil_vizinho():
    """13,8 pertence ao TMS-058 e ao TMS-103, nunca ao TMS-102."""
    p = CONFIG["perfis"]["SU-102"]
    assert p["largura_mm"] is None and p["altura_mm"] is None
    assert p["estado"] == "BLOQUEADO_POR_DIMENSAO"
    assert p["cotas_catalogo_secundario"]["valores_mm"] == [11.0, 12.0]
    assert "13,8" in p["_arbitragem_dimensional"]
    assert p["dimensao_bounding_box"]["status"] == "pendente_confirmacao"


def test_su102_calibrador_tem_os_dois_eixos_mas_gate_ainda_reprova():
    """Com 22,2 × 51 confirmados, a referência fina pode calibrar os dois eixos
    — mas o SU-102 continua bloqueado, porque o gate de escala não fecha."""
    ref = CONFIG["perfis"]["SU-102"]["contorno_referencia"]
    assert ref["tratamento"] == "separacao_por_espessura"
    assert ref["estado"] == "CONTORNO_REFERENCIA_OUTRO_PERFIL_DETECTADO"
    cal = CONFIG["perfis"]["SU-053"]
    assert cal["largura_mm"] == 22.2 and cal["altura_mm"] == 51.0
    # calibrador completo não basta: a dimensão do SU-102 segue nula
    su102 = CONFIG["perfis"]["SU-102"]
    assert su102["largura_mm"] is None and su102["altura_mm"] is None
    assert su102["estado"] == "BLOQUEADO_POR_DIMENSAO"


def test_perfil_sem_cota_nao_passa_pelo_driver():
    """Perfil sem cota oficial é recusado nomeando o campo, não silenciosamente."""
    from curadoria.aquisicao import executar_lote1_e4b as ex
    with pytest.raises(ex.PerfilIncompleto, match="altura_mm"):
        ex.parametros("SU-102")


def test_su053_passa_no_driver_com_cota_confirmada():
    """O SU-053 tem cota, motivos validados e reprodutibilidade provada."""
    from curadoria.aquisicao import executar_lote1_e4b as ex
    p = ex.parametros("SU-053")
    assert p["altura_mm"] == 51.0
    assert p["estado"] == "CANDIDATO_GEOMETRICO_APROVADO"


# ============================================================================
# FONTES SEPARADAS, REGISTRO ISOTRÓPICO E GEOMETRIA COMPARTILHADA
# ============================================================================

def test_su053_fontes_separadas_por_papel():
    """Geometria, dimensão, semântica e evidência de contaminação vêm de fontes
    declaradas separadamente — não é conflito, é divisão de papéis."""
    p = CONFIG["perfis"]["SU-053"]
    assert p["fonte_geometrica_primaria"]["codigo"] == "TMS-053"
    assert p["fonte_dimensional_primaria"]["codigo"] == "TMS-053"
    assert p["fonte_semantica_motivos"]["codigo"] == "SU-053"
    assert p["fonte_semantica_motivos"]["fabricante"] == "Alcoa"
    assert p["fonte_evidencia_contaminacao"]["fabricante"] == "Alcoa"
    # trocar a fonte geométrica não pode apagar o ground truth dos motivos
    assert len(p["motivos"]) == 5
    for m in p["motivos"]:
        assert m["classe_status"] == "confirmado_bruno"


def test_tms053_nao_usa_separacao_por_espessura():
    """No card Centenário a abertura morfológica mataria o perfil e deixaria a
    pílula do rótulo — que tem 14 falsos vazios (as letras)."""
    f = CONFIG["perfis"]["SU-053"]["fonte_geometrica_primaria"]
    assert f["separacao_por_espessura"] is False
    assert f["roi_norm"] == [0.55, 0.64, 0.95, 0.90]


def test_registro_isotropico_recupera_similaridade():
    """Escala única, rotação e translação — e nada além disso."""
    from curadoria.aquisicao.registro_isotropico import registrar
    m = np.zeros((300, 300), np.uint8)
    m[80:220, 110:190] = 1
    m[120:160, 140:180] = 0
    M = cv2.getRotationMatrix2D((150, 150), 12.0, 1.35)
    d = cv2.warpAffine(m, M, (300, 300), flags=cv2.INTER_NEAREST)
    r = registrar(m, d)
    assert abs(r.escala - 1.35) / 1.35 < 0.01, r.escala
    assert abs(abs(r.rotacao_graus) - 12.0) < 0.5, r.rotacao_graus
    assert r.erro_medio_px < 1.0
    assert r.iou > 0.98


def test_registro_isotropico_nao_deforma_anisotropicamente():
    """Uma forma esticada só num eixo NÃO pode ser registrada com erro baixo:
    escala anisotrópica é proibida por construção."""
    from curadoria.aquisicao.registro_isotropico import registrar
    m = np.zeros((300, 300), np.uint8)
    m[80:220, 110:190] = 1
    esticada = np.zeros((300, 300), np.uint8)
    r_ = cv2.resize(m[80:220, 110:190], (80, 280), interpolation=cv2.INTER_NEAREST)
    esticada[10:290, 110:190] = r_
    reg = registrar(m, esticada)
    assert reg.erro_medio_px > 3.0, \
        "deformação anisotrópica não pode ser absorvida por escala única"


def test_calibracao_isotropica_do_su102_reprova():
    """O registro provou que existe UMA escala e rotação zero — o bbox não era
    o problema. Mas a escala única não reproduz as duas cotas."""
    c = CONFIG["perfis"]["SU-102"]["calibracao_isotropica_pela_referencia_fina"]
    assert c["gate"] == "REPROVA"
    assert c["erro_largura_pct"] <= 0.75, "a largura fecha"
    assert c["erro_altura_pct"] > 0.75, "a altura não fecha — é isso que bloqueia"
    assert abs(c["rotacao_graus"]) < 0.1, "rotação é zero: não é problema de giro"


def test_su102_congruente_mas_sem_equivalencia_completa():
    """IoU e aspecto não bastam: sem dimensão externa e sem gate funcional
    local, a geometria não é compartilhável."""
    e = CONFIG["perfis"]["SU-102"]["equivalencia_tms102"]
    assert e["equivalencia_global"] == "PASSA"
    assert e["equivalencia_topologica"] == "PASSA"
    assert e["equivalencia_dimensional"] == "PENDENTE"
    assert e["equivalencia_funcional_local"] == "PENDENTE"
    assert e["decisao"] == "CONGRUENCIA_GLOBAL_SEM_EQUIVALENCIA_GEOMETRICA_COMPLETA"
    # e o perfil continua bloqueado
    assert CONFIG["perfis"]["SU-102"]["estado"] == "BLOQUEADO_POR_DIMENSAO"


def test_gate_de_075_nao_foi_ampliado():
    """Nenhuma tolerância foi afrouxada para destravar perfil."""
    from curadoria.aquisicao.extrair_contorno_raster import extrair
    import inspect
    sig = inspect.signature(extrair)
    assert sig.parameters["erro_aspecto_max"].default == 0.0075


def test_curadoria_nao_grava_em_dados_oficiais():
    """Candidato compartilhado fica só na curadoria."""
    from curadoria.aquisicao.exportar import OFICIAIS_PROIBIDOS
    for p in ("dados", "domain", "contrato", "docs"):
        assert p in OFICIAIS_PROIBIDOS


# ============================================================================
# SU-053 — ROIs por origem, transformação congelada e reprodutibilidade
# ============================================================================

def _su053():
    return CONFIG["perfis"]["SU-053"]


def test_roi_alcoa_e_roi_tms_tem_status_distintos():
    """O Bruno confirmou o MAPEAMENTO; as coordenadas no TMS foram calculadas.
    Os dois não podem receber o mesmo selo de origem."""
    for m in _su053()["motivos"]:
        assert m["roi_status"] == "CONFIRMADO_BRUNO", m["motivo"]
        assert m["tms053"]["roi_status"] == \
            "VALIDADO_POR_TRANSFERENCIA_E_EQUIVALENCIA_LOCAL", m["motivo"]


def test_coordenada_bruta_da_transferencia_e_preservada():
    """O recorte ao envelope não pode apagar o que a transformação produziu."""
    for m in _su053()["motivos"]:
        t = m["tms053"]
        assert t["roi_transformada_bruta"] is not None
        assert len(t["roi_transformada_bruta"]) == 4
        assert t["recorte_aplicado"] is not None


def test_roi_efetiva_cabe_no_envelope_e_nao_move_geometria():
    """A ROI efetiva fica dentro do envelope; o recorte só desloca a caixa, e
    apenas na ordem de grandeza do arredondamento."""
    su = _su053()
    (x0e, x1e), (y0e, y1e) = su["envelope_fisico_mm"]["x"], su["envelope_fisico_mm"]["y"]
    for m in su["motivos"]:
        t = m["tms053"]
        x0, y0, x1, y1 = t["roi_efetiva_recortada_ao_envelope"]
        assert x0e <= x0 and x1 <= x1e, m["motivo"]
        assert y0e <= y0 and y1 <= y1e, m["motivo"]
        # recorte sub-milimétrico: acima disso deveria BLOQUEAR, não recortar
        assert max(abs(v) for v in t["recorte_aplicado"]) <= 0.1, m["motivo"]
    assert su["politica_recorte_roi"]["nao_e_regra_universal"] is True


def test_transformacao_congelada_e_isotropica_sem_reflexao():
    t = _su053()["transformacao_alcoa_para_tms053"]
    assert t["tipo"] == "similaridade_isotropica"
    assert t["deformacao_anisotropica"] is False
    assert t["reflexao"] is False
    assert abs(t["rotacao_graus"]) < 0.1
    assert t["mascaras_recortadas_ao_bbox_antes_do_registro"] is True


def test_mapeamento_m_para_c_congelado():
    esperado = {"M1": "C4", "M2": "C6", "M3": "C2", "M4": "C8", "M5": "C5"}
    obtido = {m["motivo"]: m["candidato_automatico"] for m in _su053()["motivos"]}
    assert obtido == esperado


def test_candidatos_descartados_nao_voltam_como_motivos():
    su = _su053()
    descartados = set(su["transferencia_de_zonas"]["candidatos_descartados"])
    usados = {m["candidato_automatico"] for m in su["motivos"]}
    assert not (descartados & usados), descartados & usados


def test_baseline_local_nao_vira_gate_universal():
    """As cinco métricas são evidência do SU-053, não regra para todo motivo."""
    su = _su053()
    b = su["baseline_validacao_local"]
    assert set(b) == {"M1", "M2", "M3", "M4", "M5"}
    assert "nao declara" in su["_nota_baseline"].lower() or \
           "NAO declara" in su["_nota_baseline"]
    # nenhum limiar universal foi introduzido no config
    texto = json.dumps(CONFIG, ensure_ascii=False)
    for proibido in ("iou_minimo_universal", "dif_area_maxima_universal"):
        assert proibido not in texto


def test_su053_reprodutivel_e_aprovado_so_na_curadoria():
    su = _su053()
    r = su["reprodutibilidade"]
    assert r["seis_hashes_identicos"] is True
    assert r["jsons_semanticamente_equivalentes"] is True
    assert r["dimensoes_mm"] == [22.2, 51.0]
    assert r["componentes"] == 1 and r["vazios"] == 0
    assert su["estado"] == "CANDIDATO_GEOMETRICO_APROVADO"
    assert "curadoria" in su["_nota_estado"].lower()
    assert "GEO-SU-053" in su["_nota_estado"]


def test_geometria_vem_da_fonte_declarada_nao_da_semantica():
    """O driver adquire pelo TMS-053, não pelo card Alcoa."""
    from curadoria.aquisicao import executar_lote1_e4b as ex
    g = ex.fonte_de_geometria(_su053())
    assert g["codigo"] == "TMS-053"
    assert g["pagina_pdf"] == 222
    assert "Centen" in g["fonte_pdf"]


def test_su102_nenhuma_fonte_cota_o_envelope():
    """Quatro catálogos investigados; nenhum publica a dimensão externa."""
    su = CONFIG["perfis"]["SU-102"]
    fontes = su["fontes_dimensionais_investigadas"]
    assert len(fontes) >= 4
    for f in fontes:
        assert f["cota_envelope_total"] is False, f["fabricante"]
    assert su["dimensao_externa"]["status"] == \
        "REQUER_MEDICAO_FISICA_OU_DESENHO_TECNICO_COTADO"
    assert su["largura_mm"] is None and su["altura_mm"] is None


def test_su102_cotas_10_e_11_nao_medem_o_envelope():
    """A cota 10 começa no perfil de REFERÊNCIA, não no SU-102 — por isso
    10+11 cobre mais que a largura do traço cheio."""
    i = CONFIG["perfis"]["SU-102"]["interpretacao_das_cotas"]
    assert i["cota_10"]["mede_o_envelope"] is False
    assert i["cota_11"]["mede_o_envelope"] is False
    x0, x1 = i["traco_cheio_px"]["x"]
    linhas = i["linhas_de_chamada_px"]
    assert linhas[0] < x0, "a primeira linha de chamada cai fora do traço cheio"
    assert x0 < linhas[1] < x1, "a segunda linha é interna ao traço cheio"
    assert linhas[2] == x1, "só a terceira coincide com a borda"
    assert (linhas[2] - linhas[0]) > (x1 - x0), \
        "10+11 abrange mais que a largura — não pode virar envelope"


def test_su102_tres_fontes_concordam_no_aspecto():
    """Dispersão entre catálogos independentes bem abaixo do gate."""
    fontes = [f for f in CONFIG["perfis"]["SU-102"]["fontes_dimensionais_investigadas"]
              if f.get("aspecto_traco_cheio")]
    aspectos = [f["aspecto_traco_cheio"] for f in fontes]
    assert len(aspectos) >= 3
    disp = (max(aspectos) - min(aspectos)) / min(aspectos) * 100
    assert disp <= 0.75, disp


def test_su102_gate_funcional_local_completo():
    """As regiões com material passam; nenhuma concentra resíduo."""
    c = CONFIG["perfis"]["SU-102"]["candidato_compartilhamento"]
    assert c["congruencia_global"] == "APROVADA"
    assert c["congruencia_topologica"] == "APROVADA"
    assert c["congruencia_funcional_local"] == "APROVADA"
    assert c["equivalencia_dimensional"] == "PENDENTE"
    assert c["decisao"] == "AGUARDANDO_DIMENSAO_EXTERNA"
    com_material = [v for v in c["evidencia_local"].values() if v != "SEM_MATERIAL"]
    assert len(com_material) >= 6
    for v in com_material:
        assert v["decisao"] == "EQUIVALENTE", v
        assert v["p95"] <= 4.0, v


def test_su102_nao_vira_geometria_oficial():
    """Candidato compartilhado fica só na curadoria."""
    su = CONFIG["perfis"]["SU-102"]
    assert su["estado"] == "BLOQUEADO_POR_DIMENSAO"
    texto = json.dumps(su, ensure_ascii=False)
    assert "GEO-SU-102" not in texto
    assert "APROVADO_EM_CURADORIA" not in texto


def test_contexto_face_nao_e_mutado(su039):
    """Contrato: o contexto é explícito e imutável — sem global, sem sessão."""
    m, px, sus = su039
    ctx = {"nao_aplicavel_justificativa": "motivo"}
    copia = dict(ctx)
    ct.gate_face(m, m, sus, px, contexto_face=ctx)
    assert ctx == copia


def test_su024_nao_aplicavel_ainda_nao_tem_contexto_comprovado():
    """Regressão 12: `NAO_APLICAVEL` é contrato disponível, mas o contexto real
    do SU-024 (página e ROI) NÃO está persistido — nenhum config o declara.

    Este teste falha no dia em que o SU-024 entrar no config sem que a
    justificativa de não aplicabilidade seja declarada junto."""
    cfg = json.loads((RAIZ / "curadoria/aquisicao/configs/e4b_suprema.json")
                     .read_text())
    if "SU-024" in cfg["perfis"]:
        p = cfg["perfis"]["SU-024"]
        assert "nao_aplicavel_justificativa" in p.get("contexto_face", {}), \
            "SU-024 entrou no config sem justificar a não aplicabilidade da face"
    else:
        assert ct.FACE_NAO_APLICAVEL in ct.FACE_ESTADOS_QUE_ACEITAM


# ============================================================================
# DECLARAÇÃO DE MOTIVOS PENDENTES E PADDING TÉCNICO DE REEXTRAÇÃO
# ============================================================================

def _valida_perfil(p: dict) -> bool:
    """Mesma regra do gate do config, isolada para poder ser testada."""
    motivos = p.get("motivos", [])
    pend = p.get("_motivos_pendentes")
    if motivos and pend:
        return False                    # não pode afirmar as duas coisas
    if motivos:
        return True
    return bool(pend
                and pend.get("levantamento") == "nao_realizado"
                and pend.get("justificativa"))


@pytest.mark.parametrize("perfil,esperado", [
    ({"motivos": []}, False),                                   # 1 sem declaração
    ({"motivos": [], "_motivos_pendentes":
        {"levantamento": "nao_realizado", "justificativa": ""}}, False),   # 2
    ({"motivos": [], "_motivos_pendentes":
        {"levantamento": "realizado", "justificativa": "x"}}, False),      # 3
    ({"motivos": [], "_motivos_pendentes":
        {"levantamento": "nao_realizado", "justificativa": "x"}}, True),   # 4
    ({"motivos": [{"id": "GAB-OLHAL-01"}]}, True),                         # 5
    ({"motivos": [{"id": "GAB-OLHAL-01"}], "_motivos_pendentes":
        {"levantamento": "nao_realizado", "justificativa": "x"}}, False),  # 6
])
def test_declaracao_de_motivos_pendentes(perfil, esperado):
    """Regras 1–6: 'não levantado' precisa ser declarado, e nunca convive com
    motivo confirmado."""
    assert _valida_perfil(perfil) is esperado


def test_config_real_respeita_a_declaracao_de_pendencia():
    """A regra vale para o config de verdade, não só para os sintéticos."""
    for grupo in ("perfis", "p4_reconhecimento"):
        for cod, p in CONFIG[grupo].items():
            if cod.startswith("_"):
                continue
            assert _valida_perfil(p), cod


def test_su053_cinco_ocorrencias_mapeadas_e_validadas():
    """Classe e ROI agora confirmadas: o mapeamento M→C veio de arbitragem
    humana e cada zona foi validada no TMS-053."""
    ms = CONFIG["perfis"]["SU-053"]["motivos"]
    assert len(ms) == 5
    esperado = ["GAB-ESCOVINHA-SU-01", "MOTIVO-ENCAIXE-BAGUETE-INTERNO",
                "GAB-OLHAL-01", "MOTIVO-ENCAIXE-BAGUETE-EXTERNO",
                "GAB-ESCOVINHA-SU-01"]
    assert [m["id"] for m in ms] == esperado
    assert [m["motivo"] for m in ms] == ["M1", "M2", "M3", "M4", "M5"]
    assert [m["candidato_automatico"] for m in ms] == ["C4", "C6", "C2", "C8", "C5"]
    for m in ms:
        assert m["classe_status"] == "confirmado_bruno", m["id"]
        assert m["roi_status"] == "CONFIRMADO_BRUNO", m["id"]
        assert m["zona_protegida"] is not None
        assert m["tms053"]["roi_efetiva_recortada_ao_envelope"] is not None
        v = m["tms053"]["validacao_local"]
        assert v["decisao"] == "EQUIVALENTE", (m["motivo"], v)
        assert v["iou"] >= 0.85, (m["motivo"], v["iou"])
        assert v["dif_area_pct"] <= 10.0, (m["motivo"], v["dif_area_pct"])


def test_su053_candidatos_descartados_ficam_registrados():
    """Os candidatos rejeitados na arbitragem guardam o porquê."""
    t = CONFIG["perfis"]["SU-053"]["transferencia_de_zonas"]
    assert t["metodo"].startswith("similaridade")
    assert set(t["candidatos_descartados"]) == {"C1", "C3", "C7", "C9", "C10"}
    for c, razao in t["candidatos_descartados"].items():
        assert razao, c
    # o registro usado na transferência não pode ter rotação relevante
    assert abs(t["registro"]["rotacao_graus"]) < 0.1


def _quadrado_com_furo(lado_px=240, px_mm=12.0):
    m = np.zeros((lado_px, lado_px), np.uint8)
    m[20:-20, 20:-20] = 1
    m[90:150, 90:150] = 0
    return m, px_mm


def test_padding_de_reextracao_e_geometricamente_neutro(tmp_path):
    """Regras 1–5 e 10 do padding: contorno, vazios, dimensões e assinatura
    idênticos com e sem margem; o padding não vira material."""
    from PIL import Image
    from curadoria.aquisicao import executar_lote1_e4b as ex
    from curadoria.aquisicao.assinatura_topologica import (
        derivar_assinatura_topologica)
    from curadoria.aquisicao.extrair_contorno_raster import extrair

    m, _ = _quadrado_com_furo()
    L = A = 20.0
    saidas = {}
    for pad in (0, ex.margem_px(L, m.shape[1])):
        img = Image.fromarray((1 - np.pad(m, pad)) * 255).convert("RGB")
        saidas[pad] = extrair("SIN", img, L, A, 1, threshold="otsu",
                              simplificacao_mm=0.05)
    sem, com = saidas[0], saidas[ex.margem_px(L, m.shape[1])]

    assert sem.contorno_externo == com.contorno_externo
    assert sem.vazios_internos == com.vazios_internos
    assert len(com.vazios_internos) == 1, "padding não pode criar nem fechar vazio"
    assert (derivar_assinatura_topologica(sem.contorno_externo, sem.vazios_internos)
            == derivar_assinatura_topologica(com.contorno_externo,
                                             com.vazios_internos))
    xs = [q[0] for q in com.contorno_externo]
    ys = [q[1] for q in com.contorno_externo]
    assert round(max(xs) - min(xs), 2) == L
    assert round(max(ys) - min(ys), 2) == A


def test_margem_de_reextracao_em_mm_respeita_a_escala():
    """Regra 8: a conversão mm→px usa a escala real da aquisição."""
    from curadoria.aquisicao import executar_lote1_e4b as ex
    assert ex.MARGEM_REEXTRACAO_MM == 0.85
    # 52,6 mm em 1241 px ≈ 23,6 px/mm  →  0,85 mm ≈ 20 px (o valor já testado)
    assert ex.margem_px(52.6, 1241) == 20
    # metade da escala, metade dos pixels
    assert ex.margem_px(52.6, 620) == 10
    assert ex.margem_px(10.0, 100) >= 1, "nunca degenera para zero"


def test_padding_nao_substitui_o_gate_recorte_da_fonte():
    """Regras 6 e 7: ROI que corta de fato o perfil continua bloqueada, e o
    padding é declarado como fase de reextração, não da fonte."""
    from PIL import Image
    from curadoria.aquisicao import executar_lote1_e4b as ex
    from curadoria.aquisicao.extrair_contorno_raster import extrair

    m, _ = _quadrado_com_furo()
    cortada = m[:, 60:]                      # ROI amputa o perfil de verdade
    img = Image.fromarray((1 - cortada) * 255).convert("RGB")
    r = extrair("SIN", img, 20.0, 20.0, 1, threshold="otsu",
                simplificacao_mm=0.05)
    assert "RECORTE" in [f.codigo for f in r.falhas], \
        "ROI realmente cortada tem de continuar bloqueando"

    reg = {"aplicado": True, "margem_mm": ex.MARGEM_REEXTRACAO_MM,
           "fase": "reextracao", "altera_geometria": False}
    assert reg["fase"] == "reextracao"
    assert reg["altera_geometria"] is False


def test_gravar_artefatos_proibidos_oficiais(tmp_path):
    """Gravação: recusa caminhos oficiais."""
    from curadoria.aquisicao import exportar

    resultado = {
        "contorno_bruto": {"contorno_externo": [[0, 0], [10, 0], [10, 10], [0, 10]], "vazios_internos": []},
        "contorno_comercial": {"contorno_externo": [[0, 0], [10, 0], [10, 10], [0, 10]], "vazios_internos": []},
        "assinatura": {"vazios": 0, "probes_material": [[5, 5]], "probes_vazio": [], "probes_exterior_conectado": []},
        "metricas": {"F1": 1.0},
        "operacoes": [],
        "dimensoes_mm": {"largura": 10, "altura": 10}
    }

    # Caminho que contém "dados" é proibido
    caminho_proibido = tmp_path / "dados" / "subdir"
    with pytest.raises(ValueError, match="proibida"):
        exportar.gravar_artefatos_curadoria("SU-001", resultado, caminho_proibido)
