"""Validações e gates da receita.

Três gates, em ordem crescente de exigência:

```
visualização preliminar  aceita papéis pendentes, desde que a receita esteja
                         marcada como preliminar e as referências resolvam
cálculo                  exige TODOS os componentes e regras confirmados
produção                 exige cálculo validado contra casos reais e
                         aprovação explícita do especialista
```

Os gates existem para que "ainda não sabemos" seja uma resposta possível do
sistema. Sem eles, a única saída seria inventar um número.
"""
from __future__ import annotations

from .modelos import (ESCOPOS_DE_APROVACAO, ESTADOS_CONFIRMADOS,
                      IDENTIFICADORES_DE_CASO, CasoRealFabricacao,
                      EstadoConhecimento, ReceitaErro, ReceitaTipologia,
                      ResultadoAprovacao, ResultadoValidacao,
                      aprovacoes_por_escopo, autoria_de_especialista_ausente,
                      incompatibilidades_da_afirmacao, indice_fontes_receita,
                      problemas_da_fonte_de_aprovacao)

from .fontes import PERFIS_SUPREMA_E4C as PERFIS_OFICIAIS

ORIGEM_BIBLIOTECA = "dados/ (via contrato de consumo)"
ORIGEM_RECEITA = "composicao/receita.py"

# O gate de produção exige EXATAMENTE os três casos canônicos, distintos entre
# si. Contar "três validados" aceitaria o mesmo caso repetido — e uma fórmula
# conferida três vezes contra a mesma janela não foi conferida.
CASOS_EXIGIDOS_PARA_PRODUCAO = IDENTIFICADORES_DE_CASO


ORIGEM_CASO = "caso real de fabricação"

# Campos sem os quais o item não descreve uma peça: uma lista de corte com
# `CorteReal()` vazio tem comprimento zero de informação.
MINIMOS_POR_SECAO = {
    "cortes": ("perfil", "comprimento_mm", "quantidade"),
    "vidros": ("folha", "largura_mm", "altura_mm", "espessura_mm"),
    "baguetes": ("perfil", "comprimento_mm", "quantidade"),
    "acessorios": ("item", "quantidade", "posicao"),
    "folgas": ("entre", "valor_mm"),
    "sobreposicoes": ("entre", "valor_mm"),
}


def _reprovar(alvo, regra, encontrado, esperado, origem):
    return ResultadoValidacao.reprovado(alvo, regra, encontrado, esperado, origem)


# ---------------------------------------------------------------------------
# Referências geométricas
# ---------------------------------------------------------------------------

def validar_referencias_geometricas(receita: ReceitaTipologia,
                                    biblioteca) -> ResultadoValidacao:
    """Toda referência da receita resolve na biblioteca oficial.

    Confere os três elos: a geometria existe, a associação existe, e a
    associação aponta para a geometria esperada. Conferir só o primeiro
    deixaria passar um perfil ligado ao contorno errado."""
    r = ResultadoValidacao.aprovado()
    codigos = {g.codigo for g in biblioteca.geometrias}
    assoc = {a.perfil_id: a.geometria_padrao_id for a in biblioteca.associacoes}

    for comp in receita.componentes:
        p = comp.perfil
        if p.id_geometria not in codigos:
            r = r.somar(_reprovar(p.codigo_perfil, "geometria inexistente",
                                  None, p.id_geometria, ORIGEM_BIBLIOTECA))
            continue
        if p.perfil_id_oficial not in assoc:
            r = r.somar(_reprovar(p.codigo_perfil, "associação inexistente",
                                  None, p.perfil_id_oficial, ORIGEM_BIBLIOTECA))
            continue
        if assoc[p.perfil_id_oficial] != p.id_geometria:
            r = r.somar(_reprovar(
                p.codigo_perfil, "associação aponta para outra geometria",
                assoc[p.perfil_id_oficial], p.id_geometria, ORIGEM_BIBLIOTECA))

    orfas = [pid for pid, gid in assoc.items() if gid not in codigos]
    if orfas:
        r = r.somar(_reprovar("-", "associações órfãs na biblioteca", orfas,
                              [], ORIGEM_BIBLIOTECA))

    # SU-102 e TMS-102 são o mesmo perfil físico (identidade confirmada no
    # E.4C). Uma geometria separada para o TMS-102 quebraria essa identidade.
    if "GEO-TMS-102" in codigos:
        r = r.somar(_reprovar("TMS-102", "GEO-TMS-102 existe", "GEO-TMS-102",
                              "ausente (duplicaria o SU-102)",
                              ORIGEM_BIBLIOTECA))
    return r


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------

