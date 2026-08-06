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

from .modelos import (ALVOS_DIMENSIONAIS_BASE, ESCOPOS_DE_APROVACAO,
                      ESTADO_CASO_VALIDADO, ESTADOS_CONFIRMADOS,
                      ESTADOS_NAO_CALCULAVEIS, IDENTIFICADORES_DE_CASO,
                      ITENS_DE_ACESSORIO_BASE, TIPOS_APTOS_PARA_VALIDAR_CASO,
                      CasoRealFabricacao, EstadoConhecimento, ReceitaErro,
                      ReceitaTipologia, ResultadoAprovacao, ResultadoValidacao,
                      aprovacoes_por_escopo,
                      incompatibilidades_da_afirmacao,
                      incompatibilidades_das_fontes_embutidas,
                      TIPOS_APTOS_PARA_CONFERIR_RECEITA,
                      assinatura_documental_caso,
                      fingerprints_primarios_do_caso,
                      indice_fontes_receita, problemas_da_fonte_de_aprovacao)

from .fontes import PERFIS_SUPREMA_E4C as PERFIS_OFICIAIS

ORIGEM_BIBLIOTECA = "dados/ (via contrato de consumo)"
ORIGEM_RECEITA = "composicao/receita.py"

# O gate de produção exige EXATAMENTE os três casos canônicos, distintos entre
# si. Contar "três validados" aceitaria o mesmo caso repetido — e uma fórmula
# conferida três vezes contra a mesma janela não foi conferida.
CASOS_EXIGIDOS_PARA_PRODUCAO = IDENTIFICADORES_DE_CASO


ORIGEM_CASO = "caso real de fabricação"
ORIGEM_ARTEFATO = "artefato de evidência no repositório"

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

    # Inventário E ocorrências: as duas citam a biblioteca, e as duas precisam
    # resolver. Conferir só as ocorrências deixaria a receita preliminar —
    # que ainda não tem nenhuma — sem verificação alguma.
    referencias = list(receita.perfis_disponiveis) + [c.perfil for c
                                                      in receita.componentes]
    vistos = set()
    for p in referencias:
        if p in vistos:
            continue
        vistos.add(p)
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
    """A evidência de cada item sustenta o que ele afirma.

    A mesma matriz cobrada da ficha do especialista vale para componentes e
    regras: sem isso a receita teria dois pesos, e um componente
    `CONFIRMADO_CASO_REAL` apoiado só num catálogo passaria."""
    r = ResultadoValidacao.aprovado()
    for item in tuple(receita.componentes) + receita.todas_as_regras:
        if item.estado in ESTADOS_NAO_CALCULAVEIS:
            continue                 # pendente é estado legítimo, não erro
        problemas = incompatibilidades_das_fontes_embutidas(item.estado,
                                                            item.fontes)
        if problemas:
            r = r.somar(_reprovar(
                item.identificador, "evidência não sustenta o estado",
                {"estado": item.estado.value,
                 "fontes": [f"{f.id_fonte}:{f.tipo}/{f.estado.value}"
                            for f in item.fontes],
                 "motivos": list(problemas)},
                "fonte com estado e tipo compatíveis (e autoria, se for do "
                "especialista)", ORIGEM_RECEITA))
    # A autoria da aprovação é conferida contra o registro central de fontes
    # em `validar_aprovacoes`: aqui a fonte é só um ID.
    return r


# ---------------------------------------------------------------------------
# Cobertura estrutural
# ---------------------------------------------------------------------------

