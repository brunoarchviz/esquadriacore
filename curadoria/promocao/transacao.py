"""Simulação, escrita e rollback da promoção.

A simulação nunca toca o disco. A escrita usa temporário no MESMO filesystem do
destino, para que `os.replace` seja atômico.

Precisão sobre atomicidade — cada substituição é atômica POR ARQUIVO; o par de
`os.replace` NÃO é um commit atômico conjunto. Ver `journal.py`, que cobre a
janela entre os dois para o caso em que o processo é morto e nenhum `except`
chega a rodar."""
from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from pathlib import Path

from . import evento, journal
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


def detectar_indentacao(caminho: Path, padrao: int = 1) -> int:
    """Indentação já usada pelo arquivo oficial.

    Reescrever 24 mil linhas só porque o serializador tem outro default
    produziria um diff impossível de revisar e esconderia qualquer alteração
    real de geometria. A promoção é aditiva: o arquivo tem de sair no mesmo
    formato em que entrou."""
    try:
        for linha in Path(caminho).read_text(encoding="utf-8").splitlines()[1:]:
            if linha.strip() and not linha.startswith("{"):
                recuo = len(linha) - len(linha.lstrip(" "))
                return recuo or padrao
    except OSError:
        pass
    return padrao


def escrever_json_temporario(destino: Path, conteudo: object,
                             indent: int | None = None) -> Path:
    """Grava ao lado do destino (mesmo filesystem) para permitir os.replace."""
    destino = Path(destino)
    if indent is None:
        indent = detectar_indentacao(destino)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=destino.name + ".",
                               suffix=".tmp")
    os.close(fd)
    tmp = Path(tmp)
    tmp.write_text(json.dumps(conteudo, ensure_ascii=False, indent=indent) + "\n",
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


class InterrupcaoSimulada(RuntimeError):
    """Encerramento abrupto simulado: sai SEM rollback, como um SIGKILL.

    Existe só para os testes de crash recovery exercitarem o caminho que o
    `except` nunca vê — um processo morto não roda `finally`."""


def aplicar_promocao_transacional(plano: PlanoPromocao, caminho_geo: Path,
                                  caminho_assoc: Path, simulacao: ResultadoSimulacao,
                                  finalizar=None,
                                  caminho_config: Path | None = None,
                                  caminho_manifesto: Path | None = None,
                                  raiz: Path | None = None,
                                  falha_injetada: str = "",
                                  interromper_em: str = "",
                                  lote: str = "E4B") -> tuple[EstadoTransacao, dict, dict]:
    """Grava dados, manifesto e config sob um único journal.

    O journal só é limpo depois da finalização auditável inteira — dados
    gravados e validados, manifesto gravado, config finalizado e verificação
    unificada aprovada. Limpar antes deixaria uma janela em que os dados estão
    promovidos e a auditoria não existe, sem nada no disco para retomar.

    `finalizar(estado_journal)` é o callback que grava manifesto e config e roda
    a verificação unificada; recebe o marco atual para poder ser retomado.

    `falha_injetada` exercita o rollback compensatório; `interromper_em` simula
    encerramento abrupto — sai sem rollback, deixando o journal."""
    caminho_geo, caminho_assoc = Path(caminho_geo), Path(caminho_assoc)
    raiz = Path(raiz) if raiz else caminho_geo.parents[1]
    dir_dados = caminho_geo.parent
    hash_antes = {str(caminho_geo): hash_arquivo(caminho_geo),
                  str(caminho_assoc): hash_arquivo(caminho_assoc)}

    if journal.pendente(dir_dados, lote):
        pend = journal.pendente(dir_dados, lote)
        raise RuntimeError(
            f"transação anterior não concluída (estado {pend['estado']}). "
            f"Rode `recuperar --lote {lote}` antes de promover.")

    with tempfile.TemporaryDirectory() as td:
        backups = criar_backup_temporario([caminho_geo, caminho_assoc], Path(td))
        tmp_geo = tmp_assoc = None
        j = None
        try:
            tmp_geo = escrever_json_temporario(caminho_geo, simulacao.geometrias_depois_doc)
            if falha_injetada == "apos_primeiro_temporario":
                raise RuntimeError("falha injetada: após o primeiro temporário")
            tmp_assoc = escrever_json_temporario(caminho_assoc, simulacao.associacoes_depois_doc)
            for x in (tmp_geo, tmp_assoc):
                json.loads(x.read_text(encoding="utf-8"))

            destinos = {"geometrias": caminho_geo, "associacoes": caminho_assoc}
            if caminho_config:
                destinos["config"] = Path(caminho_config)
            if caminho_manifesto:
                destinos["manifesto"] = Path(caminho_manifesto)

            j = journal.preparar(
                destinos,
                {"geometrias": hash_arquivo(tmp_geo),
                 "associacoes": hash_arquivo(tmp_assoc)},
                evento.recibo_evento(), raiz, lote)
            if interromper_em == "apos_journal":
                raise InterrupcaoSimulada("interrompido após preparar o journal")

            substituir_atomico(tmp_geo, caminho_geo)
            tmp_geo = None
            journal.avancar(j, journal.GEOMETRIAS_SUBSTITUIDAS)
            if interromper_em == "apos_primeiro_replace":
                raise InterrupcaoSimulada("interrompido após o 1º replace")
            if falha_injetada == "entre_os_dois_replaces":
                raise RuntimeError("falha injetada: entre os dois replaces")

            substituir_atomico(tmp_assoc, caminho_assoc)
            tmp_assoc = None
            journal.avancar(j, journal.AMBOS_SUBSTITUIDOS)
            if interromper_em == "apos_ambos_replaces":
                raise InterrupcaoSimulada("interrompido após os dois replaces")

            if falha_injetada == "na_validacao_pos_gravacao":
                raise RuntimeError("falha injetada: na validação pós-gravação")
            val = validar_pos_gravacao(caminho_geo, caminho_assoc, plano)
            if not val.ok:
                raise RuntimeError("validação pós-gravação reprovou:\n"
                                   + val.descrever())
            journal.avancar(j, journal.DADOS_VALIDOS)
            if interromper_em == "apos_dados_validos":
                raise InterrupcaoSimulada("interrompido após validar os dados")

            hash_depois = {str(caminho_geo): hash_arquivo(caminho_geo),
                           str(caminho_assoc): hash_arquivo(caminho_assoc)}

            # finalização auditável AINDA sob o journal
            if finalizar is not None:
                finalizar(j)
            journal.avancar(j, journal.CONCLUIDA)
            if interromper_em == "apos_concluida":
                raise InterrupcaoSimulada("interrompido após CONCLUIDA")
            journal.limpar(dir_dados, raiz, lote)
            return (EstadoTransacao(backups={}, aplicado=True,
                                    rollback_executado=False),
                    hash_antes, hash_depois)

        except InterrupcaoSimulada:
            raise                      # sem rollback: é o estado que `recuperar` espera

        except Exception as e:
            restaurar_backup(backups)
            for x in (tmp_geo, tmp_assoc):
                if x is not None and Path(x).exists():
                    Path(x).unlink()
            depois = {str(caminho_geo): hash_arquivo(caminho_geo),
                      str(caminho_assoc): hash_arquivo(caminho_assoc)}
            if depois != hash_antes:
                raise RuntimeError(
                    f"ROLLBACK INCOMPLETO — hashes não voltaram ao original.\n"
                    f"antes={hash_antes}\ndepois={depois}\ncausa={e}") from e
            if j is not None:
                journal.limpar(dir_dados, raiz, lote)
            return (EstadoTransacao(backups={}, aplicado=False,
                                    rollback_executado=True, detalhe=str(e)),
                    hash_antes, depois)