def validar_fontes(receita: ReceitaTipologia) -> ResultadoValidacao:
    """`CONFIRMADO` sem evidência é só uma palavra — aqui isso reprova."""
    r = ResultadoValidacao.aprovado()
    for comp in receita.componentes:
        if comp.estado in ESTADOS_CONFIRMADOS and not comp.fontes:
            r = r.somar(_reprovar(comp.identificador,
                                  "componente confirmado sem fonte",
                                  comp.estado.value, "ao menos uma fonte",
                                  ORIGEM_RECEITA))
    for regra in receita.todas_as_regras:
        if regra.estado in ESTADOS_CONFIRMADOS and not regra.fontes:
            r = r.somar(_reprovar(regra.identificador,
                                  "regra confirmada sem evidência",
                                  regra.estado.value, "ao menos uma fonte",
                                  ORIGEM_RECEITA))

    # Autoria vale para TUDO que o especialista confirma: componente, regra
    # dimensional, regra de acessório e aprovação final. Uma decisão de domínio
    # sem autor não pode ser auditada nem revogada.
    for item in tuple(receita.componentes) + receita.todas_as_regras:
        if autoria_de_especialista_ausente(item.estado, item.fontes):
            r = r.somar(_reprovar(
                item.identificador,
                "decisão de especialista sem autoria registrada",
                [f.para_dict() for f in item.fontes],
                "fonte especialista_de_dominio com responsavel, data e "
                "referencia", ORIGEM_RECEITA))
    # A autoria da aprovação é conferida contra o registro central de fontes
    # em `validar_aprovacoes`: aqui a fonte é só um ID.
    return r


# ---------------------------------------------------------------------------
# Componentes e regras
# ---------------------------------------------------------------------------

def validar_componentes_confirmados(receita: ReceitaTipologia) -> ResultadoValidacao:
    """Reprova enquanto qualquer componente não estiver plenamente confirmado."""
    r = ResultadoValidacao.aprovado()
    for comp in receita.componentes:
        pend = comp.pendencias()
        if pend:
            r = r.somar(_reprovar(comp.identificador,
                                  "componente não confirmado", list(pend),
                                  "papel, quantidade, orientação e fonte",
                                  ORIGEM_RECEITA))
    return r


def validar_regras_dimensionais(receita: ReceitaTipologia) -> ResultadoValidacao:
    """Reprova enquanto qualquer regra dimensional não tiver fórmula confirmada."""
    r = ResultadoValidacao.aprovado()
    if not receita.regras_dimensionais:
        return _reprovar(receita.codigo, "nenhuma regra dimensional declarada",
                         0, "> 0", ORIGEM_RECEITA)
    for regra in receita.regras_dimensionais:
        if not regra.calculavel:
            r = r.somar(_reprovar(
                regra.identificador, "regra sem fórmula confirmada",
                {"estado": regra.estado.value, "expressao": regra.expressao},
                "expressão confirmada com evidência", ORIGEM_RECEITA))
    return r