def validar_cobertura_estrutural_receita(receita: ReceitaTipologia) -> ResultadoValidacao:
    """A receita tem as peças que uma correr de duas folhas exige.

    Independe dos estados de conhecimento: uma receita preliminar pode ter tudo
    pendente, mas não pode estar INCOMPLETA. Sem esta checagem, apagar um perfil
    ou um alvo dimensional deixaria os gates satisfeitos com menos do que a
    tipologia precisa."""
    r = ResultadoValidacao.aprovado()

    if receita.sistema != "Suprema":
        r = r.somar(_reprovar(receita.codigo, "sistema divergente",
                              receita.sistema, "Suprema", ORIGEM_RECEITA))
    if receita.quantidade_folhas != 2:
        r = r.somar(_reprovar(receita.codigo, "quantidade de folhas divergente",
                              receita.quantidade_folhas, 2, ORIGEM_RECEITA))

    # --- INVENTÁRIO: os oito perfis oficiais precisam estar disponíveis.
    # Não se exige um componente por perfil: um perfil pode aparecer em zero,
    # uma ou várias ocorrências funcionais, e quantas é o que falta descobrir.
    disponiveis = list(receita.codigos_disponiveis)
    faltando = [p for p in PERFIS_OFICIAIS if p not in disponiveis]
    if faltando:
        r = r.somar(_reprovar(receita.codigo,
                              "perfis oficiais ausentes do inventário",
                              faltando, list(PERFIS_OFICIAIS), ORIGEM_RECEITA))
    inv_dup = sorted({p for p in disponiveis if disponiveis.count(p) > 1})
    if inv_dup:
        r = r.somar(_reprovar(receita.codigo, "perfil duplicado no inventário",
                              inv_dup, "uma entrada por perfil", ORIGEM_RECEITA))
    intrusos = sorted({p for p in disponiveis if p not in PERFIS_OFICIAIS})
    if intrusos:
        r = r.somar(_reprovar(receita.codigo, "perfil fora do microlote oficial",
                              intrusos, list(PERFIS_OFICIAIS), ORIGEM_RECEITA))
    for ref in receita.perfis_disponiveis:
        if ref.id_geometria != f"GEO-{ref.codigo_perfil}":
            r = r.somar(_reprovar(ref.codigo_perfil, "referência GEO divergente",
                                  ref.id_geometria, f"GEO-{ref.codigo_perfil}",
                                  ORIGEM_RECEITA))
        if ref.perfil_id_oficial != f"ALCOA-{ref.codigo_perfil}":
            r = r.somar(_reprovar(ref.codigo_perfil,
                                  "associação oficial divergente",
                                  ref.perfil_id_oficial,
                                  f"ALCOA-{ref.codigo_perfil}", ORIGEM_RECEITA))

    # --- OCORRÊNCIAS funcionais: quantas quiser, com identificador único e
    # perfil que exista no inventário.
    fora_do_inventario = sorted({c.perfil.codigo_perfil
                                 for c in receita.componentes
                                 if c.perfil.codigo_perfil not in disponiveis})
    if fora_do_inventario:
        r = r.somar(_reprovar(receita.codigo,
                              "componente usa perfil fora do inventário",
                              fora_do_inventario, disponiveis, ORIGEM_RECEITA))
    ids = [c.identificador for c in receita.componentes]
    ids_dup = sorted({i for i in ids if ids.count(i) > 1})
    if ids_dup:
        r = r.somar(_reprovar(receita.codigo,
                              "identificador de componente duplicado", ids_dup,
                              "identificadores únicos", ORIGEM_RECEITA))
    # --- regras dimensionais: os alvos BASE precisam existir; alvos novos são
    # bem-vindos desde que declarem de onde vieram (o modelo já cobra isso).
    alvos = [g.alvo for g in receita.regras_dimensionais]
    ausentes = [a for a in ALVOS_DIMENSIONAIS_BASE if a not in alvos]
    if ausentes:
        r = r.somar(_reprovar(receita.codigo, "alvo dimensional base ausente",
                              ausentes, list(ALVOS_DIMENSIONAIS_BASE),
                              ORIGEM_RECEITA))
    alvo_dup = sorted({a for a in alvos if alvos.count(a) > 1})
    if alvo_dup:
        r = r.somar(_reprovar(receita.codigo, "alvo dimensional duplicado",
                              alvo_dup, "uma regra por alvo", ORIGEM_RECEITA))
    ids_regra = [g.identificador for g in receita.todas_as_regras]
    regra_dup = sorted({i for i in ids_regra if ids_regra.count(i) > 1})
    if regra_dup:
        r = r.somar(_reprovar(receita.codigo,
                              "identificador de regra duplicado", regra_dup,
                              "identificadores únicos", ORIGEM_RECEITA))

    # --- acessórios: exatamente um requisito por item necessário
    itens = [a.item for a in receita.regras_acessorios]
    falta_acess = [i for i in ITENS_DE_ACESSORIO_BASE if i not in itens]
    if falta_acess:
        r = r.somar(_reprovar(receita.codigo,
                              "requisito de acessório base ausente",
                              falta_acess, list(ITENS_DE_ACESSORIO_BASE),
                              ORIGEM_RECEITA))
    acess_dup = sorted({i for i in itens if itens.count(i) > 1})
    if acess_dup:
        r = r.somar(_reprovar(receita.codigo, "acessório duplicado", acess_dup,
                              "um requisito por item", ORIGEM_RECEITA))
    return r


