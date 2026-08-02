"""CLI da promoção. Sem `--apply`, nada é gravado em `dados/`."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import auditoria, carregar, construir, transacao
from .carregar import (CAMINHO_ASSOCIACOES, CAMINHO_CONFIG, CAMINHO_GEOMETRIAS,
                       RAIZ, PromocaoErro, hash_arquivo)
from .modelos import LOTES
from .validar import validar_candidato_completo


def _plano(candidatos, geo, assoc, lote="E4B"):
    return construir.construir_plano_promocao(candidatos, geo, assoc, lote)


def _carregar_tudo(lote: str):
    cfg = carregar.carregar_config_e4b(CAMINHO_CONFIG)
    geo = carregar.carregar_geometrias_oficiais(CAMINHO_GEOMETRIAS)
    assoc = carregar.carregar_associacoes_oficiais(CAMINHO_ASSOCIACOES)
    cands = carregar.montar_candidatos(cfg, lote)
    return cfg, geo, assoc, cands


def _validar_todos(cands, cfg):
    from .modelos import ResultadoValidacao
    r = ResultadoValidacao.aprovado()
    for c in cands:
        r = r.somar(validar_candidato_completo(c, cfg))
    return r


def _arvore_suja() -> list[str]:
    """Só arquivos RASTREADOS modificados bloqueiam. Os `??` antigos não."""
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                         cwd=RAIZ, capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if l.strip()]


def cmd_diagnosticar(args) -> int:
    cfg, geo, assoc, cands = _carregar_tudo(args.lote)
    print(f"lote {args.lote}: {len(cands)} candidatos")
    print(f"biblioteca oficial: {len(geo['geometrias'])} geometrias, "
          f"{len(assoc['associacoes'])} associações")
    print(f"hash geometrias : {hash_arquivo(CAMINHO_GEOMETRIAS)[:16]}")
    print(f"hash associacoes: {hash_arquivo(CAMINHO_ASSOCIACOES)[:16]}")
    print()
    print(f"{'perfil':9s} {'GEO':13s} {'dimensão':>14s} {'pts':>5s} {'vaz':>4s}  estado")
    for c in cands:
        L, A = c.dimensao_nominal_mm
        print(f"{c.codigo_perfil:9s} {c.id_geometria:13s} "
              f"{L:6.2f} x {A:5.2f} {c.quantidade_componentes:5d} "
              f"{c.quantidade_vazios:4d}  {c.estado_curadoria}")
    val = _validar_todos(cands, cfg)
    print()
    print("validação dos candidatos:", "APROVADA" if val.ok else "REPROVADA")
    if not val.ok:
        print(val.descrever())
        return 1
    plano = _plano(cands, geo, assoc, args.lote)
    print(f"colisões bloqueantes: {len(plano.bloqueios)}")
    for c in plano.conflitos:
        print(f"  [{'BLOQUEIO' if c.bloqueante else 'aviso'}] {c.tipo}: "
              f"{c.identificador} — {c.detalhe}")
    return 0


def cmd_simular(args) -> int:
    cfg, geo, assoc, cands = _carregar_tudo(args.lote)
    val = _validar_todos(cands, cfg)
    if not val.ok:
        print("validação REPROVADA:\n" + val.descrever())
        return 1
    plano = _plano(cands, geo, assoc, args.lote)
    sim = transacao.simular_promocao(plano, geo, assoc)
    print("SIMULAÇÃO (nada foi gravado)")
    print(transacao.gerar_resumo_diff(sim))
    idem = transacao.verificar_idempotencia_simulada(
        sim, cands, lambda c, g, a: _plano(c, g, a, args.lote))
    print(f"  idempotência : {'APROVADA' if idem.ok else 'REPROVADA'}")
    if not sim.validacao.ok:
        print(sim.validacao.descrever())
    if args.json:
        print(json.dumps({
            "ids_criados": list(sim.ids_criados),
            "associacoes_criadas": list(sim.associacoes_criadas),
            "registros_antigos_alterados": list(sim.registros_antigos_alterados),
            "bloqueios": len(plano.bloqueios),
            "idempotente": idem.ok,
        }, ensure_ascii=False, indent=2))
    if sim.vazio_util if hasattr(sim, "vazio_util") else False:
        pass
    if not sim.ids_criados and not sim.associacoes_criadas:
        print("  estado já promovido e íntegro (diff vazio)")
    return 0 if (sim.aprovada and idem.ok) else 1


def cmd_promover(args) -> int:
    if not args.apply:
        print("recusado: `promover` exige --apply explícito. "
              "Use `simular` para inspecionar sem gravar.")
        return 2
    sujos = _arvore_suja()
    if sujos and not args.permitir_arvore_suja:
        print("recusado: há arquivos RASTREADOS modificados:\n  "
              + "\n  ".join(sujos))
        return 2

    cfg, geo, assoc, cands = _carregar_tudo(args.lote)
    val = _validar_todos(cands, cfg)
    if not val.ok:
        print("validação REPROVADA — nada gravado:\n" + val.descrever())
        return 1
    plano = _plano(cands, geo, assoc, args.lote)
    sim = transacao.simular_promocao(plano, geo, assoc)
    if not sim.aprovada:
        print("simulação REPROVADA — nada gravado:\n" + sim.validacao.descrever())
        return 1
    idem = transacao.verificar_idempotencia_simulada(
        sim, cands, lambda c, g, a: _plano(c, g, a, args.lote))
    if not idem.ok:
        print("idempotência REPROVADA — nada gravado:\n" + idem.descrever())
        return 1

    if not sim.ids_criados and not sim.associacoes_criadas:
        print("nada a fazer: estado já promovido e íntegro.")
        return 0

    estado, h_antes, h_depois = transacao.aplicar_promocao_transacional(
        plano, CAMINHO_GEOMETRIAS, CAMINHO_ASSOCIACOES, sim)
    if not estado.aplicado:
        print(f"ROLLBACK executado — arquivos restaurados. Causa: {estado.detalhe}")
        return 1

    man = auditoria.construir_manifesto(
        sim, h_antes, h_depois, cfg,
        resultado_idempotencia="APROVADA",
        resultado_rollback="coberto por regressão (tests/test_promocao.py)",
        lote=args.lote)
    caminho = auditoria.gravar_manifesto(man)
    print("PROMOÇÃO APLICADA")
    print(transacao.gerar_resumo_diff(sim))
    for k, v in h_depois.items():
        print(f"  {Path(k).name}: {v[:16]}")
    print(f"  manifesto: {caminho.relative_to(RAIZ)}")
    return 0


def cmd_verificar(args) -> int:
    cfg, geo, assoc, cands = _carregar_tudo(args.lote)
    ids = {g["id"] for g in geo["geometrias"]}
    perfis = {a["perfil_id"]: a["geometria_padrao_id"] for a in assoc["associacoes"]}
    problemas = []

    for c in cands:
        if c.id_geometria not in ids:
            problemas.append(f"{c.codigo_perfil}: {c.id_geometria} ausente da biblioteca")
        pid = carregar.perfil_id_oficial(c.codigo_perfil)
        if pid not in perfis:
            problemas.append(f"{c.codigo_perfil}: associação {pid} ausente")
        elif perfis[pid] != c.id_geometria:
            problemas.append(f"{c.codigo_perfil}: {pid} aponta para {perfis[pid]}")

    orfas = [p for p, g in perfis.items() if g not in ids]
    if orfas:
        problemas.append(f"associações órfãs: {orfas}")
    if "GEO-TMS-102" in ids:
        problemas.append("GEO-TMS-102 existe — duplicaria o SU-102")

    # o contrato tem de conseguir carregar tudo
    try:
        from contrato.consumo import carregar_biblioteca
        bib = carregar_biblioteca(str(CAMINHO_GEOMETRIAS), str(CAMINHO_ASSOCIACOES))
        carregadas = len(bib.geometrias)
    except Exception as e:
        problemas.append(f"contrato de consumo falhou: {e}")
        carregadas = -1

    print(f"geometrias oficiais : {len(ids)}")
    print(f"associações oficiais: {len(perfis)}")
    print(f"carregadas pelo contrato: {carregadas}")
    print(f"os {len(cands)} perfis do lote: "
          f"{sum(1 for c in cands if c.id_geometria in ids)} presentes")
    print(f"associações órfãs   : {len(orfas)}")
    print(f"GEO-TMS-102 criado  : {'GEO-TMS-102' in ids}")
    if problemas:
        print("\nPROBLEMAS:")
        for p in problemas:
            print("  -", p)
        return 1
    print("\nverificação APROVADA")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="curadoria.promocao.cli",
                                 description="Promoção de candidatos curados para dados/.")
    sub = ap.add_subparsers(dest="comando", required=True)
    for nome, fn, ajuda in (("diagnosticar", cmd_diagnosticar, "inspeciona sem gravar"),
                            ("simular", cmd_simular, "simula a promoção sem gravar"),
                            ("promover", cmd_promover, "grava em dados/ (exige --apply)"),
                            ("verificar", cmd_verificar, "confere o estado promovido")):
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("--lote", default="E4B", choices=sorted(LOTES))
        p.add_argument("--json", action="store_true", help="relatório em JSON")
        if nome == "promover":
            p.add_argument("--apply", action="store_true",
                           help="confirma a gravação em dados/")
            p.add_argument("--permitir-arvore-suja", action="store_true",
                           dest="permitir_arvore_suja")
        p.set_defaults(func=fn)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except PromocaoErro as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
