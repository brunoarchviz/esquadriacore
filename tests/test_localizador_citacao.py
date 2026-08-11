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

from composicao.modelos import (EstadoConhecimento, FonteEvidencia,
                                ReceitaErro)
from composicao.proveniencia import (VERSAO_MANIFESTO, VERSAO_MINIMA_LOCALIZADOR,
                                     VERSOES_SUPORTADAS,
                                     AfirmacaoDeProveniencia, CitacaoDeFonte,
                                     ConflitoRegistrado, LocalizadorDeFonte,
                                     ManifestoProveniencia, PapelDaFonte,
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
    """Round-trip SEM reconstrução manual — a versão anterior deste teste
    reinjetava `fontes_no_repositorio` e por isso não via o P1 #1."""
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA",
                        "localizador": {"pagina_documento": PAGINA_DOCUMENTO,
                                        "pagina_pdf": PAGINA_PDF,
                                        "secao": SECAO}})
    ida = manifesto_de_dict(dados)
    serializado = ida.para_dict()
    loc = serializado["afirmacoes"][0]["citacoes"][0]["localizador"]
    assert loc == {"pagina_documento": PAGINA_DOCUMENTO,
                   "pagina_pdf": PAGINA_PDF, "secao": SECAO}

    volta = manifesto_de_dict(serializado)      # nada é recolocado à mão

    assert len(volta.fontes) == len(ida.fontes)
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
    localizada e chega vazia do outro lado.

    A recusa vem do ponto central (`ManifestoProveniencia`), não mais do leitor
    de YAML — ver P1 #2."""
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA",
                        "localizador": {"pagina_documento": PAGINA_DOCUMENTO}},
                       versao=1)
    with pytest.raises(ReceitaErro, match="localizador exige versão"):
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

# ---------------------------------------------------------------------------
# P1 #1 · round-trip do manifesto preserva as fontes
#
# `para_dict` emite a lista achatada sob `fontes`; o leitor só conhecia
# `artefatos` e `fontes_no_repositorio`. 114 fontes viravam 0 sem erro nenhum.
# ---------------------------------------------------------------------------

def test_p1_regressao_round_trip_nao_perde_fontes():
    """O bug em uma linha: nenhuma fonte pode desaparecer na volta.

    Compara antes/depois em vez de fixar o número — o manifesto real cresce, e
    um teste preso a 114 passaria a falhar por motivo errado."""
    ida = carregar_manifesto(MANIFESTO_SUPREMA)
    assert ida.fontes, "fixture sem fontes não testa perda de fontes"

    volta = manifesto_de_dict(ida.para_dict())

    assert len(volta.fontes) == len(ida.fontes)
    assert volta.fontes != ()


def test_p1_round_trip_preserva_ids_hash_e_tamanho():
    ida = carregar_manifesto(MANIFESTO_SUPREMA)
    volta = manifesto_de_dict(ida.para_dict())

    def assinatura(m):
        return sorted((f.id_fonte, f.sha256, f.tamanho_bytes, f.tipo,
                       f.forma_referencia, f.raiz_logica, f.abrangencia)
                      for f in m.fontes)

    assert assinatura(volta) == assinatura(ida)


def test_p1_round_trip_preserva_artefatos_externos_e_bytes():
    """Acervo externo só se reconstrói com `raiz_logica` — que a chave
    `fontes_no_repositorio` não lê. É o que obriga a chave canônica própria."""
    ida = carregar_manifesto(MANIFESTO_SUPREMA)
    volta = manifesto_de_dict(ida.para_dict())
    assert len(volta.artefatos_externos) == len(ida.artefatos_externos)
    assert volta.total_de_bytes == ida.total_de_bytes
    assert all(f.raiz_logica for f in volta.artefatos_externos)


def test_p1_round_trip_mantem_citacoes_resolvendo():
    """Fonte perdida deixaria toda citação órfã — e o manifesto reprovaria."""
    ida = carregar_manifesto(MANIFESTO_SUPREMA)
    volta = manifesto_de_dict(ida.para_dict())
    assert validar_manifesto(volta).ok, validar_manifesto(volta).descrever()
    indice = volta.indice_de_fontes()
    assert all(c.id_fonte in indice
               for a in volta.afirmacoes for c in a.citacoes)