# ---------------------------------------------------------------------------
# Validação efetiva do caso real
# ---------------------------------------------------------------------------

def problemas_da_validacao_caso(caso: CasoRealFabricacao) -> tuple[str, ...]:
    """Por que a validação declarada NÃO vale.

    Um objeto `ValidacaoCasoReal(resultado=APROVADO)` é uma declaração; para
    valer, ela precisa de fonte apta a registrar a conferência, com autor e
    data coerentes, sobre dados íntegros."""
    val = caso.validacao
    if val is None:
        return ("caso sem validação estruturada",)
    problemas = []
    if not val.aprovada:
        problemas.append(f"validação com resultado {val.resultado.value}")

    indice = caso.indice_fontes
    ausentes = [i for i in val.fontes_ids if i not in indice]
    if ausentes:
        problemas.append(f"validação cita fonte inexistente: {ausentes}")
        return tuple(problemas)

    fontes = [indice[i] for i in val.fontes_ids]
    for f in fontes:
        if f.estado in ESTADOS_NAO_CALCULAVEIS:
            problemas.append(
                f"fonte da validação {f.id_fonte} está {f.estado.value}")
    aptas = [f for f in fontes
             if f.tipo in TIPOS_APTOS_PARA_VALIDAR_CASO
             and f.estado in (EstadoConhecimento.CONFIRMADO_CASO_REAL,
                              EstadoConhecimento.CONFIRMADO_ESPECIALISTA)
             and f.responsavel and f.data]
    if not aptas:
        problemas.append(
            f"nenhuma fonte apta a registrar validação "
            f"(esperado tipo em {sorted(TIPOS_APTOS_PARA_VALIDAR_CASO)}, "
            f"confirmada, com responsável e data)")
    else:
        if val.responsavel.strip() not in {f.responsavel.strip() for f in aptas}:
            problemas.append(
                f"responsável da validação ({val.responsavel}) divergente da "
                f"evidência ({sorted({f.responsavel for f in aptas})})")
        if val.data not in {f.data for f in aptas}:
            problemas.append(
                f"data da validação ({val.data}) divergente da evidência "
                f"({sorted({f.data for f in aptas})})")
    return tuple(problemas)


def estado_validacao_caso(caso: CasoRealFabricacao,
                          perfis_oficiais=()) -> str:
    """Estado EFETIVO do caso: `VALIDADO` só com evidência apta e dados íntegros."""
    if problemas_da_validacao_caso(caso):
        return caso.estado_recebimento
    if not validar_integridade_caso_real(caso, perfis_oficiais or PERFIS_OFICIAIS).ok:
        return caso.estado_recebimento
    return ESTADO_CASO_VALIDADO


def caso_validado(caso: CasoRealFabricacao, perfis_oficiais=()) -> bool:
    return estado_validacao_caso(caso, perfis_oficiais) == ESTADO_CASO_VALIDADO


# ---------------------------------------------------------------------------
# Componentes e regras
# ---------------------------------------------------------------------------