def validar_regras_de_acessorios(receita: ReceitaTipologia) -> ResultadoValidacao:
    """Acessório sem quantidade e posição confirmadas bloqueia o cálculo.

    Deixar acessórios fora do gate daria uma lista de fabricação completa em
    perfis e vidro, e silenciosa sobre quantas roldanas a janela leva."""
    r = ResultadoValidacao.aprovado()
    if not receita.regras_acessorios:
        return _reprovar(receita.codigo, "nenhuma regra de acessório declarada",
                         0, f"> 0 (ao menos os itens necessários)",
                         ORIGEM_RECEITA)
    for regra in receita.regras_acessorios:
        if not regra.calculavel:
            r = r.somar(_reprovar(
                regra.identificador, "acessório sem quantidade ou posição "
                "confirmada",
                {"estado": regra.estado.value,
                 "quantidade": regra.quantidade_expressao,
                 "posicao": regra.posicao},
                "quantidade e posição confirmadas com evidência",
                ORIGEM_RECEITA))
    return r


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def _validar_item_de_caso(item, alvo: str, minimos, indice) -> ResultadoValidacao:
    """Campos mínimos, estado coerente e evidência apta.

    Um item parcial pode ficar no caso como dado recebido; o que ele não pode é
    ser contado como prova para produção."""
    r = ResultadoValidacao.aprovado()
    faltando = [c for c in minimos if getattr(item, c, None) is None]
    if faltando:
        r = r.somar(_reprovar(alvo, "item sem campos mínimos", faltando,
                              list(minimos), ORIGEM_CASO))
    problemas = incompatibilidades_da_afirmacao(item.estado, item.fontes_ids,
                                                indice)
    if problemas:
        r = r.somar(_reprovar(alvo, "item sem evidência apta", list(problemas),
                              "estado confirmado com fonte compatível",
                              ORIGEM_CASO))
    return r


def validar_integridade_caso_real(caso: CasoRealFabricacao,
                                  perfis_oficiais=()) -> ResultadoValidacao:
    """O caso realmente prova o que diz provar.

    `bool(caso.cortes)` aceitava uma lista com objetos vazios: o gate abriria
    porque a tupla não estava vazia, sem que existisse uma única peça descrita.
    Aqui cada item é conferido — campos mínimos, estado e evidência apta."""
    r = ResultadoValidacao.aprovado()
    ident = caso.identificador or "caso sem identificador"
    indice = caso.indice_fontes

    if not caso.tem_medidas:
        r = r.somar(_reprovar(ident, "caso sem medidas completas",
                              {"largura": str(caso.largura_total_mm),
                               "altura": str(caso.altura_total_mm)},
                              "largura e altura em mm", ORIGEM_CASO))
    problemas = incompatibilidades_da_afirmacao(
        caso.estado_dimensoes, caso.fontes_ids_dimensoes, indice)
    if problemas:
        r = r.somar(_reprovar(ident, "dimensões sem evidência apta",
                              list(problemas),
                              "estado confirmado com fonte compatível",
                              ORIGEM_CASO))

    if not caso.cortes:
        r = r.somar(_reprovar(ident, "caso sem lista de corte", 0,
                              "> 0 peças", ORIGEM_CASO))
    for i, corte in enumerate(caso.cortes):
        alvo = f"{ident}.cortes[{i}]"
        r = r.somar(_validar_item_de_caso(corte, alvo,
                                          MINIMOS_POR_SECAO["cortes"], indice))
        if (perfis_oficiais and corte.perfil is not None
                and corte.perfil not in perfis_oficiais):
            r = r.somar(_reprovar(alvo, "perfil fora do microlote oficial",
                                  corte.perfil, list(perfis_oficiais),
                                  ORIGEM_CASO))

    if not caso.vidros:
        r = r.somar(_reprovar(ident, "caso sem vidros", 0, "> 0 chapas",
                              ORIGEM_CASO))
    for i, vidro in enumerate(caso.vidros):
        r = r.somar(_validar_item_de_caso(vidro, f"{ident}.vidros[{i}]",
                                          MINIMOS_POR_SECAO["vidros"], indice))

    # Demais seções: só os itens PREENCHIDOS são cobrados. Seção vazia é
    # pendência de campo, não erro de integridade.
    for secao in ("baguetes", "acessorios", "folgas", "sobreposicoes"):
        for i, item in enumerate(getattr(caso, secao)):
            r = r.somar(_validar_item_de_caso(
                item, f"{ident}.{secao}[{i}]", MINIMOS_POR_SECAO[secao], indice))
    if not caso.vista.vazia:
        r = r.somar(_validar_item_de_caso(caso.vista, f"{ident}.vista",
                                          (), indice))
    for perfil in caso.perfis:
        if not perfil.vazio:
            r = r.somar(_validar_item_de_caso(
                perfil, f"{ident}.perfis.{perfil.codigo_perfil}",
                ("funcao", "quantidade", "orientacao"), indice))

    val = caso.validacao
    if val is None:
        r = r.somar(_reprovar(ident, "caso sem validação estruturada", None,
                              "ValidacaoCasoReal APROVADA", ORIGEM_CASO))
    else:
        ausentes = [i for i in val.fontes_ids if i not in indice]
        if ausentes:
            r = r.somar(_reprovar(ident, "validação cita fonte inexistente",
                                  ausentes, sorted(indice) or "nenhuma",
                                  ORIGEM_CASO))
        else:
            autores = {indice[i].responsavel for i in val.fontes_ids
                       if indice[i].responsavel}
            if autores and val.responsavel.strip() not in autores:
                r = r.somar(_reprovar(
                    ident, "responsável da validação divergente da evidência",
                    val.responsavel, sorted(autores), ORIGEM_CASO))
            datas = {indice[i].data for i in val.fontes_ids if indice[i].data}
            if datas and val.data not in datas:
                r = r.somar(_reprovar(
                    ident, "data da validação divergente da evidência",
                    val.data, sorted(datas), ORIGEM_CASO))
        if not val.aprovada:
            r = r.somar(_reprovar(ident, "validação do caso não é APROVADO",
                                  val.resultado.value,
                                  ResultadoAprovacao.APROVADO.value,
                                  ORIGEM_CASO))
    return r


