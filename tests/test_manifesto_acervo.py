"""Infraestrutura mínima do MANIFESTO_ACERVO.yaml (E.4H, pós-acervo).

Cobre o que a rodada entrega: schema do item (arquivo|colecao), leitor de
YAML que recusa item estruturalmente malformado assim que ele nasce, e o
validador leve que só enxerga o conjunto (id duplicado, referência para item
inexistente, drive_file_id ausente quando o item se declara presente no
Drive). Cobre também que o MANIFESTO_ACERVO.yaml real, semeado nesta rodada,
valida sem problemas.

O que NÃO cobre, porque não existe ainda: verificação de bytes reais contra o
Drive (isso exige rclone montado, é outra rodada, do mesmo jeito que
`proveniencia.py` separa validação estrutural de verificação física)."""
from pathlib import Path

import pytest

from acervo.manifesto import (Granularidade, ItemAcervo, LeituraBootstrap,
                              ManifestoAcervo, ManifestoAcervoErro,
                              StatusEpistemologico, carregar_manifesto,
                              manifesto_de_dict, validar_manifesto)

RAIZ = Path(__file__).resolve().parent.parent
MANIFESTO_REAL = RAIZ / "MANIFESTO_ACERVO.yaml"


def _item_minimo(**overrides) -> dict:
    base = dict(
        id="ACV-TESTE-ITEM", nome="Item de teste", granularidade="arquivo",
        tipo="catalogo", presente_no_drive=False,
        leitura_bootstrap="sob_demanda", status_epistemologico="VIGENTE",
        resumo_uma_linha="Item usado só nos testes.")
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Construção do item — malformado é recusado ao nascer
# ---------------------------------------------------------------------------

def test_item_minimo_valido_constroi():
    item = ItemAcervo(**_item_minimo())
    assert item.granularidade is Granularidade.ARQUIVO
    assert item.leitura_bootstrap is LeituraBootstrap.SOB_DEMANDA
    assert item.status_epistemologico is StatusEpistemologico.VIGENTE
    assert item.tags == ()


def test_item_sem_id_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(id=""))


def test_item_com_id_fora_do_formato_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(id="nao-e-formato-acv"))


def test_item_com_granularidade_desconhecida_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(granularidade="pasta"))


def test_item_com_leitura_bootstrap_desconhecida_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(leitura_bootstrap="as_vezes"))


def test_item_com_status_epistemologico_desconhecido_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(status_epistemologico="TALVEZ"))


def test_item_sem_resumo_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(resumo_uma_linha=""))


def test_item_com_sha256_mal_formado_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(sha256="nao-e-um-hash"))


def test_item_com_sha256_valido_aceita():
    item = ItemAcervo(**_item_minimo(sha256="a" * 64))
    assert item.sha256 == "a" * 64


def test_item_com_tamanho_bytes_negativo_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(tamanho_bytes=-1))


def test_item_com_presente_no_drive_nao_booleano_reprova():
    with pytest.raises(ManifestoAcervoErro):
        ItemAcervo(**_item_minimo(presente_no_drive="sim"))


# ---------------------------------------------------------------------------
# Leitura do dict cru — mesmas recusas, pela porta de manifesto_de_dict
# ---------------------------------------------------------------------------

def test_manifesto_de_dict_versao_nao_suportada_reprova():
    with pytest.raises(ManifestoAcervoErro):
        manifesto_de_dict({"versao_manifesto": 99, "itens": []})


def test_manifesto_de_dict_raiz_nao_mapeamento_reprova():
    with pytest.raises(ManifestoAcervoErro):
        manifesto_de_dict([])


def test_manifesto_de_dict_constroi_itens_e_varredura():
    m = manifesto_de_dict({
        "versao_manifesto": 1,
        "ultima_varredura": {
            "data": "2026-08-15",
            "locais_cobertos": ["handoff"],
            "pontos_cegos_conhecidos": ["nada varrido ainda"],
        },
        "itens": [_item_minimo()],
    })
    assert isinstance(m, ManifestoAcervo)
    assert len(m.itens) == 1
    assert m.ultima_varredura.data == "2026-08-15"
    assert m.item("ACV-TESTE-ITEM") is not None
    assert m.item("ACV-INEXISTENTE") is None


# ---------------------------------------------------------------------------
# Validador — checagens que só existem em relação ao conjunto
# ---------------------------------------------------------------------------

def test_validar_manifesto_vazio_aprova():
    assert validar_manifesto(ManifestoAcervo()) == ()


def test_validar_manifesto_id_duplicado_reprova():
    m = manifesto_de_dict({"versao_manifesto": 1, "itens": [
        _item_minimo(), _item_minimo()]})
    problemas = validar_manifesto(m)
    assert any("duplicado" in p.regra for p in problemas)