def validar_componentes_confirmados(receita: ReceitaTipologia) -> ResultadoValidacao:
    """Reprova enquanto qualquer componente não estiver plenamente confirmado.

    Receita sem nenhuma ocorrência funcional não calcula nada: ela sabe quais
    perfis existem, não como a janela se monta."""
    r = ResultadoValidacao.aprovado()
    if not receita.componentes:
        r = r.somar(_reprovar(
            receita.codigo, "nenhuma ocorrência funcional registrada", 0,
            "> 0 componentes com papel, quantidade e posição", ORIGEM_RECEITA))
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

    # Perfil e APLICAÇÃO são coisas diferentes: o perfil só responde por
    # `observacoes_gerais`; papel, quantidade e orientação vivem em cada
    # ocorrência. Cobrar `perfil.funcao` era procurar campo que não existe mais.
    ids_componente: dict = {}
    for perfil in caso.perfis:
        alvo_perfil = f"{ident}.perfis.{perfil.codigo_perfil}"
        if perfil.observacoes_gerais and perfil.estado is not None:
            r = r.somar(_validar_item_de_caso(perfil, alvo_perfil, (), indice))
        for i, ap in enumerate(perfil.aplicacoes):
            if ap.vazia:
                continue
            alvo = f"{alvo_perfil}.aplicacoes[{i}]"
            if ap.id_componente:
                if ap.id_componente in ids_componente:
                    r = r.somar(_reprovar(
                        alvo, "id_componente duplicado no caso",
                        ap.id_componente,
                        f"único (já usado em {ids_componente[ap.id_componente]})",
                        ORIGEM_CASO))
                ids_componente[ap.id_componente] = alvo
            if ap.estado in ESTADOS_NAO_CALCULAVEIS or ap.estado is None:
                continue          # aplicação parcial fica registrada, não prova
            r = r.somar(_validar_item_de_caso(
                ap, alvo, ("id_componente", "funcao", "quantidade",
                           "orientacao"), indice))

    return r


# ---------------------------------------------------------------------------
# Estudo × homologação
# ---------------------------------------------------------------------------

def validar_caso_para_estudo(caso: CasoRealFabricacao,
                             perfis_oficiais=()) -> ResultadoValidacao:
    """Mínimo para COMEÇAR a estudar uma derivação — não para homologar.

    Um caso com um corte e um vidro já permite investigar; ele não prova que a
    receita inteira produz aquela janela."""
    return validar_integridade_caso_real(caso, perfis_oficiais or PERFIS_OFICIAIS)


def validar_caso_contra_receita(caso: CasoRealFabricacao,
                                receita: ReceitaTipologia) -> ResultadoValidacao:
    """A janela real corresponde, peça a peça, ao que a receita declara.

    Integridade do caso responde "os dados estão completos?". Isto responde
    "a receita produz ESTA janela?" — e são perguntas diferentes: uma lista de
    corte impecável pode não ter nada a ver com os componentes registrados."""
    r = ResultadoValidacao.aprovado()
    ident = caso.identificador or "caso sem identificador"
    confirmados = [c for c in receita.componentes if c.confirmado]
    if not confirmados:
        return _reprovar(ident, "receita sem componentes confirmados", 0,
                         "> 0 ocorrências funcionais confirmadas", ORIGEM_CASO)

    por_id = {c.identificador: c for c in confirmados}
    cortes_por_componente: dict = {}
    for i, corte in enumerate(caso.cortes):
        alvo = f"{ident}.cortes[{i}]"
        if not corte.componente_id:
            r = r.somar(_reprovar(alvo, "corte sem componente_id", None,
                                  sorted(por_id), ORIGEM_CASO))
            continue
        comp = por_id.get(corte.componente_id)
        if comp is None:
            r = r.somar(_reprovar(alvo, "corte cita componente desconhecido",
                                  corte.componente_id, sorted(por_id),
                                  ORIGEM_CASO))
            continue
        if corte.perfil != comp.perfil.codigo_perfil:
            r = r.somar(_reprovar(
                alvo, "perfil do corte diverge do componente", corte.perfil,
                comp.perfil.codigo_perfil, ORIGEM_CASO))
        cortes_por_componente.setdefault(corte.componente_id, 0)
        cortes_por_componente[corte.componente_id] += (corte.quantidade or 0)

    for comp in confirmados:
        total = cortes_por_componente.get(comp.identificador)
        if total is None:
            r = r.somar(_reprovar(comp.identificador,
                                  "componente sem corte correspondente", None,
                                  f"{comp.quantidade} peça(s)", ORIGEM_CASO))
        elif comp.quantidade is not None and total != comp.quantidade:
            r = r.somar(_reprovar(
                comp.identificador, "quantidade agregada divergente", total,
                comp.quantidade, ORIGEM_CASO))

    if not caso.vidros:
        r = r.somar(_reprovar(ident, "caso sem vidros para conferir", 0,
                              "> 0 chapas", ORIGEM_CASO))
    calculaveis = [a.item for a in receita.regras_acessorios if a.calculavel]
    presentes = {a.item for a in caso.acessorios if a.item}
    faltando = [i for i in calculaveis if i not in presentes]
    if faltando:
        r = r.somar(_reprovar(ident, "acessório calculado ausente do caso",
                              faltando, calculaveis, ORIGEM_CASO))
    return r