def test_p1_round_trip_e_idempotente():
    ida = carregar_manifesto(MANIFESTO_SUPREMA)
    uma = manifesto_de_dict(ida.para_dict())
    duas = manifesto_de_dict(uma.para_dict())
    assert uma.para_dict() == duas.para_dict()


def test_p1_misturar_forma_canonica_e_autoral_reprova():
    """Somar as duas listas duplicaria fontes — recusa explícita, não escolha."""
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA"})
    dados["fontes"] = [{"id_fonte": "FONTE-B", "tipo": "catalogo",
                        "referencia": "b.pdf", "descricao": "x",
                        "estado": "PENDENTE"}]
    with pytest.raises(ReceitaErro, match="duas representações"):
        manifesto_de_dict(dados)


def test_p1_fontes_canonicas_sozinhas_sao_aceitas():
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA"})
    dados["fontes"] = dados.pop("fontes_no_repositorio")
    man = manifesto_de_dict(dados)
    assert [f.id_fonte for f in man.fontes] == ["FONTE-A"]


# ---------------------------------------------------------------------------
# P1 #2 · a invariante de versão vale por TODAS as portas de entrada
# ---------------------------------------------------------------------------

def _manifesto_objeto(versao: int, com_localizador: bool):
    """Constrói o manifesto direto em objetos, sem passar por YAML/dict."""
    fonte = FonteEvidencia(
        id_fonte="FONTE-A", tipo="catalogo", referencia="catalogo.pdf",
        descricao="x", estado=EstadoConhecimento.CONFIRMADO_CATALOGO)
    citacao = CitacaoDeFonte(
        "FONTE-A", PapelDaFonte.DIRETA,
        localizador=(LocalizadorDeFonte(pagina_pdf=PAGINA_PDF)
                     if com_localizador else None))
    return ManifestoProveniencia(
        conjunto="X", raiz_logica="X", versao=versao, fontes=(fonte,),
        afirmacoes=(AfirmacaoDeProveniencia(
            identificador="A01", texto="t",
            estado=EstadoConhecimento.CONFIRMADO_CATALOGO,
            citacoes=(citacao,)),))


def test_p2_v1_por_objeto_com_localizador_nao_pode_existir():
    """A porta dos fundos do P1 #2: sem esta trava, `para_dict` emitiria um
    documento v1 com localizador dentro."""
    with pytest.raises(ReceitaErro, match="localizador exige versão"):
        _manifesto_objeto(versao=1, com_localizador=True)


def test_p2_v1_por_objeto_sem_localizador_continua_valido():
    man = _manifesto_objeto(versao=1, com_localizador=False)
    assert man.versao == 1
    assert validar_manifesto(man).ok


def test_p2_v2_por_objeto_com_localizador_e_aceito():
    man = _manifesto_objeto(versao=VERSAO_MANIFESTO, com_localizador=True)
    assert man.afirmacoes[0].citacoes[0].localizador.pagina_pdf == PAGINA_PDF
    assert validar_manifesto(man).ok


def test_p2_v2_por_objeto_sem_localizador_e_aceito():
    assert validar_manifesto(
        _manifesto_objeto(versao=VERSAO_MANIFESTO, com_localizador=False)).ok


def test_p2_nenhuma_serializacao_emite_v1_com_localizador():
    """A prova final da invariante: não existe caminho público que produza o
    documento proibido, porque o objeto proibido não chega a ser construído."""
    with pytest.raises(ReceitaErro):
        _manifesto_objeto(versao=1, com_localizador=True).para_dict()


def test_p2_conflito_por_objeto_tambem_respeita_a_versao():
    """A invariante varre conflitos, não só afirmações."""
    fonte = FonteEvidencia(id_fonte="FONTE-A", tipo="catalogo",
                           referencia="c.pdf", descricao="x",
                           estado=EstadoConhecimento.PENDENTE)
    with pytest.raises(ReceitaErro, match="localizador exige versão"):
        ManifestoProveniencia(
            conjunto="X", raiz_logica="X", versao=1, fontes=(fonte,),
            conflitos=(ConflitoRegistrado(
                identificador="K1", descricao="d",
                citacoes=(CitacaoDeFonte(
                    "FONTE-A", PapelDaFonte.CONFLITANTE,
                    localizador=LocalizadorDeFonte(pagina_pdf=PAGINA_PDF)),)),))


