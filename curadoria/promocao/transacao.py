"""Simulação, escrita atômica e rollback.

A simulação nunca toca o disco. A escrita real usa temporário no MESMO
filesystem do destino, para que `os.replace` seja atômico."""
from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from pathlib import Path

from .carregar import calcular_hash_canonico, hash_arquivo
from .modelos import (EstadoTransacao, PlanoPromocao, ResultadoSimulacao,
                      ResultadoValidacao)


# ---------------------------------------------------------------------------
# Simulação (em memória)
# ---------------------------------------------------------------------------

def _aplicar_plano_em_memoria(plano: PlanoPromocao, geometrias: dict,
                              associacoes: dict) -> tuple[dict, dict]:
    g = copy.deepcopy(geometrias)
    a = copy.deepcopy(associacoes)
    g["geometrias"] = list(g["geometrias"]) + [p.registro for p in plano.geometrias_novas]
    a["associacoes"] = list(a["associacoes"]) + [x.registro for x in plano.associacoes_novas]
    return g, a


def verificar_preservacao_registros_existentes(antes: dict, depois: dict,
                                               chave: str, id_campo: str,
                                               ids_novos: set) -> tuple:
    """Devolve a lista de registros antigos que MUDARAM. Deve ser vazia."""
    orig = {r[id_campo]: calcular_hash_canonico(r) for r in antes[chave]}
    alterados = []
    for r in depois[chave]:
        ident = r[id_campo]
        if ident in ids_novos:
            continue
        if ident in orig and calcular_hash_canonico(r) != orig[ident]:
            alterados.append(ident)
    for ident in orig:
        if ident not in {r[id_campo] for r in depois[chave]}:
            alterados.append(f"{ident} (removido)")
    return tuple(alterados)


def gerar_diff_estrutural(antes: dict, depois: dict) -> dict:
    return {
        "geometrias_antes": len(antes["geometrias"]["geometrias"]),
        "geometrias_depois": len(depois["geometrias"]["geometrias"]),
        "associacoes_antes": len(antes["associacoes"]["associacoes"]),
        "associacoes_depois": len(depois["associacoes"]["associacoes"]),
    }


def simular_promocao(plano: PlanoPromocao, geometrias_atuais: dict,
                     associacoes_atuais: dict) -> ResultadoSimulacao:
    g2, a2 = _aplicar_plano_em_memoria(plano, geometrias_atuais, associacoes_atuais)

    ids_novos = {p.id for p in plano.geometrias_novas}
    perfis_novos = {x.perfil_id for x in plano.associacoes_novas}

    alterados = verificar_preservacao_registros_existentes(
        geometrias_atuais, g2, "geometrias", "id", ids_novos)
    alterados += verificar_preservacao_registros_existentes(
        associacoes_atuais, a2, "associacoes", "perfil_id", perfis_novos)

    val = ResultadoValidacao.aprovado()
    if alterados:
        val = val.somar(ResultadoValidacao.reprovado(
            "-", "registros oficiais anteriores foram alterados",
            list(alterados), [], "dados/"))
    for c in plano.bloqueios:
        val = val.somar(ResultadoValidacao.reprovado(
            c.perfil, c.tipo, c.identificador, "sem conflito", "dados/"))

    # órfãs: toda associação tem de apontar para geometria existente
    ids_depois = {x["id"] for x in g2["geometrias"]}
    orfas = [x["perfil_id"] for x in a2["associacoes"]
             if x["geometria_padrao_id"] not in ids_depois]
    if orfas:
        val = val.somar(ResultadoValidacao.reprovado(
            "-", "associação órfã após a promoção", orfas, [], "dados/"))

    return ResultadoSimulacao(
        plano=plano,
        geometrias_antes=len(geometrias_atuais["geometrias"]),
        geometrias_depois=len(g2["geometrias"]),
        associacoes_antes=len(associacoes_atuais["associacoes"]),
        associacoes_depois=len(a2["associacoes"]),
        ids_criados=tuple(p.id for p in plano.geometrias_novas),
        ids_reutilizados=tuple(plano.geometrias_reutilizadas),
        associacoes_criadas=tuple(x.perfil_id for x in plano.associacoes_novas),
        associacoes_reutilizadas=tuple(plano.associacoes_reutilizadas),
        registros_antigos_alterados=tuple(alterados),
        avisos=tuple(f"{c.tipo}: {c.identificador}"
                     for c in plano.conflitos if not c.bloqueante),
        validacao=val,
        geometrias_depois_doc=g2,
        associacoes_depois_doc=a2,
    )


