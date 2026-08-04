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
                      IDENTIFICADORES_DE_CASO, EstadoConhecimento,
                      ReceitaTipologia, ResultadoAprovacao, ResultadoValidacao,
                      aprovacoes_por_escopo, autoria_de_especialista_ausente)

ORIGEM_BIBLIOTECA = "dados/ (via contrato de consumo)"
ORIGEM_RECEITA = "composicao/receita.py"

# O gate de produção exige EXATAMENTE os três casos canônicos, distintos entre
# si. Contar "três validados" aceitaria o mesmo caso repetido — e uma fórmula
# conferida três vezes contra a mesma janela não foi conferida.
CASOS_EXIGIDOS_PARA_PRODUCAO = IDENTIFICADORES_DE_CASO


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
    for aprov in receita.aprovacoes:
        if autoria_de_especialista_ausente(
                EstadoConhecimento.CONFIRMADO_ESPECIALISTA, (aprov.fonte,)):
            r = r.somar(_reprovar(
                f"aprovacao:{aprov.escopo}",
                "aprovação sem autoria completa na fonte",
                aprov.fonte.para_dict(),
                "responsavel, data e referencia", ORIGEM_RECEITA))
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
        if not c.cortes:
            r = r.somar(_reprovar(c.identificador, "caso sem lista de corte",
                                  0, "> 0 peças", ORIGEM_RECEITA))
        if not c.vidros:
            r = r.somar(_reprovar(c.identificador, "caso sem vidros",
                                  0, "> 0 chapas", ORIGEM_RECEITA))
        if not c.fontes:
            r = r.somar(_reprovar(c.identificador, "caso sem fonte registrada",
                                  0, "ao menos uma fonte", ORIGEM_RECEITA))
        val = c.validacao
        if val is not None:
            ausentes = [i for i in val.fontes_ids if i not in c.indice_fontes]
            if ausentes:
                r = r.somar(_reprovar(
                    c.identificador, "validação cita fonte inexistente",
                    ausentes, sorted(c.indice_fontes) or "nenhuma",
                    ORIGEM_RECEITA))
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