def conferencia_valida_do_caso(receita: ReceitaTipologia,
                               caso: CasoRealFabricacao) -> tuple[str, ...]:
    """Problemas da conferência do caso contra o RESULTADO CALCULADO.

    "Conferi cortes, vidros e acessórios" é afirmação sem objeto enquanto não
    existe um resultado para comparar. A conferência aponta para um
    `ResultadoCalculoCaso`; sem ele, não há o que conferir."""
    ident = caso.identificador or ""
    registros = receita.conferencia_do_caso(ident)
    if not registros:
        return (f"{ident}: sem conferência contra a receita",)
    if len(registros) > 1:
        return (f"{ident}: {len(registros)} conferências para o mesmo caso — "
                f"conflito não se resolve pela ordem",)
    conf = registros[0]
    problemas = []
    if not conf.aprovada:
        problemas.append(
            f"{ident}: conferência {conf.resultado.value}"
            + (f" com divergências {list(conf.divergencias)}"
               if conf.divergencias else "")
            + ("" if conf.cortes_conferidos and conf.vidros_conferidos
               and conf.acessorios_conferidos
               else " — cortes, vidros e acessórios precisam ter sido vistos"))

    # --- resultado calculado
    resultado = receita.resultado_calculado(conf.resultado_calculo_id)
    if resultado is None:
        problemas.append(
            f"{ident}: conferência cita resultado calculado inexistente "
            f"({conf.resultado_calculo_id}) — não há o que conferir")
    else:
        if resultado.caso_id != ident:
            problemas.append(
                f"{ident}: resultado {resultado.id_resultado} pertence ao caso "
                f"{resultado.caso_id}")
        if resultado.receita_codigo != receita.codigo:
            problemas.append(
                f"{ident}: resultado {resultado.id_resultado} pertence à receita "
                f"{resultado.receita_codigo}, não a {receita.codigo}")
        if not resultado.tem_conteudo:
            problemas.append(
                f"{ident}: resultado {resultado.id_resultado} sem componentes, "
                f"cortes ou vidros calculados")
        else:
            conferidos = list(conf.componentes_conferidos)
            duplicados = sorted({c for c in conferidos
                                 if conferidos.count(c) > 1})
            if duplicados:
                problemas.append(f"{ident}: componentes conferidos duplicados "
                                 f"{duplicados}")
            calculados = set(resultado.componentes)
            faltando = sorted(calculados - set(conferidos))
            if faltando:
                problemas.append(f"{ident}: componentes calculados não "
                                 f"conferidos {faltando}")
            sobrando = sorted(set(conferidos) - calculados)
            if sobrando:
                problemas.append(f"{ident}: conferiu componentes que não estão "
                                 f"no resultado {sobrando}")

    # --- assinatura
    indice = indice_fontes_receita(receita)
    fonte = indice.get(conf.fonte_id) or caso.indice_fontes.get(conf.fonte_id)
    if fonte is None:
        problemas.append(f"{ident}: conferência cita fonte não registrada "
                         f"({conf.fonte_id})")
        return tuple(problemas)
    if fonte.estado in ESTADOS_NAO_CALCULAVEIS:
        problemas.append(f"{ident}: fonte da conferência está "
                         f"{fonte.estado.value}")
    if fonte.tipo not in TIPOS_APTOS_PARA_CONFERIR_RECEITA:
        problemas.append(
            f"{ident}: fonte {fonte.id_fonte} é {fonte.tipo!r} — conferência "
            f"exige tipo em {sorted(TIPOS_APTOS_PARA_CONFERIR_RECEITA)}")
    if not fonte.autoria_completa:
        problemas.append(f"{ident}: fonte da conferência sem autoria completa")
    else:
        if fonte.responsavel.strip() != conf.responsavel.strip():
            problemas.append(
                f"{ident}: conferência assinada por {conf.responsavel!r} com "
                f"evidência de {fonte.responsavel!r}")
        if fonte.data != conf.data:
            problemas.append(
                f"{ident}: conferência datada em {conf.data} com evidência de "
                f"{fonte.data}")
    return tuple(problemas)