def validar_prontidao_para_visualizacao(receita: ReceitaTipologia,
                                        biblioteca) -> ResultadoValidacao:
    """Visualização PRELIMINAR: mostrar os perfis que existem, sem montá-los.

    Aceita papéis pendentes — desde que a receita se declare preliminar. O que
    não se aceita é referência quebrada: desenhar um perfil que não está na
    biblioteca seria mostrar geometria inventada."""
    r = validar_referencias_geometricas(receita, biblioteca)
    r = r.somar(validar_fontes(receita))
    if not receita.preliminar:
        pend = [c.identificador for c in receita.componentes if c.pendencias()]
        if pend:
            r = r.somar(_reprovar(
                receita.codigo,
                "receita não preliminar com componentes pendentes", pend, [],
                ORIGEM_RECEITA))
    avisos = tuple(
        f"{c.perfil.codigo_perfil}: {', '.join(c.pendencias())}"
        for c in receita.componentes if c.pendencias())
    return r.somar(ResultadoValidacao.aprovado(avisos))


def validar_prontidao_para_calculo(receita: ReceitaTipologia,
                                   biblioteca) -> ResultadoValidacao:
    """Cálculo oficial: tudo confirmado, sem exceção."""
    r = validar_referencias_geometricas(receita, biblioteca)
    r = r.somar(validar_fontes(receita))
    r = r.somar(validar_componentes_confirmados(receita))
    r = r.somar(validar_regras_dimensionais(receita))
    r = r.somar(validar_regras_de_acessorios(receita))
    if receita.preliminar:
        r = r.somar(_reprovar(
            receita.codigo, "receita ainda é preliminar", receita.estado,
            "estado confirmado pelo especialista", ORIGEM_RECEITA))
    return r


def validar_prontidao_para_producao(receita: ReceitaTipologia,
                                    biblioteca) -> ResultadoValidacao:
    """Produção: cálculo válido E conferido contra janelas reais.

    Fórmula que fecha na aritmética e nunca foi conferida contra uma janela
    fabricada não autoriza corte de alumínio."""
    r = validar_prontidao_para_calculo(receita, biblioteca)
    r = r.somar(validar_casos_reais_independentes(receita))
    r = r.somar(validar_aprovacoes(receita))
    return r


