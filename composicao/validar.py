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

from .modelos import (ESTADOS_CONFIRMADOS, CasoRealFabricacao, ComponenteReceita,
                      EstadoConhecimento, PapelComponente, ReceitaTipologia,
                      RegraDimensional, ResultadoValidacao,
                      ESTADO_CASO_VALIDADO)

ORIGEM_BIBLIOTECA = "dados/ (via contrato de consumo)"
ORIGEM_RECEITA = "composicao/receita.py"

# Quantos casos reais independentes o gate de produção exige. Não é chute de
# engenharia: é o mínimo para que uma fórmula tenha sido conferida em mais de
# uma medida — pequeno, médio e grande.
MINIMO_CASOS_PARA_PRODUCAO = 3


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
        if regra.estado == EstadoConhecimento.CONFIRMADO_ESPECIALISTA:
            sem_autor = [f for f in regra.fontes if not f.responsavel]
            if sem_autor:
                r = r.somar(_reprovar(
                    regra.identificador,
                    "decisão de especialista sem autoria registrada",
                    None, "responsavel preenchido", ORIGEM_RECEITA))
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
    """Reprova enquanto qualquer regra não tiver fórmula confirmada."""
    r = ResultadoValidacao.aprovado()
    if not receita.todas_as_regras:
        return _reprovar(receita.codigo, "nenhuma regra dimensional declarada",
                         0, "> 0", ORIGEM_RECEITA)
    for regra in receita.todas_as_regras:
        if not regra.calculavel:
            r = r.somar(_reprovar(
                regra.identificador, "regra sem fórmula confirmada",
                {"estado": regra.estado.value, "expressao": regra.expressao},
                "expressão confirmada com evidência", ORIGEM_RECEITA))
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
    validados = [c for c in receita.casos_reais
                 if c.estado_validacao == ESTADO_CASO_VALIDADO]
    if len(validados) < MINIMO_CASOS_PARA_PRODUCAO:
        r = r.somar(_reprovar(
            receita.codigo, "casos reais validados insuficientes",
            len(validados), f">= {MINIMO_CASOS_PARA_PRODUCAO} "
            f"(pequeno, médio e grande)", ORIGEM_RECEITA))
    if not receita.decisoes_do_especialista:
        r = r.somar(_reprovar(
            receita.codigo, "sem aprovação registrada do especialista",
            [], "ao menos uma decisão registrada", ORIGEM_RECEITA))
    return r