# ---------------------------------------------------------------------------
# Independência documental dos casos
# ---------------------------------------------------------------------------

def validar_independencia_dos_casos(casos) -> ResultadoValidacao:
    """Três janelas, não a mesma três vezes.

    Medidas diferentes não bastam: a mesma lista de corte pode ser reaproveitada
    com números trocados. Exemplar, evidência primária e assinatura documental
    têm de ser distintos."""
    r = ResultadoValidacao.aprovado()
    casos = tuple(casos)

    sem_exemplar = [c.identificador for c in casos if not c.id_exemplar]
    if sem_exemplar:
        r = r.somar(_reprovar("-", "caso sem id_exemplar", sem_exemplar,
                              "ordem de produção, orçamento, etiqueta ou "
                              "código interno", ORIGEM_CASO))
    exemplares = [c.id_exemplar for c in casos if c.id_exemplar]
    repetidos = sorted({e for e in exemplares if exemplares.count(e) > 1})
    if repetidos:
        r = r.somar(_reprovar("-", "mesmo exemplar usado em mais de um caso",
                             repetidos, "um exemplar por caso", ORIGEM_CASO))

    # Artefato primário é identificado pelo CONTEÚDO (sha256) quando há hash:
    # a mesma lista de corte copiada para três pastas continua sendo um
    # artefato só. Ter uma foto própria ao lado não torna a lista compartilhada
    # em evidência independente.
    dono_do_artefato: dict = {}
    for c in casos:
        primarias = fingerprints_primarios_do_caso(c)
        if not primarias:
            r = r.somar(_reprovar(c.identificador or "-",
                                  "caso sem evidência primária própria", [],
                                  "medição, foto, croqui ou lista de corte",
                                  ORIGEM_CASO))
            continue
        for fp in sorted(primarias):
            anterior = dono_do_artefato.get(fp)
            if anterior is not None and anterior != c.identificador:
                r = r.somar(_reprovar(
                    c.identificador or "-",
                    "artefato primário reutilizado entre casos", fp,
                    f"evidência exclusiva (já usada por {anterior})",
                    ORIGEM_CASO))
            dono_do_artefato[fp] = c.identificador

    assinaturas: dict = {}
    for c in casos:
        a = assinatura_documental_caso(c)
        if a in assinaturas:
            r = r.somar(_reprovar(
                c.identificador or "-", "assinatura documental repetida",
                [assinaturas[a], c.identificador],
                "documentos distintos", ORIGEM_CASO))
        assinaturas[a] = c.identificador
    return r