def test_validar_manifesto_presente_no_drive_sem_localizador_reprova():
    m = manifesto_de_dict({"versao_manifesto": 1, "itens": [
        _item_minimo(presente_no_drive=True, drive_file_id=None)]})
    problemas = validar_manifesto(m)
    assert any("drive_file_id" in p.regra for p in problemas)


def test_validar_manifesto_presente_no_drive_com_localizador_aprova():
    m = manifesto_de_dict({"versao_manifesto": 1, "itens": [
        _item_minimo(presente_no_drive=True, drive_file_id="1AbC")]})
    assert validar_manifesto(m) == ()


def test_validar_manifesto_substitui_referencia_inexistente_reprova():
    m = manifesto_de_dict({"versao_manifesto": 1, "itens": [
        _item_minimo(substitui="ACV-FANTASMA-X")]})
    problemas = validar_manifesto(m)
    assert any("substitui" in p.regra for p in problemas)


def test_validar_manifesto_substitui_a_si_mesmo_reprova():
    m = manifesto_de_dict({"versao_manifesto": 1, "itens": [
        _item_minimo(id="ACV-TESTE-A", substitui="ACV-TESTE-A")]})
    problemas = validar_manifesto(m)
    assert any("aponta para si mesmo" in p.regra for p in problemas)


def test_validar_manifesto_substitui_referencia_existente_aprova():
    m = manifesto_de_dict({"versao_manifesto": 1, "itens": [
        _item_minimo(id="ACV-TESTE-A"),
        _item_minimo(id="ACV-TESTE-B", substitui="ACV-TESTE-A"),
    ]})
    assert validar_manifesto(m) == ()


def test_carregar_manifesto_inexistente_reprova(tmp_path):
    with pytest.raises(ManifestoAcervoErro):
        carregar_manifesto(tmp_path / "nao-existe.yaml")


# ---------------------------------------------------------------------------
# O MANIFESTO_ACERVO.yaml real desta rodada
# ---------------------------------------------------------------------------

def test_manifesto_real_existe():
    assert MANIFESTO_REAL.exists()


def test_manifesto_real_carrega_e_valida_sem_problemas():
    manifesto = carregar_manifesto(MANIFESTO_REAL)
    problemas = validar_manifesto(manifesto)
    assert problemas == (), "\n".join(str(p) for p in problemas)


def test_manifesto_real_tem_os_itens_semeados_pelo_handoff():
    manifesto = carregar_manifesto(MANIFESTO_REAL)
    esperados = {
        "ACV-COLECAO-SUPREMA-CORRER-2F",
        "ACV-ARQUIVO-ALCOA-GOLD3",
        "ACV-ARQUIVO-ALCOA-LINHA-SUPREMA",
        "ACV-ARQUIVO-ALCOA-LINHA-25",
        "ACV-ARQUIVO-ALCOA-LINHA-30",
        "ACV-ARQUIVO-CENTENARIO",
        "ACV-ARQUIVO-VIDRACEIRO-RICO-SUPREMA",
        "ACV-ARQUIVO-VIDRACEIRO-RICO-GOLD",
        "ACV-ARQUIVO-PACRE-SUPREMA-PERFIS",
        "ACV-ARQUIVO-PACRE-GOLD-FINAL",
        "ACV-COLECAO-ESPELHO-VISUAL-CONTORNOS",
        "ACV-COLECAO-ESPELHO-VISUAL-COMPARATIVOS",
    }
    ids_reais = {i.id for i in manifesto.itens}
    assert esperados <= ids_reais


def test_manifesto_real_nao_afirma_presenca_no_drive_sem_localizador():
    """Nesta rodada nenhum drive_file_id foi coletado — ver comentário no
    topo do YAML. Este teste trava essa convenção: se alguém marcar
    presente_no_drive=true sem preencher drive_file_id, o validador (não só
    este teste) já reprova, mas aqui documentamos a intenção da rodada."""
    manifesto = carregar_manifesto(MANIFESTO_REAL)
    sem_localizador = [i.id for i in manifesto.itens if i.presente_no_drive
                       and not i.drive_file_id]
    assert sem_localizador == []


def test_manifesto_real_linha_25_e_30_tem_sha256_valido():
    manifesto = carregar_manifesto(MANIFESTO_REAL)
    l25 = manifesto.item("ACV-ARQUIVO-ALCOA-LINHA-25")
    l30 = manifesto.item("ACV-ARQUIVO-ALCOA-LINHA-30")
    assert l25.sha256 == (
        "e94dbb2d0d354a3a86b3df8c6081cb7483ed11843dac532fd7227264ec2a67bd")
    assert l30.sha256 == (
        "a0c9bd3b1db18b58a5e76d97bcd00a1809b3a507cde84bdae9eaff39120ef4f4")
