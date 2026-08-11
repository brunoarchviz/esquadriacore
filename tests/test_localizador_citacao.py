"""Localizador estruturado da citação — E.4H, contrato de proveniência.

Uma citação diz QUEM sustenta a afirmação; o localizador diz ONDE conferir.
Sem ele, citar um catálogo de 135 páginas é mandar reler o documento inteiro.

O que estes testes protegem, em ordem de importância:

```text
versionamento     manifesto v1 não pode carregar localizador — o leitor da v1
                  o descartaria em silêncio, e a citação pareceria localizada
round-trip        objeto -> dict -> objeto preserva página e seção com o tipo
                  original; um 117 que volta como "117" já não é página
autoridade        localizador NÃO muda papel, estado nem gate — ele descreve,
                  não sustenta
```

Os casos numéricos são adversariais de propósito: `True` é `int` em Python, e
sem recusa explícita `pagina_pdf: true` viraria a página 1 sem que ninguém
visse.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from composicao.modelos import EstadoConhecimento, ReceitaErro
from composicao.proveniencia import (VERSAO_MANIFESTO, VERSAO_MINIMA_LOCALIZADOR,
                                     VERSOES_SUPORTADAS, CitacaoDeFonte,
                                     LocalizadorDeFonte, PapelDaFonte,
                                     carregar_manifesto, localizador_de_dict,
                                     manifesto_de_dict, validar_manifesto)

RAIZ = Path(__file__).resolve().parent.parent
MANIFESTO_SUPREMA = RAIZ / "composicao/insumos/proveniencia_suprema_2f.yaml"

# Localização real do SUP JCR 200 no catálogo Alcoa: página impressa 117,
# página 113 do PDF. É o caso que motivou o campo e o que prova que as duas
# páginas não são a mesma grandeza.
PAGINA_DOCUMENTO = 117
PAGINA_PDF = 113
SECAO = "SUP JCR 200"


def _manifesto(citacao: dict, versao: int = VERSAO_MANIFESTO) -> dict:
    """Manifesto mínimo válido com UMA citação — o resto é cenário."""
    return {
        "versao_manifesto": versao, "conjunto": "X", "raiz_logica": "X",
        "fontes_no_repositorio": [
            {"id_fonte": "FONTE-A", "tipo": "catalogo",
             "referencia": "catalogo.pdf", "descricao": "x",
             "estado": "CONFIRMADO_CATALOGO"}],
        "afirmacoes": [
            {"identificador": "A01", "texto": "t",
             "estado": "CONFIRMADO_CATALOGO", "citacoes": [citacao]}],
    }


def _citacao_do(dados: dict) -> CitacaoDeFonte:
    return manifesto_de_dict(dados).afirmacoes[0].citacoes[0]


# ---------------------------------------------------------------------------
# 1–5 · o campo é opcional e cada combinação sobrevive
# ---------------------------------------------------------------------------

def test_01_citacao_sem_localizador_continua_valida():
    """O campo é aditivo: toda citação escrita antes dele continua legítima."""
    c = _citacao_do(_manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA"}))
    assert c.localizador is None
    assert c.para_dict()["localizador"] is None


def test_02_localizador_completo_preservado():
    c = _citacao_do(_manifesto({
        "id_fonte": "FONTE-A", "papel": "DIRETA",
        "localizador": {"pagina_documento": PAGINA_DOCUMENTO,
                        "pagina_pdf": PAGINA_PDF, "secao": SECAO}}))
    assert c.localizador.pagina_documento == PAGINA_DOCUMENTO
    assert c.localizador.pagina_pdf == PAGINA_PDF
    assert c.localizador.secao == SECAO


def test_03_somente_pagina_documento():
    c = _citacao_do(_manifesto({
        "id_fonte": "FONTE-A", "papel": "DIRETA",
        "localizador": {"pagina_documento": PAGINA_DOCUMENTO}}))
    assert c.localizador.pagina_documento == PAGINA_DOCUMENTO
    assert c.localizador.pagina_pdf is None
    assert c.localizador.secao is None


def test_04_somente_pagina_pdf():
    """PDF sem paginação impressa é caso real — não se exige a outra página."""
    c = _citacao_do(_manifesto({
        "id_fonte": "FONTE-A", "papel": "DIRETA",
        "localizador": {"pagina_pdf": PAGINA_PDF}}))
    assert c.localizador.pagina_pdf == PAGINA_PDF
    assert c.localizador.pagina_documento is None


def test_05_somente_secao():
    """Norma citada por seção, sem página útil, continua localizável."""
    c = _citacao_do(_manifesto({
        "id_fonte": "FONTE-A", "papel": "DIRETA",
        "localizador": {"secao": SECAO}}))
    assert c.localizador.secao == SECAO
    assert c.localizador.pagina_documento is None


def test_05b_as_duas_paginas_sao_grandezas_distintas():
    """117 impressa e 113 no PDF: colapsá-las mandaria conferir a página errada."""
    loc = LocalizadorDeFonte(pagina_documento=PAGINA_DOCUMENTO,
                             pagina_pdf=PAGINA_PDF)
    assert loc.pagina_documento != loc.pagina_pdf


# ---------------------------------------------------------------------------
# 6–9 · validação numérica e textual
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("campo", ["pagina_documento", "pagina_pdf"])
def test_06_pagina_zero_rejeitada(campo):
    """Base 1: não existe página 0 num documento, só num índice de programador."""
    with pytest.raises(ReceitaErro, match=">= 1"):
        LocalizadorDeFonte(**{campo: 0})


@pytest.mark.parametrize("campo", ["pagina_documento", "pagina_pdf"])
def test_07_pagina_negativa_rejeitada(campo):
    with pytest.raises(ReceitaErro, match=">= 1"):
        LocalizadorDeFonte(**{campo: -3})


@pytest.mark.parametrize("campo", ["pagina_documento", "pagina_pdf"])
@pytest.mark.parametrize("valor", [True, False])
def test_08_bool_rejeitado_como_pagina(campo, valor):
    """`isinstance(True, int)` é True: sem recusa, `true` viraria página 1."""
    with pytest.raises(ReceitaErro, match="[Bb]ooleano"):
        LocalizadorDeFonte(**{campo: valor})


@pytest.mark.parametrize("valor", ["", "   "])
def test_09_secao_vazia_rejeitada(valor):
    with pytest.raises(ReceitaErro, match="seção vazia"):
        LocalizadorDeFonte(secao=valor)


@pytest.mark.parametrize("valor", ["117", 117.5, [117]])
def test_09b_pagina_nao_inteira_rejeitada(valor):
    """Página é contagem. "117" e 117.5 não são localização conferível."""
    with pytest.raises(ReceitaErro, match="inteiro"):
        LocalizadorDeFonte(pagina_pdf=valor)


def test_09c_localizador_inteiramente_vazio_rejeitado():
    """Localizador que não localiza nada é ruído com aparência de dado."""
    with pytest.raises(ReceitaErro, match="não localiza nada"):
        LocalizadorDeFonte()


def test_09d_secao_e_normalizada_sem_espacos_de_borda():
    assert LocalizadorDeFonte(secao="  SUP JCR 200 ").secao == SECAO


def test_09e_chave_desconhecida_no_localizador_reprova():
    """Erro de digitação aqui produziria citação que parece localizada.

    Severidade restrita a este campo — a política global do manifesto, que
    ignora chave desconhecida, NÃO foi alterada nesta rodada."""
    with pytest.raises(ReceitaErro, match="campo desconhecido no localizador"):
        localizador_de_dict({"pagina_documeto": 117}, "alvo")


# ---------------------------------------------------------------------------
# 10 · imutabilidade
# ---------------------------------------------------------------------------

def test_10_localizador_e_imutavel():
    loc = LocalizadorDeFonte(pagina_documento=PAGINA_DOCUMENTO)
    with pytest.raises(Exception):
        loc.pagina_documento = 999
    assert loc.pagina_documento == PAGINA_DOCUMENTO


def test_10b_mutar_o_dict_de_origem_nao_altera_o_objeto():
    """Os campos são escalares copiados na construção — nada compartilhado."""
    bruto = {"pagina_documento": PAGINA_DOCUMENTO, "secao": SECAO}
    loc = localizador_de_dict(bruto, "alvo")
    bruto["pagina_documento"] = 999
    bruto["secao"] = "OUTRA"
    assert loc.pagina_documento == PAGINA_DOCUMENTO
    assert loc.secao == SECAO


def test_10c_citacao_com_localizador_continua_frozen():
    c = CitacaoDeFonte("FONTE-A", PapelDaFonte.DIRETA,
                       localizador=LocalizadorDeFonte(pagina_pdf=PAGINA_PDF))
    with pytest.raises(Exception):
        c.localizador = None


# ---------------------------------------------------------------------------
# 11 · o manifesto existente continua carregando
# ---------------------------------------------------------------------------

def test_11_manifesto_suprema_real_continua_carregando():
    """Zero migração: o manifesto em produção é v1 e permanece válido."""
    man = carregar_manifesto(MANIFESTO_SUPREMA)
    assert man.versao == 1
    assert validar_manifesto(man).ok
    assert all(c.localizador is None
               for a in man.afirmacoes for c in a.citacoes)


def test_11b_versao_1_continua_suportada():
    assert 1 in VERSOES_SUPORTADAS
    assert VERSAO_MANIFESTO in VERSOES_SUPORTADAS


# ---------------------------------------------------------------------------
# 12–13 · o localizador não altera autoridade nem papel
# ---------------------------------------------------------------------------

def test_12_localizador_nao_muda_compatibilidade_fonte_afirmacao():
    """Descrever onde conferir não é sustentar: a validação é idêntica."""
    sem = manifesto_de_dict(_manifesto({"id_fonte": "FONTE-A",
                                        "papel": "DIRETA"}))
    com = manifesto_de_dict(_manifesto({
        "id_fonte": "FONTE-A", "papel": "DIRETA",
        "localizador": {"pagina_documento": PAGINA_DOCUMENTO}}))
    assert validar_manifesto(sem).ok == validar_manifesto(com).ok
    assert sem.afirmacoes[0].estado == com.afirmacoes[0].estado


def test_12b_localizador_nao_salva_afirmacao_sem_sustentacao():
    """Uma citação CORROBORATIVA com página continua não confirmando nada."""
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "CORROBORATIVA",
                        "localizador": {"pagina_documento": PAGINA_DOCUMENTO,
                                        "secao": SECAO}})
    r = validar_manifesto(manifesto_de_dict(dados))
    assert not r.ok
    assert any("sem fonte que a sustente" in f["regra"] for f in r.falhas)


@pytest.mark.parametrize("papel", sorted(p.value for p in PapelDaFonte))
def test_13_localizador_nao_muda_o_papel(papel):
    com = CitacaoDeFonte("FONTE-A", PapelDaFonte(papel),
                         localizador=LocalizadorDeFonte(pagina_pdf=PAGINA_PDF))
    sem = CitacaoDeFonte("FONTE-A", PapelDaFonte(papel))
    assert com.papel is sem.papel
    assert com.sustenta == sem.sustenta


# ---------------------------------------------------------------------------
# 14 · round-trip
# ---------------------------------------------------------------------------

def test_14_round_trip_preserva_valores_e_tipos():
    original = CitacaoDeFonte(
        "FONTE-A", PapelDaFonte.DIRETA, observacao="nota",
        localizador=LocalizadorDeFonte(pagina_documento=PAGINA_DOCUMENTO,
                                       pagina_pdf=PAGINA_PDF, secao=SECAO))
    refeita = CitacaoDeFonte(**original.para_dict())
    assert refeita == original
    assert refeita.localizador == original.localizador
    # Um 117 que volta como "117" deixou de ser página.
    assert isinstance(refeita.localizador.pagina_documento, int)
    assert isinstance(refeita.localizador.pagina_pdf, int)


def test_14b_round_trip_pelo_manifesto_inteiro():
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA",
                        "localizador": {"pagina_documento": PAGINA_DOCUMENTO,
                                        "pagina_pdf": PAGINA_PDF,
                                        "secao": SECAO}})
    ida = manifesto_de_dict(dados)
    serializado = ida.para_dict()
    loc = serializado["afirmacoes"][0]["citacoes"][0]["localizador"]
    assert loc == {"pagina_documento": PAGINA_DOCUMENTO,
                   "pagina_pdf": PAGINA_PDF, "secao": SECAO}
    volta = manifesto_de_dict({**serializado,
                               "versao_manifesto": ida.versao,
                               "fontes_no_repositorio":
                                   dados["fontes_no_repositorio"]})
    assert volta.afirmacoes[0].citacoes[0].localizador == \
        ida.afirmacoes[0].citacoes[0].localizador


def test_14c_round_trip_de_citacao_sem_localizador():
    original = CitacaoDeFonte("FONTE-A", PapelDaFonte.CORROBORATIVA)
    assert CitacaoDeFonte(**original.para_dict()) == original


# ---------------------------------------------------------------------------
# Versionamento — o motivo pelo qual esta mudança é de contrato
# ---------------------------------------------------------------------------

def test_v01_localizador_sob_versao_1_reprova():
    """O núcleo da decisão de versão.

    Um leitor da v1 aceita este manifesto e devolve a citação SEM o
    localizador, sem erro. Deixar passar produziria uma citação que se diz
    localizada e chega vazia do outro lado."""
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA",
                        "localizador": {"pagina_documento": PAGINA_DOCUMENTO}},
                       versao=1)
    with pytest.raises(ReceitaErro, match="localizador exige versao_manifesto"):
        manifesto_de_dict(dados)


def test_v02_localizador_nulo_sob_versao_1_e_aceito():
    """`localizador: ~` não é declaração de localizador — é ausência."""
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA",
                        "localizador": None}, versao=1)
    assert manifesto_de_dict(dados).afirmacoes[0].citacoes[0].localizador is None


def test_v03_versao_minima_do_localizador_e_a_versao_corrente():
    assert VERSAO_MINIMA_LOCALIZADOR == VERSAO_MANIFESTO == 2


def test_v04_versao_desconhecida_continua_recusada():
    with pytest.raises(ReceitaErro, match="não suportada"):
        manifesto_de_dict({"versao_manifesto": 99, "conjunto": "X",
                           "raiz_logica": "X"})


# ---------------------------------------------------------------------------
# Conflitos citam com localizador pelo mesmo caminho
# ---------------------------------------------------------------------------

def test_conflito_tambem_aceita_localizador():
    """Divergência documental também precisa dizer em que página está."""
    dados = {
        "versao_manifesto": VERSAO_MANIFESTO, "conjunto": "X",
        "raiz_logica": "X",
        "fontes_no_repositorio": [
            {"id_fonte": "FONTE-A", "tipo": "catalogo",
             "referencia": "catalogo.pdf", "descricao": "x",
             "estado": "CONFIRMADO_CATALOGO"}],
        "conflitos": [
            {"identificador": "K1", "descricao": "d", "estado": "PENDENTE",
             "citacoes": [{"id_fonte": "FONTE-A", "papel": "CONFLITANTE",
                           "localizador": {"pagina_pdf": PAGINA_PDF}}]}],
    }
    man = manifesto_de_dict(dados)
    assert man.conflitos[0].citacoes[0].localizador.pagina_pdf == PAGINA_PDF
    assert man.conflitos[0].estado is EstadoConhecimento.PENDENTE