# ---------------------------------------------------------------------------
# Artefatos de evidência
# ---------------------------------------------------------------------------

def _dentro_da_raiz(caminho, raiz) -> bool:
    """Contenção por componentes de caminho, não por prefixo de texto."""
    from pathlib import Path as _P
    try:
        _P(caminho).relative_to(_P(raiz))
        return True
    except ValueError:
        return False


def validar_artefato_de_evidencia(fonte, raiz_repositorio) -> ResultadoValidacao:
    """A evidência local existe e continua sendo a que foi registrada.

    Um caminho bem formado não prova nada: o arquivo pode não existir, ou ter
    sido substituído depois. `sha256` é o que transforma a referência em prova."""
    from pathlib import Path as _P
    if fonte.forma_referencia != "arquivo":
        return ResultadoValidacao.aprovado()      # URL/identificador externo
    if fonte.estado in ESTADOS_NAO_CALCULAVEIS:
        return ResultadoValidacao.aprovado()      # pendente não precisa provar

    raiz = _P(raiz_repositorio).resolve()
    alvo = (raiz / fonte.referencia)
    try:
        resolvido = alvo.resolve()          # resolve symlinks
    except OSError:
        resolvido = alvo
    # `startswith` aceitaria `/tmp/repo-fora` como se estivesse em `/tmp/repo`,
    # e um symlink apontando para fora passaria. `relative_to` compara
    # componentes de caminho, não prefixo de texto.
    if not _dentro_da_raiz(resolvido, raiz):
        return _reprovar(fonte.id_fonte, "artefato resolve fora da raiz",
                         fonte.referencia, f"dentro de {raiz}", ORIGEM_ARTEFATO)
    if not resolvido.exists():
        return _reprovar(fonte.id_fonte, "artefato inexistente",
                         fonte.referencia, "arquivo presente no repositório",
                         ORIGEM_ARTEFATO)
    if not resolvido.is_file():
        return _reprovar(fonte.id_fonte, "artefato não é arquivo regular",
                         fonte.referencia, "arquivo regular", ORIGEM_ARTEFATO)
    if not fonte.sha256:
        return _reprovar(fonte.id_fonte, "evidência confirmada sem sha256",
                         None, "sha256 do arquivo registrado", ORIGEM_ARTEFATO)

    import hashlib
    dados = resolvido.read_bytes()
    atual = hashlib.sha256(dados).hexdigest()
    r = ResultadoValidacao.aprovado()
    if atual != fonte.sha256:
        r = r.somar(_reprovar(fonte.id_fonte, "artefato alterado após o registro",
                              atual[:16], fonte.sha256[:16], ORIGEM_ARTEFATO))
    if fonte.tamanho_bytes is not None and len(dados) != fonte.tamanho_bytes:
        r = r.somar(_reprovar(fonte.id_fonte, "tamanho do artefato divergente",
                              len(dados), fonte.tamanho_bytes, ORIGEM_ARTEFATO))
    return r


def validar_artefatos_do_caso(caso: CasoRealFabricacao,
                              raiz_repositorio) -> ResultadoValidacao:
    r = ResultadoValidacao.aprovado()
    for f in caso.fontes:
        r = r.somar(validar_artefato_de_evidencia(f, raiz_repositorio))
    return r


def validar_artefatos_da_receita(receita: ReceitaTipologia,
                                 raiz_repositorio) -> ResultadoValidacao:
    r = ResultadoValidacao.aprovado()
    try:
        indice = indice_fontes_receita(receita)
    except ReceitaErro as e:
        return _reprovar(receita.codigo, "registro de fontes inconsistente",
                         str(e), "um id_fonte por evidência", ORIGEM_RECEITA)
    for fonte in indice.values():
        r = r.somar(validar_artefato_de_evidencia(fonte, raiz_repositorio))
    return r


