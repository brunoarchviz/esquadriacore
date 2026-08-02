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


def escrever_texto_temporario(destino: Path, texto: str) -> Path:
    """Grava ao lado do destino (mesmo filesystem) para permitir os.replace.

    Recebe TEXTO já serializado: é o mesmo byte a byte cujo hash foi prometido
    ao journal. Reserializar aqui abriria a chance de gravar conteúdo diferente
    do que o journal diz esperar."""
    destino = Path(destino)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=destino.name + ".",
                               suffix=".tmp")
    os.close(fd)
    tmp = Path(tmp)
    tmp.write_text(texto, encoding="utf-8")
    sincronizar_arquivo(tmp)
    return tmp


def escrever_json_temporario(destino: Path, conteudo: object,
                             indent: int | None = None) -> Path:
    destino = Path(destino)
    if indent is None:
        indent = detectar_indentacao(destino)
    return escrever_texto_temporario(
        destino, json.dumps(conteudo, ensure_ascii=False, indent=indent) + "\n")


def sincronizar_arquivo(caminho: Path) -> None:
    with open(caminho, "rb") as f:
        os.fsync(f.fileno())


def substituir_atomico(temporario: Path, destino: Path) -> None:
    os.replace(temporario, destino)


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
                                  documentos,
                                  caminho_config: Path,
                                  caminho_manifesto: Path,
                                  finalizar,
                                  raiz: Path | None = None,
                                  falha_injetada: str = "",
                                  interromper_em: str = "",
                                  lote: str = "E4B") -> tuple[EstadoTransacao, dict, dict]:
    """Grava os QUATRO artefatos sob um único journal.

    `documentos` traz os quatro já serializados e com os hashes finais — todos
    calculados ANTES do primeiro `os.replace`, para que o journal possa
    prometer o conteúdo final de cada um dos quatro papéis, e não só o dos dois
    arquivos de `dados/`.

    O journal só é limpo depois da finalização auditável inteira. Limpar antes
    deixaria uma janela em que os dados estão promovidos e a auditoria não
    existe, sem nada no disco para retomar.

    Rollback: enquanto o journal não existe, nenhum destino foi tocado e basta
    apagar os temporários. Depois que ele existe, o journal é a ÚNICA
    autoridade para desfazer — restaurar dois arquivos por um mecanismo
    paralelo deixaria manifesto e config novos no disco enquanto `dados/`
    voltava, que é exatamente a incoerência que a transação promete não
    produzir.

    `falha_injetada` exercita o rollback compensatório; `interromper_em` simula
    encerramento abrupto — sai sem rollback, deixando o journal."""
    caminho_geo, caminho_assoc = Path(caminho_geo), Path(caminho_assoc)
    caminho_config, caminho_manifesto = Path(caminho_config), Path(caminho_manifesto)
    raiz = Path(raiz) if raiz else caminho_geo.parents[1]
    dir_dados = caminho_geo.parent
    hash_antes = {str(caminho_geo): hash_arquivo(caminho_geo),
                  str(caminho_assoc): hash_arquivo(caminho_assoc)}

    pend = journal.pendente(dir_dados, lote)
    if pend:
        raise RuntimeError(
            f"transação anterior não concluída (estado {pend['estado']}). "
            f"Rode `recuperar --lote {lote}` antes de promover.")

    hashes_finais = documentos.hashes
    tmp_geo = tmp_assoc = None
    j = None
    try:
        tmp_geo = escrever_texto_temporario(caminho_geo, documentos.geometrias)
        if falha_injetada == "apos_primeiro_temporario":
            raise RuntimeError("falha injetada: após o primeiro temporário")
        tmp_assoc = escrever_texto_temporario(caminho_assoc, documentos.associacoes)
        for x in (tmp_geo, tmp_assoc):
            json.loads(x.read_text(encoding="utf-8"))
        for papel, tmp in (("geometrias", tmp_geo), ("associacoes", tmp_assoc)):
            if hash_arquivo(tmp) != hashes_finais[papel]:
                raise RuntimeError(
                    f"{papel}: temporário não corresponde ao hash planejado")

        destinos = {"geometrias": caminho_geo, "associacoes": caminho_assoc,
                    "config": caminho_config, "manifesto": caminho_manifesto}
        j = journal.preparar(destinos, hashes_finais, evento.recibo_evento(),
                             raiz, lote)
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

        # Finalização auditável AINDA sob o journal: grava manifesto e config,
        # roda a verificação unificada, avança até CONCLUIDA e limpa.
        rel = finalizar(j)
        pendente_limpeza = bool(getattr(rel, "limpeza_pendente", False))
        return (EstadoTransacao(backups={}, aplicado=True,
                                rollback_executado=False,
                                limpeza_pendente=pendente_limpeza,
                                detalhe=getattr(rel, "detalhe", "")),
                hash_antes, hash_depois)

    except InterrupcaoSimulada:
        raise                      # sem rollback: é o estado que `recuperar` espera

    except Exception as e:
        for x in (tmp_geo, tmp_assoc):
            if x is not None and Path(x).exists():
                Path(x).unlink()
        if j is None:
            # Nada foi substituído ainda: não há o que desfazer.
            return (EstadoTransacao(backups={}, aplicado=False,
                                    rollback_executado=False, detalhe=str(e)),
                    hash_antes, dict(hash_antes))

        # A promoção já foi confirmada? Depois de CONCLUIDA os quatro artefatos
        # estão gravados, conferidos por hash e aprovados pela verificação
        # unificada. Uma falha na faxina que vem DEPOIS disso não pode virar
        # rollback: seria desfazer um resultado correto por causa de um backup
        # que ninguém consome.
        try:
            atual = journal.ler(j, raiz)
        except journal.JournalCorrompido:
            atual = None
        if atual is not None and atual["estado"] == journal.CONCLUIDA:
            return (EstadoTransacao(
                        backups={}, aplicado=True, rollback_executado=False,
                        limpeza_pendente=True,
                        detalhe=f"promoção CONCLUIDA; limpeza pendente: {e}"),
                    hash_antes,
                    {str(caminho_geo): hash_arquivo(caminho_geo),
                     str(caminho_assoc): hash_arquivo(caminho_assoc)})

        # Journal existe e a promoção não foi confirmada: ele é a única
        # autoridade. Se o rollback falhar, journal e backups ficam no disco.
        journal.recuperar(dir_dados, raiz, lote)
        depois = {str(caminho_geo): hash_arquivo(caminho_geo),
                  str(caminho_assoc): hash_arquivo(caminho_assoc)}
        if depois != hash_antes:
            raise RuntimeError(
                f"ROLLBACK INCOMPLETO — hashes não voltaram ao original.\n"
                f"antes={hash_antes}\ndepois={depois}\ncausa={e}") from e
        return (EstadoTransacao(backups={}, aplicado=False,
                                rollback_executado=True, detalhe=str(e)),
                hash_antes, depois)
