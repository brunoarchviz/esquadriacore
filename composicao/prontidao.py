"""Relatório de prontidão — o que já se sabe e o que ainda falta perguntar.

O relatório é determinístico: mesma receita e mesma biblioteca produzem
exatamente o mesmo documento. É o que permite comparar duas rodadas e ver o que
mudou de verdade.

Cada gate vem com o MOTIVO de estar aberto ou bloqueado. Um gate bloqueado sem
motivo legível seria só um "não" — e o objetivo aqui é transformar a ausência de
conhecimento numa lista de perguntas objetivas.
"""
from __future__ import annotations

from .modelos import ReceitaTipologia
from .receita import PERGUNTAS_ABERTAS, variaveis_disponiveis
from .validar import (validar_prontidao_para_calculo,
                      validar_prontidao_para_producao,
                      validar_prontidao_para_visualizacao)

# Perguntas cuja resposta é pré-requisito de qualquer fórmula. Não são
# curiosidade: sem elas não há como sequer nomear as variáveis do cálculo.
CHECKLIST_SERRALHERIA = (
    "Fotografar a janela montada, de dentro e de fora, com escala visível.",
    "Anotar largura e altura totais do vão e do produto acabado.",
    "Copiar a lista de corte real, peça a peça, com perfil e comprimento.",
    "Anotar o desconto de corte aplicado a cada perfil e por quê.",
    "Medir a folga entre folha e marco, nos quatro lados.",
    "Medir a sobreposição no encontro central das duas folhas.",
    "Anotar as medidas do vidro e a folga de encaixe usada.",
    "Fotografar o encaixe da baguete nos dois lados do perfil.",
    "Listar acessórios com quantidade e posição.",
    "Registrar qual folha corre no trilho interno e de que lado se olha.",
    "Registrar o sentido de movimento de cada folha e a posição do fecho.",
    "Guardar o croqui do serralheiro, mesmo rabiscado.",
)


def _resumo_gate(resultado, nome: str) -> dict:
    return {
        "aberto": resultado.ok,
        "motivo": ("todos os requisitos atendidos" if resultado.ok
                   else f"{len(resultado.falhas)} requisito(s) não atendido(s)"),
        "bloqueios": [f"{f['alvo']}: {f['regra']}" for f in resultado.falhas],
        "avisos": list(resultado.avisos),
        "gate": nome,
    }


def gerar_relatorio_prontidao(receita: ReceitaTipologia,
                              biblioteca) -> dict:
    """Documento único com geometrias, componentes, regras, casos e gates."""
    codigos = {g.codigo for g in biblioteca.geometrias}
    disponiveis = sorted(c.perfil.id_geometria for c in receita.componentes
                         if c.perfil.id_geometria in codigos)
    ausentes = sorted(c.perfil.id_geometria for c in receita.componentes
                      if c.perfil.id_geometria not in codigos)

    confirmados = [c.identificador for c in receita.componentes if c.confirmado]
    pendentes = [{"componente": c.identificador,
                  "perfil": c.perfil.codigo_perfil,
                  "pendencias": list(c.pendencias())}
                 for c in receita.componentes if c.pendencias()]

    regras_confirmadas = [r.identificador for r in receita.regras_dimensionais
                          if r.calculavel]
    regras_pendentes = [{"regra": r.identificador, "alvo": r.alvo,
                         "estado": r.estado.value,
                         "expressao": r.expressao}
                        for r in receita.regras_dimensionais if not r.calculavel]
    acessorios_confirmados = [a.identificador for a in receita.regras_acessorios
                              if a.calculavel]
    acessorios_pendentes = [{"regra": a.identificador, "item": a.item,
                             "estado": a.estado.value,
                             "quantidade": a.quantidade_expressao,
                             "posicao": a.posicao}
                            for a in receita.regras_acessorios
                            if not a.calculavel]

    visual = validar_prontidao_para_visualizacao(receita, biblioteca)
    calculo = validar_prontidao_para_calculo(receita, biblioteca)
    producao = validar_prontidao_para_producao(receita, biblioteca)

    return {
        "tipologia": {"codigo": receita.codigo, "nome": receita.nome,
                      "sistema": receita.sistema,
                      "quantidade_folhas": receita.quantidade_folhas,
                      "estado": receita.estado},
        "geometrias": {"disponiveis": disponiveis, "ausentes": ausentes,
                       "total_na_biblioteca": len(codigos)},
        "componentes": {"confirmados": confirmados, "pendentes": pendentes,
                        "total": len(receita.componentes)},
        "regras": {"confirmadas": regras_confirmadas,
                   "pendentes": regras_pendentes,
                   "total": len(receita.regras_dimensionais)},
        "acessorios": {"confirmados": acessorios_confirmados,
                       "pendentes": acessorios_pendentes,
                       "total": len(receita.regras_acessorios)},
        "casos_reais": {
            "recebidos": [c.identificador for c in receita.casos_reais],
            "validados": [c.identificador for c in receita.casos_reais
                          if c.validado],
        },
        "gates": {
            "visualizacao_preliminar": _resumo_gate(visual, "visualizacao_preliminar"),
            "calculo": _resumo_gate(calculo, "calculo"),
            "producao": _resumo_gate(producao, "producao"),
        },
        "aprovacoes_do_especialista": [a.para_dict() for a in receita.aprovacoes],
        "casos_reais_detalhe": [c.para_dict() for c in receita.casos_reais],
        "perguntas_abertas": list(receita.perguntas_abertas),
        "variaveis_disponiveis": list(variaveis_disponiveis()),
        "checklist_serralheria": list(CHECKLIST_SERRALHERIA),
        "fontes": [f.para_dict() for f in receita.fontes],
    }


