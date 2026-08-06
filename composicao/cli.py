"""CLI da composição. Nada aqui calcula corte, vidro, folga ou acessório.

Não existe comando `calcular` — e não vai existir enquanto o gate de cálculo
estiver bloqueado. Um comando que devolvesse números com regras `PENDENTE`
produziria lista de corte inventada.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import fontes, prontidao, receita as receita_mod, validar
from .modelos import ReceitaErro

TIPOLOGIAS = {receita_mod.CODIGO_TIPOLOGIA: receita_mod.construir_receita_preliminar}


def _receita(codigo: str):
    try:
        return TIPOLOGIAS[codigo]()
    except KeyError:
        raise ReceitaErro(f"tipologia desconhecida: {codigo!r} "
                          f"(conhecidas: {sorted(TIPOLOGIAS)})")


def cmd_diagnosticar(args) -> int:
    rec = _receita(args.tipologia)
    bib = fontes.carregar_biblioteca_oficial()
    codigos = {g.codigo for g in bib.geometrias}
    presentes = [p for p in rec.perfis_disponiveis
                 if p.id_geometria in codigos]

    print(f"tipologia: {rec.codigo} — {rec.nome}")
    print(f"sistema  : {rec.sistema}, {rec.quantidade_folhas} folhas")
    print(f"estado   : {rec.estado}")
    print()
    print(f"{len(presentes)} de {len(rec.perfis_disponiveis)} geometrias "
          f"oficiais disponíveis (biblioteca com {len(codigos)})")
    print()
    print("INVENTÁRIO — perfis disponíveis para a tipologia")
    print(f"{'perfil':9s} {'GEO':14s} {'associação':16s} ocorrências")
    for ref in rec.perfis_disponiveis:
        marca = "" if ref.id_geometria in codigos else "  <-- AUSENTE"
        ocorrencias = rec.componentes_do_perfil(ref.codigo_perfil)
        print(f"{ref.codigo_perfil:9s} {ref.id_geometria:14s} "
              f"{ref.perfil_id_oficial:16s} {len(ocorrencias)}{marca}")
    print()
    print(f"OCORRÊNCIAS funcionais registradas: {len(rec.componentes)}")
    print("  (um perfil pode exercer vários papéis; quantas ocorrências "
          "existem é o que falta descobrir)")
    for c in rec.componentes:
        qtd = "-" if c.quantidade is None else str(c.quantidade)
        print(f"  {c.identificador:28s} {c.perfil.codigo_perfil:9s} "
              f"{c.papel.value:24s} {qtd:>4s}  {c.estado.value}")

    refs = validar.validar_referencias_geometricas(rec, bib)
    print()
    print(f"referências geométricas: {'APROVADAS' if refs.ok else 'REPROVADAS'}")
    if not refs.ok:
        print(refs.descrever())
    print()
    print(f"papéis funcionais  : "
          f"{len([c for c in rec.componentes if c.confirmado])}"
          f"/{len(rec.componentes)} ocorrências confirmadas")
    print(f"regras de corte    : "
          f"{len([r for r in rec.regras_corte if r.calculavel])}"
          f"/{len(rec.regras_corte)} confirmadas")
    print(f"regras de vidro    : "
          f"{len([r for r in rec.regras_vidro if r.calculavel])}"
          f"/{len(rec.regras_vidro)} confirmadas")
    print(f"acessórios         : {len(rec.regras_acessorios)} regras")
    print(f"casos reais        : {len(rec.casos_reais)}")
    return 0 if refs.ok else 1


def cmd_validar_ficha(args) -> int:
    caminho = Path(args.caminho)
    try:
        dados = fontes.carregar_ficha_campo(caminho)
    except ReceitaErro as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1

    estrutura = fontes.validar_estrutura_ficha(dados, str(caminho))
    print(f"ficha: {caminho}")
    print(f"estrutura: {'VÁLIDA' if estrutura.ok else 'INVÁLIDA'}")
    if not estrutura.ok:
        print(estrutura.descrever())

    # Preenchido nao e confirmado: sao contagens diferentes de proposito.
    preenchidos = fontes.extrair_campos_preenchidos(dados)
    confirmadas = fontes.extrair_decisoes_confirmadas(dados)
    pendencias = fontes.extrair_pendencias(dados)
    print(f"campos preenchidos  : {len(preenchidos)}")
    for d in preenchidos[:20]:
        print(f"  {d['escopo']}.{d['campo']} = {d['valor']!r}")
    if len(preenchidos) > 20:
        print(f"  ... e mais {len(preenchidos) - 20}")
    print(f"decisões confirmadas: {len(confirmadas)}"
          f"  (valor + estado confirmado + fonte + autoria)")
    for d in confirmadas[:20]:
        print(f"  {d['escopo']}.{d['campo']} = {d['valor']!r} "
              f"[{d['estado']}]")
    print(f"pendências: {len(pendencias)}")
    for p in pendencias[:20]:
        print(f"  {p['escopo']}.{p['campo']}")
    if len(pendencias) > 20:
        print(f"  ... e mais {len(pendencias) - 20}")

    if estrutura.ok:
        try:
            caso = fontes.converter_ficha_em_caso_real(dados, str(caminho))
        except ReceitaErro as e:
            print(f"erro na conversão: {e}", file=sys.stderr)
            return 1
        ident = caso.identificador or "NAO_INFORMADO"
        # Estado de RECEBIMENTO. "VALIDADO" não sai daqui: depende de fonte
        # apta e de integridade, conferidas no gate de produção.
        print(f"caso real: {ident} — {caso.estado_recebimento}")
        print(f"  seções preenchidas: "
              f"{', '.join(caso.secoes_preenchidas) or 'nenhuma'}")
        largura = ("NAO_INFORMADO" if caso.largura_total_mm is None
                   else f"{caso.largura_total_mm} mm")
        altura = ("NAO_INFORMADO" if caso.altura_total_mm is None
                  else f"{caso.altura_total_mm} mm")
        print(f"  largura: {largura}")
        print(f"  altura : {altura}")
    if args.json:
        print(json.dumps({"estrutura_valida": estrutura.ok,
                          "campos_preenchidos": len(preenchidos),
                          "decisoes_confirmadas": len(confirmadas),
                          "pendencias": [f"{p['escopo']}.{p['campo']}"
                                         for p in pendencias]},
                         ensure_ascii=False, indent=2))
    return 0 if estrutura.ok else 1


def cmd_registrar_evidencia(args) -> int:
    """Calcula o hash de um artefato para você COLAR na ficha.

    Não edita a ficha: registrar evidência é ato do especialista, e um comando
    que escrevesse sozinho poderia carimbar como conferido um arquivo que
    ninguém olhou."""
    import hashlib
    raiz = fontes.RAIZ
    alvo = Path(args.caminho)
    if alvo.is_absolute():
        try:
            relativo = alvo.resolve().relative_to(raiz)
        except ValueError:
            print(f"erro: {alvo} está fora do repositório ({raiz})",
                  file=sys.stderr)
            return 1
    else:
        relativo = alvo
    completo = (raiz / relativo).resolve()
    if not str(completo).startswith(str(raiz.resolve())):
        print(f"erro: caminho resolve fora da raiz do repositório: {relativo}",
              file=sys.stderr)
        return 1
    if not completo.is_file():
        print(f"erro: arquivo inexistente ou não regular: {relativo}",
              file=sys.stderr)
        return 1

    dados = completo.read_bytes()
    print(f"# cole em fontes: — id_fonte {args.id_fonte or '<defina>'}")
    print(f"referencia: {relativo.as_posix()}")
    print(f"sha256: {hashlib.sha256(dados).hexdigest()}")
    print(f"tamanho_bytes: {len(dados)}")
    return 0


def cmd_prontidao(args) -> int:
    rec = _receita(args.tipologia)
    bib = fontes.carregar_biblioteca_oficial()
    rel = prontidao.gerar_relatorio_prontidao(rec, bib)

    if args.json:
        print(json.dumps(rel, ensure_ascii=False, indent=2))
        return 0
    if args.markdown:
        print(prontidao.relatorio_em_markdown(rel))
        return 0

    g, c, r = rel["geometrias"], rel["componentes"], rel["regras"]
    print(f"{len(g['disponiveis'])} geometrias oficiais disponíveis")
    print(f"receita preliminar carregada ({rel['tipologia']['estado']})")
    print(f"papéis funcionais: {len(c['pendentes'])} pendentes de {c['total']}")
    print(f"regras de corte  : {len([x for x in r['pendentes'] if 'corte' in x['alvo'] or 'folha' in x['alvo']])} pendentes")
    print(f"regras de vidro  : {len([x for x in r['pendentes'] if 'vidro' in x['alvo']])} pendentes")
    a = rel["acessorios"]
    print(f"acessórios       : {len(a['pendentes'])} pendentes de {a['total']}")
    print(f"casos reais      : {len(rel['casos_reais']['recebidos'])} recebidos, "
          f"{len(rel['casos_reais']['validados'])} validados")
    print()
    for nome, gate in rel["gates"].items():
        print(f"gate de {nome}: {'ABERTO' if gate['aberto'] else 'BLOQUEADO'}")
        for b in gate["bloqueios"][:5]:
            print(f"    - {b}")
        if len(gate["bloqueios"]) > 5:
            print(f"    ... e mais {len(gate['bloqueios']) - 5}")
    print()
    print("perguntas abertas para o especialista:")
    for i, q in enumerate(rel["perguntas_abertas"], 1):
        print(f"  {i}. {q}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="composicao.cli",
        description="Receita de tipologia — infraestrutura preliminar. "
                    "Não calcula corte, vidro, folga nem acessório.")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("diagnosticar", help="estado da receita e das referências")
    p.add_argument("--tipologia", default=receita_mod.CODIGO_TIPOLOGIA,
                   choices=sorted(TIPOLOGIAS))
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_diagnosticar)

    p = sub.add_parser("validar-ficha", help="valida a ficha preenchida")
    p.add_argument("caminho")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_validar_ficha)

    p = sub.add_parser("registrar-evidencia",
                       help="calcula sha256 de um artefato (não edita a ficha)")
    p.add_argument("caminho")
    p.add_argument("--id-fonte", dest="id_fonte", default=None)
    p.set_defaults(func=cmd_registrar_evidencia)

    p = sub.add_parser("prontidao", help="relatório de gates e pendências")
    p.add_argument("--tipologia", default=receita_mod.CODIGO_TIPOLOGIA,
                   choices=sorted(TIPOLOGIAS))
    p.add_argument("--json", action="store_true")
    p.add_argument("--markdown", action="store_true")
    p.set_defaults(func=cmd_prontidao)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ReceitaErro as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