def validar_aprovacoes(receita: ReceitaTipologia) -> ResultadoValidacao:
    """Uma aprovação vigente APROVADA por escopo — nem zero, nem duas.

    Devolver a primeira aprovação encontrada esconderia um segundo parecer
    conflitante, e a ordem da tupla decidiria se a produção abre. Um parecer
    REPROVADO ou REVOGADO não é aprovação nenhuma."""
    r = ResultadoValidacao.aprovado()
    try:
        indice = indice_fontes_receita(receita)
    except ReceitaErro as e:
        return _reprovar(receita.codigo, "registro de fontes inconsistente",
                         str(e), "um id_fonte por evidência", ORIGEM_RECEITA)

    desconhecidos = [a.escopo for a in receita.aprovacoes
                     if a.escopo not in ESCOPOS_DE_APROVACAO]
    if desconhecidos:
        r = r.somar(_reprovar(receita.codigo, "escopo de aprovação desconhecido",
                              desconhecidos, list(ESCOPOS_DE_APROVACAO),
                              ORIGEM_RECEITA))

    for escopo in ESCOPOS_DE_APROVACAO:
        do_escopo = aprovacoes_por_escopo(receita, escopo)
        if not do_escopo:
            r = r.somar(_reprovar(
                receita.codigo, f"sem aprovação do especialista para {escopo}",
                [a.escopo for a in receita.aprovacoes],
                f"uma AprovacaoEspecialista APROVADA com escopo={escopo!r}",
                ORIGEM_RECEITA))
            continue
        if len(do_escopo) > 1:
            r = r.somar(_reprovar(
                receita.codigo, f"mais de uma aprovação vigente para {escopo}",
                [a.resultado.value for a in do_escopo],
                "exatamente uma — conflito não se resolve pela ordem",
                ORIGEM_RECEITA))
            continue
        aprovacao = do_escopo[0]
        if not aprovacao.aprovada:
            r = r.somar(_reprovar(
                receita.codigo, f"aprovação de {escopo} não é APROVADO",
                aprovacao.resultado.value, ResultadoAprovacao.APROVADO.value,
                ORIGEM_RECEITA))
        problemas = problemas_da_fonte_de_aprovacao(aprovacao, indice)
        if problemas:
            r = r.somar(_reprovar(
                receita.codigo, f"evidência da aprovação de {escopo} inválida",
                list(problemas),
                "fonte registrada, de especialista, confirmada e coerente",
                ORIGEM_RECEITA))
    return r


def validar_casos_reais_independentes(receita: ReceitaTipologia) -> ResultadoValidacao:
    """Os três casos canônicos, distintos, completos e validados.

    Três casos com as mesmas medidas não distinguem constante de proporção: a
    fórmula passaria por acidente."""
    r = ResultadoValidacao.aprovado()
    # `validado` deriva de uma ValidacaoCasoReal APROVADA — nunca de uma string
    # escrita à mão no campo de estado.
    validados = [c for c in receita.casos_reais if c.validado]
    por_id = {}
    for c in validados:
        por_id.setdefault(c.identificador, []).append(c)

    duplicados = sorted(i for i, cs in por_id.items() if len(cs) > 1)
    if duplicados:
        r = r.somar(_reprovar(receita.codigo, "casos reais duplicados",
                              duplicados, "um caso por identificador",
                              ORIGEM_RECEITA))
    faltando = [i for i in CASOS_EXIGIDOS_PARA_PRODUCAO if i not in por_id]
    if faltando:
        r = r.somar(_reprovar(
            receita.codigo, "casos reais canônicos ausentes", faltando,
            list(CASOS_EXIGIDOS_PARA_PRODUCAO), ORIGEM_RECEITA))

    dimensoes = []
    for c in validados:
        if c.identificador is None:
            r = r.somar(_reprovar(receita.codigo,
                                  "caso validado sem identificador", None,
                                  list(CASOS_EXIGIDOS_PARA_PRODUCAO),
                                  ORIGEM_RECEITA))
            continue
        if not c.tem_medidas:
            r = r.somar(_reprovar(c.identificador, "caso sem medidas completas",
                                  {"largura": str(c.largura_total_mm),
                                   "altura": str(c.altura_total_mm)},
                                  "largura e altura em mm", ORIGEM_RECEITA))
        if not c.fontes:
            r = r.somar(_reprovar(c.identificador, "caso sem fonte registrada",
                                  0, "ao menos uma fonte", ORIGEM_RECEITA))
        # Aprovar a validação não salva um caso incompleto: as duas condições
        # são necessárias ao mesmo tempo.
        r = r.somar(validar_integridade_caso_real(c, PERFIS_OFICIAIS))
        if c.tem_medidas:
            dimensoes.append((c.identificador,
                              (c.largura_total_mm, c.altura_total_mm)))

    vistos = {}
    for ident, dim in dimensoes:
        if dim in vistos:
            r = r.somar(_reprovar(
                receita.codigo, "casos reais com dimensões idênticas",
                [vistos[dim], ident],
                "medidas distintas (pequeno, médio e grande)", ORIGEM_RECEITA))
        vistos[dim] = ident
    return r