def relatorio_em_markdown(relatorio: dict) -> str:
    """Mesmo conteúdo, legível no celular — é como o Bruno lê."""
    t = relatorio["tipologia"]
    linhas = [
        f"# {t['nome']}",
        "",
        f"`{t['codigo']}` — sistema {t['sistema']}, "
        f"{t['quantidade_folhas']} folhas",
        "",
        f"**Estado:** {t['estado']}",
        "",
        "## Gates",
        "",
        "| gate | situação | motivo |",
        "|---|---|---|",
    ]
    for nome, g in relatorio["gates"].items():
        situacao = "ABERTO" if g["aberto"] else "BLOQUEADO"
        linhas.append(f"| {nome} | **{situacao}** | {g['motivo']} |")

    g = relatorio["geometrias"]
    linhas += ["", "## Geometrias oficiais", "",
               f"- disponíveis: {len(g['disponiveis'])} "
               f"({', '.join(g['disponiveis']) or '—'})",
               f"- ausentes: {len(g['ausentes'])}"]

    c = relatorio["componentes"]
    linhas += ["", "## Componentes", "",
               f"- confirmados: {len(c['confirmados'])} de {c['total']}",
               f"- pendentes: {len(c['pendentes'])}", ""]
    for p in c["pendentes"]:
        linhas.append(f"  - `{p['perfil']}` — {'; '.join(p['pendencias'])}")

    r = relatorio["regras"]
    linhas += ["", "## Regras dimensionais", "",
               f"- confirmadas: {len(r['confirmadas'])} de {r['total']}",
               f"- pendentes: {len(r['pendentes'])}", ""]
    for p in r["pendentes"]:
        linhas.append(f"  - `{p['alvo']}` — {p['estado']}, sem fórmula")

    a = relatorio["acessorios"]
    linhas += ["", "## Acessórios", "",
               f"- confirmados: {len(a['confirmados'])} de {a['total']}",
               f"- pendentes: {len(a['pendentes'])}", ""]
    for p in a["pendentes"]:
        linhas.append(f"  - `{p['item']}` — {p['estado']}, sem quantidade "
                      f"nem posição")

    cr = relatorio["casos_reais"]
    linhas += ["", "## Casos reais", "",
               f"- recebidos: {len(cr['recebidos'])}",
               f"- validados: {len(cr['validados'])}",
               "", "## Perguntas abertas para o especialista", ""]
    linhas += [f"{i}. {q}" for i, q in
               enumerate(relatorio["perguntas_abertas"], 1)]
    linhas += ["", "## Checklist da visita à serralheria", ""]
    linhas += [f"- [ ] {x}" for x in relatorio["checklist_serralheria"]]
    linhas += ["", "## Variáveis disponíveis", "",
               "| variável | origem | estado |", "|---|---|---|"]
    linhas += [f"| `{v['nome']}` | {v['origem']} | {v['estado']} |"
               for v in relatorio["variaveis_disponiveis"]]
    linhas.append("")
    return "\n".join(linhas)


def perguntas_objetivas(receita: ReceitaTipologia) -> tuple[str, ...]:
    """Só as perguntas — para colar numa mensagem ao especialista."""
    return tuple(receita.perguntas_abertas) or PERGUNTAS_ABERTAS
