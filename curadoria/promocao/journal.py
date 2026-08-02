"""Journal persistente da promoção — recuperação após encerramento abrupto.

Dois `os.replace` sequenciais **não** são um commit atômico conjunto. Cada
substituição é atômica por arquivo; o conjunto não é. Um `SIGKILL`, queda de
energia ou travamento entre os dois deixaria `geometrias.json` novo e
`perfil_geometria.json` antigo, e o processo morto não executaria rollback
nenhum — o `try/except` só cobre exceções que o próprio processo vê.

O journal fecha essa janela: é gravado e sincronizado ANTES da primeira
substituição, e registra onde estão os backups e quais hashes são esperados.
Se o processo morrer no meio, o journal sobrevive e `recuperar` desfaz.

Os arquivos ficam no MESMO diretório dos destinos, para garantir mesmo
filesystem, e são removidos apenas depois do sucesso confirmado.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .carregar import hash_arquivo

VERSAO_JOURNAL = 1

# Estados, em ordem. `CONCLUIDA` só é escrito depois da validação pós-gravação.
PREPARADA = "PREPARADA"
GEOMETRIAS_SUBSTITUIDAS = "GEOMETRIAS_SUBSTITUIDAS"
AMBOS_SUBSTITUIDOS = "AMBOS_SUBSTITUIDOS"
VALIDADA = "VALIDADA"
CONCLUIDA = "CONCLUIDA"

ESTADOS_INCOMPLETOS = (PREPARADA, GEOMETRIAS_SUBSTITUIDAS,
                       AMBOS_SUBSTITUIDOS, VALIDADA)


class JournalCorrompido(RuntimeError):
    """Journal existe mas não é utilizável para recuperar."""


def caminho_journal(dir_dados: Path, lote: str = "E4B") -> Path:
    return Path(dir_dados) / f".promocao_{lote.lower()}_transacao.json"


def caminho_backup(destino: Path, lote: str = "E4B") -> Path:
    d = Path(destino)
    return d.parent / f".{d.name}.{lote.lower()}.bak"


def _fsync_arquivo(caminho: Path) -> None:
    with open(caminho, "rb") as f:
        os.fsync(f.fileno())


def sincronizar_diretorio(caminho: Path) -> None:
    """Torna duráveis as operações de nome (rename/unlink) do diretório.

    Sem isto, o rename pode não sobreviver a uma queda de energia mesmo com o
    conteúdo já sincronizado."""
    fd = os.open(str(Path(caminho)), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _gravar_journal(caminho: Path, conteudo: dict) -> None:
    tmp = Path(str(caminho) + ".tmp")
    tmp.write_text(json.dumps(conteudo, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    _fsync_arquivo(tmp)
    os.replace(tmp, caminho)
    sincronizar_diretorio(Path(caminho).parent)


def preparar(destinos: dict, hashes_esperados: dict, lote: str = "E4B") -> Path:
    """Cria backups duráveis e o journal. Chamado ANTES do primeiro replace.

    `destinos` mapeia papel -> Path; `hashes_esperados` mapeia papel -> hash
    calculado sobre o temporário já escrito."""
    dir_dados = Path(next(iter(destinos.values()))).parent
    arquivos = {}
    for papel, destino in destinos.items():
        destino = Path(destino)
        bak = caminho_backup(destino, lote)
        shutil.copy2(destino, bak)
        _fsync_arquivo(bak)
        arquivos[papel] = {
            "destino": str(destino.relative_to(destino.parents[1])),
            "backup": str(bak.relative_to(bak.parents[1])),
            "hash_antes": hash_arquivo(destino),
            "hash_esperado_depois": hashes_esperados[papel],
        }
    j = caminho_journal(dir_dados, lote)
    _gravar_journal(j, {"versao": VERSAO_JOURNAL, "lote": lote,
                        "estado": PREPARADA, "arquivos": arquivos})
    sincronizar_diretorio(dir_dados)
    return j


def avancar(caminho: Path, estado: str) -> None:
    j = Path(caminho)
    d = json.loads(j.read_text(encoding="utf-8"))
    d["estado"] = estado
    _gravar_journal(j, d)


def ler(caminho: Path) -> dict | None:
    """Devolve o journal, ou None se não existir. Levanta se estiver ilegível."""
    j = Path(caminho)
    if not j.exists():
        return None
    try:
        d = json.loads(j.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise JournalCorrompido(f"journal ilegível em {j}: {e}") from e
    if d.get("versao") != VERSAO_JOURNAL or "arquivos" not in d:
        raise JournalCorrompido(
            f"journal com estrutura desconhecida em {j}: "
            f"versao={d.get('versao')!r}, chaves={sorted(d)}")
    return d


def pendente(dir_dados: Path, lote: str = "E4B") -> dict | None:
    """Journal que representa transação NÃO concluída, se houver."""
    d = ler(caminho_journal(dir_dados, lote))
    if d is None:
        return None
    return d if d.get("estado") in ESTADOS_INCOMPLETOS else None


def limpar(dir_dados: Path, lote: str = "E4B") -> None:
    """Remove journal e backups. Só depois de concluído ou recuperado."""
    dir_dados = Path(dir_dados)
    d = ler(caminho_journal(dir_dados, lote))
    if d is not None:
        for info in d["arquivos"].values():
            bak = dir_dados.parent / info["backup"]
            if bak.exists():
                bak.unlink()
    j = caminho_journal(dir_dados, lote)
    if j.exists():
        j.unlink()
    sincronizar_diretorio(dir_dados)


def recuperar(dir_dados: Path, lote: str = "E4B") -> dict:
    """Restaura os destinos aos hashes anteriores e limpa o journal.

    Devolve um relatório. Não apaga nada sem confirmar que o estado voltou."""
    dir_dados = Path(dir_dados)
    d = ler(caminho_journal(dir_dados, lote))
    if d is None:
        return {"acao": "nada_a_recuperar", "restaurados": [], "ok": True}
    if d.get("estado") == CONCLUIDA:
        limpar(dir_dados, lote)
        return {"acao": "journal_concluido_removido", "restaurados": [], "ok": True}

    raiz = dir_dados.parent
    restaurados, faltando = [], []
    for papel, info in d["arquivos"].items():
        destino = raiz / info["destino"]
        bak = raiz / info["backup"]
        if not bak.exists():
            faltando.append(papel)
            continue
        if hash_arquivo(destino) != info["hash_antes"]:
            shutil.copy2(bak, destino)
            _fsync_arquivo(destino)
            restaurados.append(papel)
    sincronizar_diretorio(dir_dados)

    if faltando:
        raise JournalCorrompido(
            f"backup ausente para {faltando} — recuperação impossível sem "
            f"sobrescrever com dado não verificado. Journal preservado em "
            f"{caminho_journal(dir_dados, lote)}")

    divergentes = [p for p, i in d["arquivos"].items()
                   if hash_arquivo(raiz / i["destino"]) != i["hash_antes"]]
    if divergentes:
        raise JournalCorrompido(
            f"após restaurar, os hashes de {divergentes} ainda divergem do "
            f"original. Journal preservado para inspeção.")

    limpar(dir_dados, lote)
    return {"acao": "restaurado", "restaurados": restaurados,
            "estado_encontrado": d["estado"], "ok": True}
