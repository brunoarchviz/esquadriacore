"""Catálogo Alcoa Suprema — manifesto de proveniência autônomo (E.4H).

O catálogo é documentação PRIMÁRIA DO FABRICANTE em revisão histórica, e
entra no projeto como manifesto próprio, com raiz lógica própria. O que estes
testes protegem:

```text
autonomia      nenhuma citação e nenhuma derivação atravessa a fronteira do
               manifesto — o contrato resolve só dentro do documento
procedência    o catálogo afirma o que o FABRICANTE diz; nada de regra que
               dependa de medição de campo entra como afirmação dele
integridade    sha256 e tamanho conferidos contra os bytes reais quando o PDF
               está disponível; ausência do PDF nunca vira aprovação
isolamento     o acervo de campo (SUPREMA_CORRER_2F) não é tocado
```

O PDF não está no Git. Os testes que dependem dele pulam com motivo
explícito; os estruturais rodam em qualquer clone.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from composicao import validar
from composicao.modelos import (ABRANGENCIA_COMPARTILHADA,
                                ESTADOS_CONFIRMADOS, EstadoConhecimento,
                                FORMA_ACERVO_EXTERNO)
from composicao.proveniencia import (VERSAO_MINIMA_LOCALIZADOR,
                                     carregar_manifesto, validar_manifesto,
                                     verificar_acervo_do_manifesto)

RAIZ = Path(__file__).resolve().parent.parent
MANIFESTO_CATALOGO = RAIZ / "composicao/insumos/proveniencia_alcoa_suprema.yaml"
MANIFESTO_CAMPO = RAIZ / "composicao/insumos/proveniencia_suprema_2f.yaml"

RAIZ_LOGICA_CATALOGO = "ALCOA_LINHA_SUPREMA"
ID_FONTE_CATALOGO = "FONTE-ALCOA-LINHA-SUPREMA-PDF"

# Identidade do PDF, conferida contra o arquivo real nesta ingestão.
SHA256_CATALOGO = \
    "e64577df8d4ff33a7ec0d204f03a321136450507407e29f4e6c080e442d12deb"
TAMANHO_CATALOGO = 9_120_081

# Baseline do acervo de CAMPO, que esta ingestão não pode alterar.
ARTEFATOS_CAMPO = 112
BYTES_CAMPO = 22_401_782


@pytest.fixture(scope="module")
def catalogo():
    return carregar_manifesto(MANIFESTO_CATALOGO)


# ---------------------------------------------------------------------------
# 1–2 · carrega e valida com o contrato atual, sem o PDF presente
# ---------------------------------------------------------------------------

def test_manifesto_do_catalogo_valida(catalogo):
    r = validar_manifesto(catalogo)
    assert r.ok, r.descrever()


def test_validacao_estrutural_dispensa_o_pdf(catalogo):
    """`validar_manifesto` roda em qualquer clone: nenhum byte é aberto.

    É o que permite o CI validar o registro sem ter o catálogo — e é diferente
    de `verificar_acervo`, que exige os bytes e reprova sem eles."""
    assert not (RAIZ / "alcoa-linha-suprema.pdf").exists(), \
        "o PDF não deve estar no repositório"
    assert validar_manifesto(catalogo).ok


def test_identidade_do_catalogo_registrada(catalogo):
    fonte = catalogo.indice_de_fontes()[ID_FONTE_CATALOGO]
    assert fonte.sha256 == SHA256_CATALOGO
    assert fonte.tamanho_bytes == TAMANHO_CATALOGO
    assert fonte.tipo == "catalogo"
    assert fonte.forma_referencia == FORMA_ACERVO_EXTERNO
    assert fonte.raiz_logica == RAIZ_LOGICA_CATALOGO
    # Cobre a linha inteira, não um exemplar.
    assert fonte.abrangencia == ABRANGENCIA_COMPARTILHADA


def test_manifesto_e_v2_por_causa_do_localizador(catalogo):
    assert catalogo.versao >= VERSAO_MINIMA_LOCALIZADOR


# ---------------------------------------------------------------------------
# 3 · bytes reais — pula sem o PDF, mas ausência NUNCA vira aprovação
# ---------------------------------------------------------------------------

def test_bytes_reais_conferem_quando_o_catalogo_esta_montado(catalogo):
    raizes = validar.raizes_fisicas_do_ambiente()
    if RAIZ_LOGICA_CATALOGO not in raizes:
        pytest.skip(f"defina ESQUADRIACORE_ACERVO_{RAIZ_LOGICA_CATALOGO} "
                    f"para conferir os bytes reais do catálogo")
    r = verificar_acervo_do_manifesto(catalogo, raizes)
    assert r.ok, r.descrever()


def test_sem_raiz_fisica_a_verificacao_reprova(catalogo):
    """Não conferir é REPROVAÇÃO, não silêncio — o oposto de um falso positivo.

    Roda sempre, inclusive no CI sem o PDF: é justamente a garantia de que a
    ausência de evidência não é lida como evidência."""
    r = verificar_acervo_do_manifesto(catalogo, {})
    assert not r.ok
    assert any("raiz física" in f["regra"] for f in r.falhas)


def test_o_catalogo_e_verificavel_por_bytes(catalogo):
    """Contra a armadilha do `identificador_externo`: se a fonte não fosse
    artefato de acervo externo, `verificar-acervo` aprovaria sem abrir nada e
    o sha256 viraria decoração."""
    assert len(catalogo.artefatos_externos) == 1
    assert catalogo.total_de_bytes == TAMANHO_CATALOGO


# ---------------------------------------------------------------------------
# 4 · o invariante de raiz lógica
# ---------------------------------------------------------------------------

def test_artefato_em_outra_raiz_logica_e_rejeitado():
    """O invariante que torna o manifesto uma unidade autocontida: artefato de
    outra raiz não entra. É o que impede, por construção, "importar" a fonte
    do catálogo para dentro do manifesto de campo."""
    from composicao.proveniencia import manifesto_de_dict
    dados = {
        "versao_manifesto": 2, "conjunto": "X", "raiz_logica": "X",
        "fontes": [{"id_fonte": ID_FONTE_CATALOGO, "tipo": "catalogo",
                    "referencia": "alcoa-linha-suprema.pdf", "descricao": "x",
                    "estado": "CONFIRMADO_CATALOGO",
                    "forma_referencia": FORMA_ACERVO_EXTERNO,
                    "raiz_logica": RAIZ_LOGICA_CATALOGO,
                    "sha256": SHA256_CATALOGO,
                    "tamanho_bytes": TAMANHO_CATALOGO}]}
    r = validar_manifesto(manifesto_de_dict(dados))
    assert not r.ok
    assert any("outra raiz lógica" in f["regra"] for f in r.falhas)


# ---------------------------------------------------------------------------
# 5 · procedência das afirmações — o catálogo só afirma o que o fabricante diz
# ---------------------------------------------------------------------------

def test_nenhuma_afirmacao_usa_confirmado_caso_real(catalogo):
    """O catálogo não mediu janela nenhuma. `CONFIRMADO_CASO_REAL` aqui
    atribuiria ao fabricante uma observação de campo."""
    assert catalogo.afirmacoes
    for a in catalogo.afirmacoes:
        assert a.estado is not EstadoConhecimento.CONFIRMADO_CASO_REAL, \
            f"{a.identificador} declara caso real num manifesto de catálogo"


def test_afirmacoes_confirmadas_sao_de_catalogo(catalogo):
    for a in catalogo.afirmacoes:
        if a.estado in ESTADOS_CONFIRMADOS:
            assert a.estado is EstadoConhecimento.CONFIRMADO_CATALOGO, \
                f"{a.identificador}: {a.estado.value} não é estado de catálogo"


# Padrões que NÃO podem aparecer nos campos textuais de uma afirmação do
# catálogo. Cada família tem NOME próprio, não é só uma lista de regex solta:
# é o que permite provar cada padrão isoladamente (ver
# test_cada_familia_de_expressao_proibida_pega_seu_positivo abaixo) em vez de
# provar só que "algum padrão, algum dia" casou em alguma frase.
#
# Casam por TOKEN, não por substring: `H-50` é cota impressa na prancha e
# legítima, enquanto `H-55` seria a expressão de corte derivada. Uma primeira
# versão deste teste usava `in` e reprovava a cota real por causa do prefixo —
# a checagem precisa ser tão precisa quanto a distinção que ela protege.
#
# `(?:_v[ãa]o)?` entre a variável e o traço cobre a grafia com a variável
# nomeada (`L_vão-32`) e a grafia crua (`L-32`) com o MESMO padrão — é o
# mesmo número proibido, escrito de duas formas, e as duas precisam cair.
EXPRESSOES_DERIVADAS = {
    "L-32": r"\bL(?:_v[ãa]o)?\s*-\s*32\b(?!\d)",
    "H-5": r"\bH(?:_v[ãa]o)?\s*-\s*5\b(?!\d)",
    "H-55": r"\bH(?:_v[ãa]o)?\s*-\s*55\b(?!\d)",
    "L-132": r"\bL(?:_v[ãa]o)?\s*-\s*132\b(?!\d)",
    "vao": r"\bv[ãa]o\b",
    "quantizacao": r"quantiza",
    "floor": r"\bfloor\b",
    "trunc": r"\btrunc\b",
    "arredondamento": r"arredond",
    "caso_abc": r"\bCASO[_ ][ABC]\b",
    "vidro_934": r"\b934\b",
    "vidro_994": r"\b994\b",
    "baguete_1040": r"\b1040\b",
    "baguete_980": r"\b980\b",
}

# Campos textuais varridos. `texto` já era coberto; `observacao` da afirmação
# e da citação entram porque são prosa livre — o mesmo lugar onde uma
# interpretação proibida poderia ser deslocada para escapar do teste anterior,
# que olhava só `texto`. `secao` do localizador entra por completude: hoje só
# guarda rótulos como "Perfis" ou "SUP JCR 200", nenhum dos quais colide com
# os padrões acima, mas é texto livre e a auditoria pediu que fosse avaliado.
# `pagina_documento`/`pagina_pdf` ficam de fora: são identificador de página
# (inclusive podem ser um rótulo alfanumérico como "117a"), não narrativa —
# não é onde uma fórmula se esconderia, e variar o padrão acima contra um
# identificador de página tende a criar falso positivo, não proteção real.
def _campos_textuais(a) -> tuple[tuple[str, str], ...]:
    campos = [(f"{a.identificador}.texto", a.texto)]
    if a.observacao:
        campos.append((f"{a.identificador}.observacao", a.observacao))
    for i, c in enumerate(a.citacoes):
        if c.observacao:
            campos.append((f"{a.identificador}.citacoes[{i}].observacao",
                           c.observacao))
        if c.localizador and c.localizador.secao:
            campos.append((f"{a.identificador}.citacoes[{i}].localizador.secao",
                           c.localizador.secao))
    return tuple(campos)


@pytest.mark.parametrize("nome_padrao", sorted(EXPRESSOES_DERIVADAS))
def test_nenhuma_regra_derivada_entra_como_afirmacao_do_fabricante(catalogo,
                                                                   nome_padrao):
    """Expressão em função do VÃO combina desenho do fabricante com medição de
    campo: é conclusão do domínio, não declaração da Alcoa. O mesmo vale para
    quantização, medidas de caso real e arbitragens em aberto — em qualquer
    campo textual da afirmação, não só em `texto`."""
    import re
    padrao = EXPRESSOES_DERIVADAS[nome_padrao]
    for a in catalogo.afirmacoes:
        for alvo, valor in _campos_textuais(a):
            assert not re.search(padrao, valor, re.IGNORECASE), \
                f"{alvo} atribui ao fabricante algo derivado ({nome_padrao})"


# Um positivo e um negativo por família, provados INDIVIDUALMENTE: o teste
# anterior só provava que a UNIÃO dos padrões casava em alguma frase — uma
# frase com "L-32" e "vão" juntos continuaria passando mesmo com o padrão de
# L-32 quebrado, porque o de "vão" ainda casava por trás. Aqui cada família
# é testada sozinha, então a quebra de qualquer uma reprova só ela.
CASOS_POSITIVOS_POR_FAMILIA = [
    ("L-32", "corte L-32"),
    ("L-32", "corte L - 32"),
    ("L-32", "corte L_vão-32"),
    ("L-32", "corte L_vão - 32"),
    ("H-5", "corte H-5"),
    ("H-5", "corte H - 5"),
    ("H-5", "corte H_vão-5"),
    ("H-5", "corte H_vão - 5"),
    ("H-55", "corte H-55"),
    ("H-55", "corte H - 55"),
    ("H-55", "corte H_vão-55"),
    ("H-55", "corte H_vão - 55"),
    ("L-132", "(L-132)/2"),
    ("L-132", "(L_vão-132)/2"),
]

CASOS_NEGATIVOS_POR_FAMILIA = [
    ("H-5", "cota H-50"),
    ("H-5", "cota H - 50"),
    ("H-55", "cota H-134"),
    ("H-55", "cota H - 134"),
    ("L-32", "cota L-320"),
    ("L-132", "cota L-1320"),
]


@pytest.mark.parametrize("familia,texto", CASOS_POSITIVOS_POR_FAMILIA)
def test_cada_familia_de_expressao_proibida_pega_seu_positivo(familia, texto):
    import re
    assert re.search(EXPRESSOES_DERIVADAS[familia], texto, re.IGNORECASE), \
        f"padrão {familia!r} deveria casar em {texto!r} e não casou"


@pytest.mark.parametrize("familia,texto", CASOS_NEGATIVOS_POR_FAMILIA)
def test_cota_literal_nao_e_confundida_com_expressao_proibida(familia, texto):
    import re
    assert not re.search(EXPRESSOES_DERIVADAS[familia], texto, re.IGNORECASE), \
        f"padrão {familia!r} casou indevidamente em {texto!r}"


# ---------------------------------------------------------------------------
# Trava de regressão — pares código/nome/peso de CAT-06..09
#
# A leitura da página 59/56 (layout de duas colunas) foi auditada de forma
# independente pelo Codex, que confirmou a associação de cada código com seu
# nome e peso batendo com o PDF real. Este teste NÃO é prova autônoma da
# leitura do PDF — ele só IMPEDE que uma edição futura no YAML troque um par
# já homologado sem que ninguém perceba, comparando o texto da afirmação
# contra os valores que a auditoria confirmou.
# ---------------------------------------------------------------------------
PARES_HOMOLOGADOS_CAT_06_09 = {
    "CAT-06": ("SU-039", "Montante da folha", "0,520 kg/m"),
    "CAT-07": ("SU-040", "Montante mão de amigo", "0,480 kg/m"),
    "CAT-08": ("SU-041", "Montante mão de amigo", "0,507 kg/m"),
    "CAT-09": ("SU-053", "Travessa da folha", "0,507 kg/m"),
}


@pytest.mark.parametrize("identificador", sorted(PARES_HOMOLOGADOS_CAT_06_09))
def test_par_codigo_nome_peso_de_cat_06_09_nao_regride(catalogo, identificador):
    codigo, nome, peso = PARES_HOMOLOGADOS_CAT_06_09[identificador]
    a = catalogo.afirmacao(identificador)
    assert a is not None, f"{identificador} não existe mais no manifesto"
    assert codigo in a.texto, f"{identificador}: código {codigo} ausente"
    assert nome in a.texto, f"{identificador}: nome {nome!r} ausente"
    assert peso in a.texto, f"{identificador}: peso {peso!r} ausente"


def test_toda_afirmacao_tem_localizador_com_as_duas_paginas(catalogo):
    """Citar um documento de 135 páginas sem dizer onde não é auditável."""
    for a in catalogo.afirmacoes:
        for c in a.citacoes:
            loc = c.localizador
            assert loc is not None, f"{a.identificador}: citação sem localizador"
            assert loc.pagina_documento is not None, a.identificador
            assert loc.pagina_pdf is not None, a.identificador
            assert 1 <= loc.pagina_pdf <= 135, \
                f"{a.identificador}: página fora do PDF ({loc.pagina_pdf})"


def test_as_duas_paginas_divergem_e_o_deslocamento_nao_e_constante(catalogo):
    """Achado real deste catálogo: a folha 45 é a 42ª do PDF (-3) e a folha
    117 é a 113ª (-4). Um campo único de página mandaria conferir a folha
    errada em pelo menos uma das regiões."""
    deslocamentos = {
        loc.pagina_documento - loc.pagina_pdf
        for a in catalogo.afirmacoes for c in a.citacoes
        if (loc := c.localizador) and isinstance(loc.pagina_documento, int)}
    assert len(deslocamentos) > 1, \
        f"deslocamento único {deslocamentos} — reveja as páginas registradas"


# ---------------------------------------------------------------------------
# 6 · nenhuma referência cross-manifest
# ---------------------------------------------------------------------------

def test_nenhuma_citacao_aponta_para_fora_do_manifesto(catalogo):
    indice = catalogo.indice_de_fontes()
    for a in catalogo.afirmacoes:
        for c in a.citacoes:
            assert c.id_fonte in indice, \
                f"{a.identificador} cita fonte de fora: {c.id_fonte}"


def test_nenhuma_afirmacao_deriva_de_outro_manifesto(catalogo):
    """Cross-manifest não é suportado e não foi contornado: `derivada_de` está
    vazio em todas as afirmações do catálogo."""
    for a in catalogo.afirmacoes:
        assert a.derivada_de == (), \
            f"{a.identificador} declara derivação: {a.derivada_de}"


def test_o_catalogo_nao_cita_nenhuma_fonte_do_acervo_de_campo(catalogo):
    campo = carregar_manifesto(MANIFESTO_CAMPO)
    ids_de_campo = set(campo.indice_de_fontes())
    for a in catalogo.afirmacoes:
        for c in a.citacoes:
            assert c.id_fonte not in ids_de_campo, \
                f"{a.identificador} cita fonte do acervo de campo"


# ---------------------------------------------------------------------------
# 7 e 9 · a ingestão do catálogo não criou dependência cross-manifest
#
# Não trava mais os BYTES do manifesto de campo — isso impediria qualquer
# correção legítima futura de A18 em diante (ver
# curadoria/handoffs/e4h/correcao_epistemologica_pos_e4g.md, que corrigiu o
# texto de A18 sem tocar nesta PR). O que a ingestão do catálogo precisa
# garantir não é que o manifesto de campo pare no tempo — é que ela não
# introduziu citação nem derivação cruzando a fronteira dos dois manifestos.
# ---------------------------------------------------------------------------

def test_suprema_nao_cita_fonte_exclusiva_do_catalogo(catalogo):
    """Nenhuma citação de SUPREMA_CORRER_2F aponta para uma fonte que só
    existe no manifesto do catálogo — a ingestão não criou dependência na
    direção contrária à testada em test_o_catalogo_nao_cita_nenhuma_fonte_do_acervo_de_campo."""
    campo = carregar_manifesto(MANIFESTO_CAMPO)
    ids_do_catalogo = set(catalogo.indice_de_fontes())
    for a in campo.afirmacoes:
        for c in a.citacoes:
            assert c.id_fonte not in ids_do_catalogo, \
                f"{a.identificador} (SUPREMA_CORRER_2F) cita fonte exclusiva " \
                f"do catálogo Alcoa: {c.id_fonte}"


def test_suprema_nao_deriva_de_nenhuma_cat(catalogo):
    """Nenhuma afirmação de SUPREMA_CORRER_2F declara `derivada_de` apontando
    para uma CAT-* do catálogo — cross-manifest de afirmação não foi
    introduzido em nenhuma direção."""
    campo = carregar_manifesto(MANIFESTO_CAMPO)
    ids_cat = {a.identificador for a in catalogo.afirmacoes}
    for a in campo.afirmacoes:
        origem_indevida = set(a.derivada_de) & ids_cat
        assert not origem_indevida, \
            f"{a.identificador} (SUPREMA_CORRER_2F) deriva de CAT-* do " \
            f"catálogo: {origem_indevida}"


def test_baseline_do_acervo_de_campo_nao_muda():
    """O catálogo não é um 113º artefato físico: contagem e bytes do acervo de
    campo continuam exatamente os mesmos."""
    campo = carregar_manifesto(MANIFESTO_CAMPO)
    assert len(campo.artefatos_externos) == ARTEFATOS_CAMPO
    assert campo.total_de_bytes == BYTES_CAMPO
    assert campo.versao == 1


def test_os_dois_manifestos_tem_raizes_logicas_distintas(catalogo):
    campo = carregar_manifesto(MANIFESTO_CAMPO)
    assert catalogo.raiz_logica != campo.raiz_logica
    assert set(catalogo.indice_de_fontes()) & set(campo.indice_de_fontes()) \
        == set(), "os dois manifestos não podem compartilhar id_fonte"


# ---------------------------------------------------------------------------
# 8 · gates
# ---------------------------------------------------------------------------

def test_o_catalogo_nao_abre_gate_de_calculo():
    from composicao import fontes, receita as receita_mod
    rec = receita_mod.construir_receita_preliminar()
    bib = fontes.carregar_biblioteca_oficial()
    assert not validar.validar_prontidao_para_calculo(rec, bib, RAIZ).ok


def test_o_catalogo_nao_abre_gate_de_producao():
    from composicao import fontes, receita as receita_mod
    rec = receita_mod.construir_receita_preliminar()
    bib = fontes.carregar_biblioteca_oficial()
    assert not validar.validar_prontidao_para_producao(rec, bib, RAIZ).ok