def verificar_idempotencia_simulada(simulacao: ResultadoSimulacao,
                                    candidatos, construir_plano) -> ResultadoValidacao:
    """Reaplica o plano sobre o estado JÁ promovido: tem de dar diff vazio."""
    plano2 = construir_plano(candidatos, simulacao.geometrias_depois_doc,
                             simulacao.associacoes_depois_doc)
    sim2 = simular_promocao(plano2, simulacao.geometrias_depois_doc,
                            simulacao.associacoes_depois_doc)
    if sim2.ids_criados or sim2.associacoes_criadas:
        return ResultadoValidacao.reprovado(
            "-", "segunda aplicação não é idempotente",
            {"ids": list(sim2.ids_criados), "assoc": list(sim2.associacoes_criadas)},
            {"ids": [], "assoc": []}, "dados/")
    return ResultadoValidacao.aprovado()


def gerar_resumo_diff(sim: ResultadoSimulacao) -> str:
    return "\n".join([
        f"  geometrias   : {sim.geometrias_antes} -> {sim.geometrias_depois}",
        f"  associacoes  : {sim.associacoes_antes} -> {sim.associacoes_depois}",
        f"  IDs criados  : {len(sim.ids_criados)} {list(sim.ids_criados)}",
        f"  IDs reusados : {len(sim.ids_reutilizados)} {list(sim.ids_reutilizados)}",
        f"  assoc criadas: {len(sim.associacoes_criadas)}",
        f"  assoc reusadas: {len(sim.associacoes_reutilizadas)}",
        f"  antigos alterados: {len(sim.registros_antigos_alterados)}",
        f"  bloqueios    : {len(sim.plano.bloqueios)}",
        f"  avisos       : {len(sim.avisos)}",
    ])


# ---------------------------------------------------------------------------
# Escrita atômica
# ---------------------------------------------------------------------------

def criar_backup_temporario(caminhos, diretorio_temporario: Path) -> dict:
    backups = {}
    for c in caminhos:
        destino = Path(diretorio_temporario) / (Path(c).name + ".bak")
        shutil.copy2(c, destino)
        backups[Path(c)] = destino
    return backups


def escrever_json_temporario(destino: Path, conteudo: object) -> Path:
    """Grava ao lado do destino (mesmo filesystem) para permitir os.replace."""
    destino = Path(destino)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=destino.name + ".",
                               suffix=".tmp")
    os.close(fd)
    tmp = Path(tmp)
    tmp.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    sincronizar_arquivo(tmp)
    return tmp


def sincronizar_arquivo(caminho: Path) -> None:
    with open(caminho, "rb") as f:
        os.fsync(f.fileno())


def substituir_atomico(temporario: Path, destino: Path) -> None:
    os.replace(temporario, destino)


def restaurar_backup(backups: dict) -> None:
    for destino, bak in backups.items():
        shutil.copy2(bak, destino)