def validar_prontidao_para_visualizacao(receita: ReceitaTipologia,
                                        biblioteca,
                                        raiz_repositorio=None) -> ResultadoValidacao:
    """Visualização PRELIMINAR: mostrar os perfis que existem, sem montá-los.

    Aceita papéis pendentes — desde que a receita se declare preliminar. O que
    não se aceita é referência quebrada: desenhar um perfil que não está na
    biblioteca seria mostrar geometria inventada."""
    r = validar_referencias_geometricas(receita, biblioteca)
    r = r.somar(validar_cobertura_estrutural_receita(receita))
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


def validar_prontidao_para_calculo(receita: ReceitaTipologia, biblioteca,
                                   raiz_repositorio=None) -> ResultadoValidacao:
    """Cálculo oficial: tudo confirmado, sem exceção.

    Inclui a integridade dos ARTEFATOS: uma evidência que sumiu ou foi trocada
    depois do registro não sustenta mais o que sustentava."""
    r = validar_referencias_geometricas(receita, biblioteca)
    if raiz_repositorio is not None:
        r = r.somar(validar_artefatos_da_receita(receita, raiz_repositorio))
    r = r.somar(validar_cobertura_estrutural_receita(receita))
    r = r.somar(validar_fontes(receita))
    r = r.somar(validar_componentes_confirmados(receita))
    r = r.somar(validar_regras_dimensionais(receita))
    r = r.somar(validar_regras_de_acessorios(receita))
    if receita.preliminar:
        r = r.somar(_reprovar(
            receita.codigo, "receita ainda é preliminar", receita.estado,
            "estado confirmado pelo especialista", ORIGEM_RECEITA))
    return r


def validar_prontidao_para_producao(receita: ReceitaTipologia, biblioteca,
                                    raiz_repositorio=None) -> ResultadoValidacao:
    """Produção: cálculo válido E conferido contra janelas reais.

    Fórmula que fecha na aritmética e nunca foi conferida contra uma janela
    fabricada não autoriza corte de alumínio."""
    r = validar_prontidao_para_calculo(receita, biblioteca, raiz_repositorio)
    r = r.somar(validar_casos_reais_independentes(receita))
    r = r.somar(validar_independencia_dos_casos(receita.casos_reais))
    r = r.somar(validar_aprovacoes(receita))
    if not receita.resultados_calculados:
        r = r.somar(_reprovar(
            receita.codigo, "nenhum resultado calculado para conferir", 0,
            "um ResultadoCalculoCaso por caso — produção compara o cálculo "
            "com a janela real, e não existe cálculo nesta sprint",
            ORIGEM_RECEITA))
    for caso in receita.casos_reais:
        if raiz_repositorio is not None:
            r = r.somar(validar_artefatos_do_caso(caso, raiz_repositorio))
        r = r.somar(validar_caso_contra_receita(caso, receita))
        for motivo in conferencia_valida_do_caso(receita, caso):
            r = r.somar(_reprovar(caso.identificador or "-",
                                  "conferência contra a receita inválida",
                                  motivo, "uma conferência APROVADA por caso",
                                  ORIGEM_CASO))
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
    validados = [c for c in receita.casos_reais
                 if caso_validado(c, PERFIS_OFICIAIS)]
    # Casos que se DECLARAM validados mas não passam: o motivo tem de aparecer.
    # Contar só os efetivos deixaria a falha como "caso canônico ausente", sem
    # dizer que o problema era a lista de corte vazia.
    declarados = [c for c in receita.casos_reais
                  if c.validacao_declarada_aprovada and c not in validados]
    for c in declarados:
        r = r.somar(validar_integridade_caso_real(c, PERFIS_OFICIAIS))
        for motivo in problemas_da_validacao_caso(c):
            r = r.somar(_reprovar(
                c.identificador or "caso sem identificador",
                "validação declarada não vale", motivo,
                "validação aprovada com fonte apta sobre dados íntegros",
                ORIGEM_CASO))
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
        for motivo in problemas_da_validacao_caso(c):
            r = r.somar(_reprovar(c.identificador, "validação do caso inválida",
                                  motivo, "validação aprovada com fonte apta",
                                  ORIGEM_CASO))
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
