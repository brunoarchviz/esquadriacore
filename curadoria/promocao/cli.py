"""CLI da promoção. Sem `--apply`, nada é gravado em `dados/`."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import (auditoria, carregar, construir, finalizacao, integridade,
               journal, transacao)
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


DIR_DADOS = CAMINHO_GEOMETRIAS.parent


def _bloquear_se_journal_pendente(lote: str) -> int | None:
    """Toda operação normal recusa enquanto houver transação não concluída."""
    try:
        pend = journal.pendente(DIR_DADOS, lote)
    except journal.JournalCorrompido as e:
        print(f"journal inutilizável: {e}\n"
              f"rode: python -m curadoria.promocao.cli recuperar --lote {lote}",
              file=sys.stderr)
        return 2
    if pend:
        print(f"journal pendente (estado {pend['estado']}).\n"
              f"rode: python -m curadoria.promocao.cli recuperar --lote {lote}",
              file=sys.stderr)
        return 2
    return None


def _verificador_das_quatro_camadas(cands, lote: str):
    """Relê as QUATRO camadas do disco e roda a verificação unificada.

    Reler é o ponto: verificar o config que estava em memória antes da
    transação provaria apenas que o objeto carregado é coerente consigo mesmo,
    não que o arquivo gravado é."""
    def verificar():
        cfg = carregar.carregar_config_e4b(CAMINHO_CONFIG)
        geo = carregar.carregar_geometrias_oficiais(CAMINHO_GEOMETRIAS)
        assoc = carregar.carregar_associacoes_oficiais(CAMINHO_ASSOCIACOES)
        man = json.loads(auditoria.CAMINHO_MANIFESTO.read_text(encoding="utf-8"))
        return integridade.verificar_integridade_promocao_e4b(
            cfg, geo, assoc, man, cands)
    return verificar


def _finalizacao_auditavel(documentos, cands, lote: str):
    """Callback da transação: retoma a finalização a partir do marco atual."""
    def finalizar(j):
        return finalizacao.retomar_finalizacao(
            j, RAIZ, documentos, _verificador_das_quatro_camadas(cands, lote),
            lote=lote)
    return finalizar


def _manifesto_ausente_mas_dados_promovidos(cfg, geo, assoc, cands) -> bool:
    ids = {g["id"] for g in geo["geometrias"]}
    promovido = all(c.id_geometria in ids for c in cands)
    return promovido and not auditoria.CAMINHO_MANIFESTO.exists()


def _documentos_para_retomada(lote: str):
    """Reconstrói os quatro documentos finais a partir do estado atual.

    A transformação do config é idempotente, então reconstruir sobre um config
    já promovido ou sobre um ainda pré-promoção dá o MESMO documento. É o que
    permite a retomada conferir o resultado contra o hash que o journal
    prometeu, em vez de confiar no que encontrou no disco."""
    cfg, geo, assoc, cands = _carregar_tudo(lote)
    plano = _plano(cands, geo, assoc, lote)
    sim = transacao.simular_promocao(plano, geo, assoc)
    if not sim.ids_criados and not sim.associacoes_criadas:
        # `dados/` já promovido: a simulação viva enxerga 54 -> 54. Os
        # documentos finais precisam da simulação do EVENTO, refeita sobre o
        # estado anterior reconstruído por remoção dos registros do lote.
        geo_antes, assoc_antes = _estado_anterior(geo, assoc, cands)
        plano = _plano(cands, geo_antes, assoc_antes, lote)
        sim = transacao.simular_promocao(plano, geo_antes, assoc_antes)
    docs = finalizacao.planejar_documentos(
        sim, cfg, cands, CAMINHO_GEOMETRIAS, CAMINHO_ASSOCIACOES,
        CAMINHO_CONFIG, lote=lote)
    return docs, cands


def _estado_anterior(geo: dict, assoc: dict, cands):
    """Biblioteca sem os registros do lote — o estado de onde a promoção saiu."""
    ids = {c.id_geometria for c in cands}
    perfis = {carregar.perfil_id_oficial(c.codigo_perfil) for c in cands}
    g = dict(geo, geometrias=[x for x in geo["geometrias"] if x["id"] not in ids])
    a = dict(assoc, associacoes=[x for x in assoc["associacoes"]
                                 if x["perfil_id"] not in perfis])
    return g, a


def cmd_recuperar(args) -> int:
    """Estratégia determinística por estado do journal.

    Antes de DADOS_VALIDOS  -> rollback dos QUATRO artefatos (estratégia A).
    De DADOS_VALIDOS em diante -> retomar a finalização estado a estado
    (estratégia B): os dados já estão válidos no disco e desfazê-los perderia
    trabalho verificado.
    CONCLUIDA -> conferir os quatro hashes e a verificação unificada ANTES de
    limpar. Limpar às cegas confiaria num rótulo."""
    d = None
    try:
        d = journal.ler(journal.caminho_journal(DIR_DADOS, args.lote), RAIZ)
    except journal.JournalCorrompido as e:
        print(f"journal inutilizável: {e}", file=sys.stderr)
        return 1
    if d is None:
        print("recuperação: nada_a_recuperar")
        print("  nenhum journal ou backup pendente")
        return 0

    estado = d["estado"]
    if estado in journal.ESTADOS_FINALIZAVEIS + (journal.CONCLUIDA,):
        print(f"recuperação: estado {estado} — retomando a finalização "
              f"(estratégia B)")
        try:
            docs, cands = _documentos_para_retomada(args.lote)
            rel = finalizacao.retomar_finalizacao(
                journal.caminho_journal(DIR_DADOS, args.lote), RAIZ, docs,
                _verificador_das_quatro_camadas(cands, args.lote),
                lote=args.lote)
        except (finalizacao.FinalizacaoBloqueada, journal.JournalCorrompido) as e:
            print(f"recuperação bloqueada: {e}\n"
                  f"journal e backups preservados", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"retomada falhou: {e}\njournal e backups preservados",
                  file=sys.stderr)
            return 1
        rec = d.get("evento_promocao") or {}
        for p in rel.passos:
            print(f"  {p}")
        print(f"  evento retomado: "
              f"{rec.get('quantidade_antes',{}).get('geometrias')} -> "
              f"{rec.get('quantidade_depois',{}).get('geometrias')} geometrias")
        print("  nenhum journal ou backup pendente")
        return 0

    print(f"recuperação: estado {estado} — desfazendo (estratégia A)")
    try:
        rel = journal.recuperar(DIR_DADOS, RAIZ, args.lote)
    except (journal.JournalCorrompido, journal.RecuperacaoBloqueada) as e:
        print(f"recuperação bloqueada: {e}", file=sys.stderr)
        return 1
    print(f"  {rel['acao']}: restaurados={rel['restaurados']} "
          f"removidos={rel['removidos']}")
    print("  nenhum journal ou backup pendente")
    return 0


def cmd_diagnosticar(args) -> int:
    if (c := _bloquear_se_journal_pendente(args.lote)) is not None:
        return c
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
              f"{L:6.2f} x {A:5.2f} {c.quantidade_pontos_contorno_externo:5d} "
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
    if (c := _bloquear_se_journal_pendente(args.lote)) is not None:
        return c
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
    if (c := _bloquear_se_journal_pendente(args.lote)) is not None:
        return c
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
        # `dados/` promovido com manifesto ausente NÃO é "nada a fazer": a
        # gravação e a auditoria ficariam permanentemente dessincronizadas.
        if _manifesto_ausente_mas_dados_promovidos(cfg, geo, assoc, cands):
            # `promover` NÃO reconstrói em silêncio. Decidir sucesso porque os
            # oito GEOs existem é fraco demais: o config pode não declarar a
            # promoção, uma associação pode apontar errado, um contorno pode ter
            # sido alterado. Reconstruir é operação própria, explícita e
            # auditada.
            print("recusado: dados promovidos e manifesto AUSENTE.\n"
                  "rode: python -m curadoria.promocao.cli "
                  f"reconstruir-manifesto --lote {args.lote} --apply")
            return 2
        print("nada a fazer: estado já promovido e íntegro.")
        return 0

    documentos = finalizacao.planejar_documentos(
        sim, cfg, cands, CAMINHO_GEOMETRIAS, CAMINHO_ASSOCIACOES,
        CAMINHO_CONFIG, lote=args.lote)
    estado, h_antes, h_depois = transacao.aplicar_promocao_transacional(
        plano, CAMINHO_GEOMETRIAS, CAMINHO_ASSOCIACOES, sim, documentos,
        caminho_config=CAMINHO_CONFIG,
        caminho_manifesto=auditoria.CAMINHO_MANIFESTO,
        finalizar=_finalizacao_auditavel(documentos, cands, args.lote),
        raiz=RAIZ, lote=args.lote)
    if not estado.aplicado:
        print(f"ROLLBACK executado — arquivos restaurados. Causa: {estado.detalhe}")
        return 1
    caminho = auditoria.CAMINHO_MANIFESTO
    print("PROMOÇÃO APLICADA")
    print(transacao.gerar_resumo_diff(sim))
    for k, v in h_depois.items():
        print(f"  {Path(k).name}: {v[:16]}")
    print(f"  manifesto: {caminho.relative_to(RAIZ)}")
    if estado.limpeza_pendente:
        print(f"\nATENÇÃO: promoção CONCLUÍDA, mas a LIMPEZA falhou.\n"
              f"  {estado.detalhe}\n"
              f"  Os quatro artefatos estão no estado final e validados.\n"
              f"  rode: python -m curadoria.promocao.cli recuperar "
              f"--lote {args.lote}")
        return 3
    return 0


def cmd_reconstruir_manifesto(args) -> int:
    """Recria o manifesto ausente — explicitamente, e sem tocar em mais nada.

    Antes isto acontecia dentro de `promover`, decidindo sucesso só porque os
    oito GEOs existiam. Fraco demais: o config podia não declarar a promoção,
    uma associação podia apontar para o GEO errado, um contorno podia ter sido
    alterado. Aqui a coerência das três camadas é conferida ANTES de escrever, e
    o manifesto recém-criado é removido se a verificação final reprovar."""
    if not args.apply:
        print("recusado: `reconstruir-manifesto` exige --apply explícito.")
        return 2
    if (c := _bloquear_se_journal_pendente(args.lote)) is not None:
        return c

    caminho = auditoria.CAMINHO_MANIFESTO
    if caminho.exists():
        print(f"recusado: o manifesto já existe em {caminho.relative_to(RAIZ)}.\n"
              "Este comando só recria manifesto AUSENTE — sobrescrever seria "
              "apagar o registro do evento.")
        return 2

    cfg, geo, assoc, cands = _carregar_tudo(args.lote)

    # Coerência das três camadas SEM depender do manifesto: se `dados/` não
    # sustenta a promoção, reconstruir a auditoria seria fabricar evidência.
    val = _validar_todos(cands, cfg)
    if not val.ok:
        print("validação dos candidatos REPROVADA — nada gravado:\n"
              + val.descrever())
        return 1
    perm = integridade.verificar_permanencia_atual_e4b(cfg, geo, assoc, cands)
    if not perm.ok:
        print("estado atual não sustenta a promoção — manifesto NÃO criado:\n"
              + perm.descrever())
        return 1

    geo_antes, assoc_antes = _estado_anterior(geo, assoc, cands)
    sim = transacao.simular_promocao(
        _plano(cands, geo_antes, assoc_antes, args.lote), geo_antes, assoc_antes)
    # Os fatos vêm de evento.py: uma reconstrução não muda o que aconteceu, e
    # `reconstruido_apos_gravacao` continua false porque descreve o evento.
    man = auditoria.construir_manifesto(sim, cfg, lote=args.lote)
    auditoria.gravar_manifesto(man)

    relido = json.loads(caminho.read_text(encoding="utf-8"))
    unif = integridade.verificar_integridade_promocao_e4b(
        cfg, geo, assoc, relido, cands)
    if not unif.ok:
        caminho.unlink()
        journal.sincronizar_diretorio(caminho.parent)
        print("verificação unificada REPROVOU — manifesto removido:\n"
              + unif.descrever(), file=sys.stderr)
        return 1

    print("MANIFESTO RECONSTRUÍDO")
    print(f"  {caminho.relative_to(RAIZ)}")
    print(f"  evento: {man['quantidade_antes']['geometrias']} -> "
          f"{man['quantidade_depois']['geometrias']} geometrias, "
          f"{man['quantidade_antes']['associacoes']} -> "
          f"{man['quantidade_depois']['associacoes']} associações")
    print(f"  reconstruido_apos_gravacao: {man['reconstruido_apos_gravacao']} "
          f"(o campo descreve o evento, não esta operação)")
    print("  verificação unificada: APROVADA")
    return 0


def cmd_verificar(args) -> int:
    if (c := _bloquear_se_journal_pendente(args.lote)) is not None:
        return c
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
    # verificação unificada das quatro camadas
    man = {}
    if auditoria.CAMINHO_MANIFESTO.exists():
        man = json.loads(auditoria.CAMINHO_MANIFESTO.read_text(encoding="utf-8"))
    else:
        problemas.append("manifesto ausente — rode `promover --apply` para reconstruir")
    unif = integridade.verificar_integridade_promocao_e4b(cfg, geo, assoc, man, cands)
    print(f"verificação unificada (config/dados/associações/manifesto): "
          f"{'APROVADA' if unif.ok else 'REPROVADA'}")
    if not unif.ok:
        print(unif.descrever())

    if problemas or not unif.ok:
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
                            ("verificar", cmd_verificar, "confere o estado promovido"),
                            ("recuperar", cmd_recuperar,
                             "desfaz transação interrompida (journal pendente)"),
                            ("reconstruir-manifesto", cmd_reconstruir_manifesto,
                             "recria manifesto AUSENTE (exige --apply)")):
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("--lote", default="E4B", choices=sorted(LOTES))
        p.add_argument("--json", action="store_true", help="relatório em JSON")
        if nome == "reconstruir-manifesto":
            p.add_argument("--apply", action="store_true",
                           help="confirma a criação do manifesto")
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