def validar_pos_gravacao(caminho_geo: Path, caminho_assoc: Path,
                         plano: PlanoPromocao) -> ResultadoValidacao:
    """Relê os arquivos do disco e confere o que ficou lá."""
    try:
        g = json.loads(Path(caminho_geo).read_text(encoding="utf-8"))
        a = json.loads(Path(caminho_assoc).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return ResultadoValidacao.reprovado(
            "-", "JSON parcial ou corrompido após a gravação", str(e), "JSON válido",
            str(caminho_geo))

    ids = {x["id"] for x in g["geometrias"]}
    for p in plano.geometrias_novas:
        if p.id not in ids:
            return ResultadoValidacao.reprovado(
                p.codigo_perfil, "geometria ausente após a gravação", None, p.id,
                str(caminho_geo))
    perfis = {x["perfil_id"] for x in a["associacoes"]}
    for x in plano.associacoes_novas:
        if x.perfil_id not in perfis:
            return ResultadoValidacao.reprovado(
                x.codigo_perfil, "associação ausente após a gravação", None,
                x.perfil_id, str(caminho_assoc))
    orfas = [x["perfil_id"] for x in a["associacoes"]
             if x["geometria_padrao_id"] not in ids]
    if orfas:
        return ResultadoValidacao.reprovado(
            "-", "associação órfã após a gravação", orfas, [], str(caminho_assoc))
    return ResultadoValidacao.aprovado()


def aplicar_promocao_transacional(plano: PlanoPromocao, caminho_geo: Path,
                                  caminho_assoc: Path, simulacao: ResultadoSimulacao,
                                  falha_injetada: str = "") -> tuple[EstadoTransacao, dict, dict]:
    """Grava os dois arquivos ou restaura ambos. Nunca deixa estado parcial.

    `falha_injetada` existe para o teste de rollback exercitar o caminho de
    erro de verdade — não é usada em execução normal."""
    caminho_geo, caminho_assoc = Path(caminho_geo), Path(caminho_assoc)
    hash_antes = {str(caminho_geo): hash_arquivo(caminho_geo),
                  str(caminho_assoc): hash_arquivo(caminho_assoc)}

    with tempfile.TemporaryDirectory() as td:
        backups = criar_backup_temporario([caminho_geo, caminho_assoc], Path(td))
        tmp_geo = tmp_assoc = None
        try:
            tmp_geo = escrever_json_temporario(caminho_geo, simulacao.geometrias_depois_doc)
            if falha_injetada == "apos_primeiro_temporario":
                raise RuntimeError("falha injetada: após o primeiro temporário")
            tmp_assoc = escrever_json_temporario(caminho_assoc, simulacao.associacoes_depois_doc)

            # relê os temporários antes de substituir qualquer destino
            for t in (tmp_geo, tmp_assoc):
                json.loads(t.read_text(encoding="utf-8"))

            substituir_atomico(tmp_geo, caminho_geo)
            tmp_geo = None
            if falha_injetada == "entre_os_dois_replaces":
                raise RuntimeError("falha injetada: entre os dois replaces")
            substituir_atomico(tmp_assoc, caminho_assoc)
            tmp_assoc = None

            if falha_injetada == "na_validacao_pos_gravacao":
                raise RuntimeError("falha injetada: na validação pós-gravação")
            val = validar_pos_gravacao(caminho_geo, caminho_assoc, plano)
            if not val.ok:
                raise RuntimeError("validação pós-gravação reprovou:\n"
                                   + val.descrever())

            hash_depois = {str(caminho_geo): hash_arquivo(caminho_geo),
                           str(caminho_assoc): hash_arquivo(caminho_assoc)}
            return (EstadoTransacao(backups={}, aplicado=True,
                                    rollback_executado=False),
                    hash_antes, hash_depois)

        except Exception as e:                      # rollback dos DOIS arquivos
            restaurar_backup(backups)
            for t in (tmp_geo, tmp_assoc):
                if t is not None and Path(t).exists():
                    Path(t).unlink()
            depois = {str(caminho_geo): hash_arquivo(caminho_geo),
                      str(caminho_assoc): hash_arquivo(caminho_assoc)}
            if depois != hash_antes:
                raise RuntimeError(
                    f"ROLLBACK INCOMPLETO — hashes não voltaram ao original.\n"
                    f"antes={hash_antes}\ndepois={depois}\ncausa={e}") from e
            return (EstadoTransacao(backups={}, aplicado=False,
                                    rollback_executado=True, detalhe=str(e)),
                    hash_antes, depois)
