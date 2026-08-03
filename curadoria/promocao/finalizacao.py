"""Planejamento dos quatro artefatos e finalização retomável.

Duas correções vivem aqui.

A primeira: `CONFIG_FINALIZADO` era só um rótulo. A finalização gravava o
manifesto e avançava direto para `CONFIG_FINALIZADO` sem escrever o config,
usando o objeto carregado antes da transação. Na branch viva isso passava
porque o config já estava promovido; partindo do estado real de uma promoção,
`promocao_oficial_realizada: false` nunca viraria `true`.

A segunda: a retomada após queda não retomava estado nenhum. Ela recarregava o
config atual, reconstruía o manifesto e limpava o journal, independentemente do
marco encontrado — e um journal `CONCLUIDA` era apagado sem conferir nada.

Aqui os quatro documentos são construídos ANTES do primeiro `os.replace`, e os
quatro hashes finais vão para o journal. A retomada reconstrói os documentos
pela mesma função pura e exige que os hashes batam com o que o journal
prometeu: se não baterem, ela recusa sem tocar em nada. É isso que impede a
retomada de terminar uma transação diferente da que começou.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import auditoria, journal
from .carregar import hash_arquivo
from .config_promovido import construir_config_promovido_e4b
from .transacao import detectar_indentacao

INDENT_MANIFESTO = 2


class FinalizacaoBloqueada(RuntimeError):
    """A finalização não pode prosseguir. NENHUM destino foi tocado depois disto."""


def _hash_texto(texto: str) -> str:
    import hashlib
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DocumentosFinais:
    """Os quatro documentos serializados, com os hashes que o journal promete."""
    geometrias: str
    associacoes: str
    config: str
    manifesto: str

    @property
    def hashes(self) -> dict:
        return {"geometrias": _hash_texto(self.geometrias),
                "associacoes": _hash_texto(self.associacoes),
                "config": _hash_texto(self.config),
                "manifesto": _hash_texto(self.manifesto)}


def serializar_como_o_arquivo(destino: Path, doc: object,
                              indent_padrao: int = 1) -> str:
    """Mesma indentação do arquivo oficial — a promoção é aditiva, não reformata."""
    indent = detectar_indentacao(Path(destino), indent_padrao)
    return json.dumps(doc, ensure_ascii=False, indent=indent) + "\n"


def planejar_documentos(simulacao, config_antes: dict, candidatos,
                        caminho_geo: Path, caminho_assoc: Path,
                        caminho_config: Path, lote: str = "E4B",
                        reconstruido: bool = False) -> DocumentosFinais:
    """Constrói os QUATRO documentos em memória, antes de qualquer gravação.

    Nenhum deles toca o disco aqui. O config sai da transformação pura, o
    manifesto sai dos fatos canônicos de `evento.py` — não da simulação viva,
    que sobre dados já promovidos enxergaria 54 → 54."""
    config_depois = construir_config_promovido_e4b(config_antes, candidatos)
    manifesto = auditoria.construir_manifesto(simulacao, config_depois,
                                              lote=lote,
                                              reconstruido=reconstruido)
    return DocumentosFinais(
        geometrias=serializar_como_o_arquivo(caminho_geo,
                                             simulacao.geometrias_depois_doc),
        associacoes=serializar_como_o_arquivo(caminho_assoc,
                                              simulacao.associacoes_depois_doc),
        config=serializar_como_o_arquivo(caminho_config, config_depois,
                                         indent_padrao=2),
        manifesto=json.dumps(manifesto, ensure_ascii=False,
                             indent=INDENT_MANIFESTO) + "\n",
    )


# ---------------------------------------------------------------------------
# Retomada orientada pelo estado do journal
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoRecuperacao:
    """`concluida` é a promoção confirmada; `limpeza_pendente` é só faxina.

    Depois de `CONCLUIDA` — quatro hashes conferidos e verificação unificada
    aprovada — a promoção está feita. Falhar ao apagar um backup, ao remover o
    journal ou no `fsync` final não pode desfazer isso: seria trocar um
    resultado correto e verificado por um rollback, por causa de um arquivo
    auxiliar que ninguém consome."""
    estado_encontrado: str
    passos: tuple[str, ...]
    ok: bool = True
    concluida: bool = False
    limpeza_pendente: bool = False
    detalhe: str = ""


def _destino(d: dict, papel: str, raiz: Path) -> Path:
    return Path(raiz) / d["arquivos"][papel]["destino"]


def _exigir_conteudo_final(d: dict, papel: str, raiz: Path, contexto: str) -> None:
    esperado = d["arquivos"][papel]["hash_esperado_depois"]
    alvo = _destino(d, papel, raiz)
    if not alvo.exists():
        raise FinalizacaoBloqueada(
            f"{contexto}: {papel} ausente em {d['arquivos'][papel]['destino']}")
    real = hash_arquivo(alvo)
    if real != esperado:
        raise FinalizacaoBloqueada(
            f"{contexto}: {papel} no disco não é o conteúdo final esperado "
            f"({real[:16]} != {esperado[:16]})")


def _conferir_documentos_reconstruidos(d: dict, docs: DocumentosFinais) -> None:
    """Os documentos reconstruídos têm de ser os que o journal prometeu.

    É esta conferência que impede uma retomada de gravar um config ou um
    manifesto diferentes do que a transação original ia gravar."""
    hashes = docs.hashes
    divergentes = [p for p in journal.PAPEIS
                   if hashes[p] != d["arquivos"][p]["hash_esperado_depois"]]
    if divergentes:
        raise FinalizacaoBloqueada(
            "documentos reconstruídos divergem do que o journal prometeu para "
            f"{divergentes} — recuperação bloqueada, zero arquivos alterados")


def retomar_finalizacao(caminho_journal: Path, raiz: Path,
                        documentos: DocumentosFinais, verificar,
                        lote: str = "E4B", falha_injetada: str = "",
                        interromper_em: str = "",
                        interrupcao=RuntimeError) -> ResultadoRecuperacao:
    """Leva a transação de onde ela parou até `CONCLUIDA` e limpa.

    Cada marco só avança DEPOIS que a gravação correspondente aconteceu e foi
    conferida por hash. `CONCLUIDA` não é limpo às cegas: os quatro hashes e a
    verificação unificada são conferidos primeiro."""
    caminho_journal, raiz = Path(caminho_journal), Path(raiz)
    d = journal.ler(caminho_journal, raiz)
    if d is None:
        raise FinalizacaoBloqueada(f"sem journal em {caminho_journal}")
    estado = d["estado"]
    if estado not in journal.ESTADOS_FINALIZAVEIS + (journal.CONCLUIDA,):
        raise FinalizacaoBloqueada(
            f"estado {estado} não é finalizável — use o rollback")

    problemas = journal.divergencias_do_recibo(d)
    if problemas:
        raise FinalizacaoBloqueada(
            "recibo do journal divergente:\n  " + "\n  ".join(problemas))
    _conferir_documentos_reconstruidos(d, documentos)

    i = journal.ORDEM.index(estado)
    passos = []

    # Os dados já foram gravados e validados antes de DADOS_VALIDOS; se não
    # estiverem no conteúdo final esperado, não há o que retomar.
    for papel in ("geometrias", "associacoes"):
        _exigir_conteudo_final(d, papel, raiz, f"retomada de {estado}")

    if i < journal.ORDEM.index(journal.MANIFESTO_GRAVADO):
        journal.escrever_atomico(_destino(d, "manifesto", raiz),
                                 documentos.manifesto)
        _exigir_conteudo_final(d, "manifesto", raiz, "após gravar o manifesto")
        journal.avancar(caminho_journal, journal.MANIFESTO_GRAVADO)
        passos.append("manifesto gravado")
        if falha_injetada == "depois_de_gravar_manifesto":
            raise RuntimeError("falha injetada: depois de gravar o manifesto")
        if interromper_em == "depois_de_gravar_manifesto":
            raise interrupcao("interrompido depois de gravar o manifesto")
    _exigir_conteudo_final(d, "manifesto", raiz, f"retomada de {estado}")

    if i < journal.ORDEM.index(journal.CONFIG_FINALIZADO):
        journal.escrever_atomico(_destino(d, "config", raiz), documentos.config)
        _exigir_conteudo_final(d, "config", raiz, "após gravar o config")
        journal.avancar(caminho_journal, journal.CONFIG_FINALIZADO)
        passos.append("config gravado")
        if falha_injetada == "depois_de_gravar_config":
            raise RuntimeError("falha injetada: depois de gravar o config")
        if interromper_em == "depois_de_gravar_config":
            raise interrupcao("interrompido depois de gravar o config")
    _exigir_conteudo_final(d, "config", raiz, f"retomada de {estado}")

    # Verificação unificada das quatro camadas relidas do disco. Roda também
    # quando o journal já está em VALIDACAO_UNIFICADA ou CONCLUIDA: limpar sem
    # conferir seria confiar num rótulo.
    if falha_injetada == "durante_verificacao_unificada":
        raise RuntimeError("falha injetada: durante a verificação unificada")
    unif = verificar()
    if not unif.ok:
        raise RuntimeError("verificação unificada reprovou:\n" + unif.descrever())
    passos.append("verificação unificada aprovada")
    if i < journal.ORDEM.index(journal.VALIDACAO_UNIFICADA):
        journal.avancar(caminho_journal, journal.VALIDACAO_UNIFICADA)
    if falha_injetada == "depois_de_validacao_unificada":
        raise RuntimeError("falha injetada: depois da validação unificada")
    if interromper_em == "depois_de_validacao_unificada":
        raise interrupcao("interrompido depois da validação unificada")

    if i < journal.ORDEM.index(journal.CONCLUIDA):
        journal.avancar(caminho_journal, journal.CONCLUIDA)
        passos.append("CONCLUIDA")
    if interromper_em == "apos_concluida":
        raise interrupcao("interrompido após CONCLUIDA")

    # Só agora, com os quatro conteúdos confirmados e a verificação aprovada.
    for papel in journal.PAPEIS:
        _exigir_conteudo_final(d, papel, raiz, "antes de limpar")

    # Ponto de commit: daqui em diante a promoção está confirmada. A limpeza é
    # faxina — journal e backups não são consumidos por ninguém, e falhar ao
    # removê-los não torna a promoção inválida.
    try:
        journal.limpar(_destino(d, "geometrias", raiz).parent, raiz, lote)
    except Exception as e:
        passos.append(f"LIMPEZA PENDENTE: {e}")
        return ResultadoRecuperacao(
            estado_encontrado=estado, passos=tuple(passos), ok=True,
            concluida=True, limpeza_pendente=True, detalhe=str(e))
    passos.append("journal e backups removidos")
    return ResultadoRecuperacao(estado_encontrado=estado, passos=tuple(passos),
                                concluida=True)