def test_p2_v1_via_dict_com_localizador_continua_rejeitado():
    """A porta do YAML permanece fechada depois de a regra migrar de lugar."""
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA",
                        "localizador": {"pagina_pdf": PAGINA_PDF}}, versao=1)
    with pytest.raises(ReceitaErro, match="localizador exige versão"):
        manifesto_de_dict(dados)


# ---------------------------------------------------------------------------
# P2 · `pagina_documento` é identificador editorial, não número
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rotulo", [117, "iv", "A-12", "117a", "xiv", "S-3"])
def test_rotulo_editorial_sobrevive_round_trip_com_o_tipo(rotulo):
    """`iv` continua `"iv"`: traduzir para 4 inventaria uma numeração que o
    documento não usa."""
    original = CitacaoDeFonte(
        "FONTE-A", PapelDaFonte.DIRETA,
        localizador=LocalizadorDeFonte(pagina_documento=rotulo))
    refeita = CitacaoDeFonte(**original.para_dict())
    assert refeita.localizador.pagina_documento == rotulo
    assert type(refeita.localizador.pagina_documento) is type(rotulo)


@pytest.mark.parametrize("rotulo", ["", "   "])
def test_rotulo_editorial_vazio_rejeitado(rotulo):
    with pytest.raises(ReceitaErro, match="rótulo vazio"):
        LocalizadorDeFonte(pagina_documento=rotulo)


@pytest.mark.parametrize("valor", [True, False])
def test_rotulo_editorial_recusa_bool(valor):
    with pytest.raises(ReceitaErro, match="[Bb]ooleano"):
        LocalizadorDeFonte(pagina_documento=valor)


def test_rotulo_editorial_numerico_ainda_exige_positivo():
    with pytest.raises(ReceitaErro, match=">= 1"):
        LocalizadorDeFonte(pagina_documento=0)


def test_rotulo_editorial_e_normalizado():
    assert LocalizadorDeFonte(pagina_documento="  A-12 ").pagina_documento \
        == "A-12"


def test_rotulo_editorial_recusa_tipo_impossivel():
    with pytest.raises(ReceitaErro, match="rótulo editorial"):
        LocalizadorDeFonte(pagina_documento=117.5)


def test_pagina_pdf_continua_somente_inteira():
    """Posição no arquivo é contagem: rótulo editorial não serve aqui."""
    with pytest.raises(ReceitaErro, match="pagina_pdf"):
        LocalizadorDeFonte(pagina_pdf="iv")


def test_rotulo_editorial_e_pagina_pdf_convivem():
    loc = LocalizadorDeFonte(pagina_documento="iv", pagina_pdf=3)
    assert loc.pagina_documento == "iv"
    assert loc.pagina_pdf == 3


# ---------------------------------------------------------------------------
# Limitações preservadas de propósito — NÃO resolvidas nesta branch
# ---------------------------------------------------------------------------

def test_limitacao_pagina_pdf_nao_e_cruzada_com_o_tipo_da_fonte():
    """P2 CONHECIDO E ACEITO: o contrato valida que `pagina_pdf` é inteiro
    positivo, não que a fonte citada seja realmente um PDF paginado. Não há
    metadado de mídia no contrato para distinguir isso sem heurística."""
    dados = _manifesto({"id_fonte": "FONTE-A", "papel": "DIRETA",
                        "localizador": {"pagina_pdf": PAGINA_PDF}})
    dados["fontes_no_repositorio"][0]["tipo"] = "foto"
    dados["afirmacoes"][0]["estado"] = "PENDENTE"
    dados["fontes_no_repositorio"][0]["estado"] = "PENDENTE"
    man = manifesto_de_dict(dados)
    assert man.afirmacoes[0].citacoes[0].localizador.pagina_pdf == PAGINA_PDF


def test_limitacao_cross_manifest_continua_valendo():
    """LIMITAÇÃO CROSS-MANIFEST: fonte e `derivada_de` resolvem apenas dentro
    do PRÓPRIO manifesto. O localizador não criou ponte entre manifestos."""
    dados = _manifesto({"id_fonte": "FONTE-DE-OUTRO", "papel": "DIRETA",
                        "localizador": {"pagina_pdf": PAGINA_PDF}})
    dados["afirmacoes"][0]["derivada_de"] = ["B99"]
    r = validar_manifesto(manifesto_de_dict(dados))
    assert not r.ok
    regras = " ".join(f["regra"] for f in r.falhas)
    assert "cita fonte inexistente" in regras
    assert "deriva de afirmação inexistente" in regras


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
