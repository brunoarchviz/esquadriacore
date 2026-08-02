"""Journal persistente da promoção — recuperação após encerramento abrupto.

Dois `os.replace` sequenciais **não** são um commit atômico conjunto. Cada
substituição é atômica por arquivo; o conjunto não é. Um `SIGKILL`, queda de
energia ou travamento deixaria parte dos artefatos novos e parte antigos, e o
processo morto não executaria rollback nenhum — o `try/except` só cobre
exceções que o próprio processo vê.

O journal cobre a transação INTEIRA, não só os dois arquivos de `dados/`:
inclui o config e o manifesto, e só é removido depois que a finalização
auditável termina. Ele também carrega o recibo do evento, porque `hash_antes`,
`quantidade_antes` e `ids_criados` não podem ser inferidos observando o estado
já promovido.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from .carregar import hash_arquivo

VERSAO_JOURNAL = 2

# Marcos da transação, em ordem.
PREPARADA = "PREPARADA"
GEOMETRIAS_SUBSTITUIDAS = "GEOMETRIAS_SUBSTITUIDAS"
AMBOS_SUBSTITUIDOS = "AMBOS_SUBSTITUIDOS"
DADOS_VALIDOS = "DADOS_VALIDOS"
MANIFESTO_GRAVADO = "MANIFESTO_GRAVADO"
CONFIG_FINALIZADO = "CONFIG_FINALIZADO"
VALIDACAO_UNIFICADA = "VALIDACAO_UNIFICADA"
CONCLUIDA = "CONCLUIDA"

ORDEM = (PREPARADA, GEOMETRIAS_SUBSTITUIDAS, AMBOS_SUBSTITUIDOS, DADOS_VALIDOS,
         MANIFESTO_GRAVADO, CONFIG_FINALIZADO, VALIDACAO_UNIFICADA, CONCLUIDA)

# Antes disto, recuperar = desfazer. A partir daqui, recuperar = retomar a
# finalização usando o recibo (estratégia B): os dados já estão válidos no
# disco, e desfazê-los perderia trabalho verificado sem ganho de segurança.
ESTADOS_ROLLBACK = (PREPARADA, GEOMETRIAS_SUBSTITUIDAS, AMBOS_SUBSTITUIDOS)
ESTADOS_FINALIZAVEIS = (DADOS_VALIDOS, MANIFESTO_GRAVADO, CONFIG_FINALIZADO,
                        VALIDACAO_UNIFICADA)
ESTADOS_INCOMPLETOS = ESTADOS_ROLLBACK + ESTADOS_FINALIZAVEIS


class JournalCorrompido(RuntimeError):
    """Journal existe mas não é utilizável para recuperar."""


class RecuperacaoBloqueada(RuntimeError):
    """Preflight reprovou. NENHUM destino foi tocado."""


def caminho_journal(dir_dados: Path, lote: str = "E4B") -> Path:
    return Path(dir_dados) / f".promocao_{lote.lower()}_transacao.json"


def caminho_backup(destino: Path, lote: str = "E4B") -> Path:
    d = Path(destino)
    return d.parent / f".{d.name}.{lote.lower()}.bak"


def _fsync_arquivo(caminho: Path) -> None:
    with open(caminho, "rb") as f:
        os.fsync(f.fileno())


def sincronizar_diretorio(caminho: Path) -> None:
    """Torna duráveis as operações de nome (rename/unlink) do diretório."""
    fd = os.open(str(Path(caminho)), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def escrever_atomico(destino: Path, texto: str) -> None:
    """Temporário ao lado + fsync + os.replace + fsync do diretório.

    Usado também para config e manifesto: `write_text` direto deixaria os
    artefatos de finalização fora da garantia de durabilidade."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=destino.name + ".",
                               suffix=".tmp")
    os.close(fd)
    tmp = Path(tmp)
    tmp.write_text(texto, encoding="utf-8")
    _fsync_arquivo(tmp)
    os.replace(tmp, destino)
    sincronizar_diretorio(destino.parent)


def _gravar_journal(caminho: Path, conteudo: dict) -> None:
    escrever_atomico(caminho, json.dumps(conteudo, ensure_ascii=False,
                                         indent=1) + "\n")


def preparar(destinos: dict, hashes_esperados: dict, recibo: dict,
             raiz: Path, lote: str = "E4B") -> Path:
    """Cria backups duráveis e o journal. Chamado ANTES do primeiro replace.

    `destinos` mapeia papel -> Path (inclui config e manifesto). O manifesto
    pode não existir ainda: `existia_antes=False` significa que o rollback é
    REMOVER o arquivo, não restaurar backup inexistente."""
    raiz = Path(raiz)
    dir_dados = Path(destinos["geometrias"]).parent
    arquivos = {}
    for papel, destino in destinos.items():
        destino = Path(destino)
        existia = destino.exists()
        info = {
            "destino": str(destino.relative_to(raiz)),
            "existia_antes": existia,
            "backup": None,
            "hash_antes": None,
            "hash_esperado_depois": hashes_esperados.get(papel),
        }
        if existia:
            bak = caminho_backup(destino, lote)
            shutil.copy2(destino, bak)
            _fsync_arquivo(bak)
            sincronizar_diretorio(bak.parent)
            info["backup"] = str(bak.relative_to(raiz))
            info["hash_antes"] = hash_arquivo(destino)
        arquivos[papel] = info

    j = caminho_journal(dir_dados, lote)
    _gravar_journal(j, {"versao": VERSAO_JOURNAL, "lote": lote,
                        "estado": PREPARADA, "arquivos": arquivos,
                        "evento_promocao": recibo})
    return j


def avancar(caminho: Path, estado: str) -> None:
    if estado not in ORDEM:
        raise ValueError(f"estado desconhecido: {estado!r}")
    j = Path(caminho)
    d = json.loads(j.read_text(encoding="utf-8"))
    d["estado"] = estado
    _gravar_journal(j, d)


def ler(caminho: Path) -> dict | None:
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
    if d.get("estado") not in ORDEM:
        raise JournalCorrompido(f"estado desconhecido em {j}: {d.get('estado')!r}")
    return d


def pendente(dir_dados: Path, lote: str = "E4B") -> dict | None:
    """Journal que exige ação — inclui `CONCLUIDA` abandonado antes da limpeza.

    Ignorar um `CONCLUIDA` residual deixaria backups órfãos no disco e uma
    próxima promoção rodando sobre resíduo."""
    d = ler(caminho_journal(dir_dados, lote))
    if d is None:
        return None
    return d          # qualquer journal existente exige ação


def limpar(dir_dados: Path, raiz: Path, lote: str = "E4B") -> None:
    """Remove journal e backups. Só depois de concluído ou recuperado."""
    dir_dados, raiz = Path(dir_dados), Path(raiz)
    d = ler(caminho_journal(dir_dados, lote))
    if d is not None:
        for info in d["arquivos"].values():
            if info.get("backup"):
                bak = raiz / info["backup"]
                if bak.exists():
                    bak.unlink()
    j = caminho_journal(dir_dados, lote)
    if j.exists():
        j.unlink()
    sincronizar_diretorio(dir_dados)


# ---------------------------------------------------------------------------
# Recuperação: preflight completo antes de QUALQUER mutação
# ---------------------------------------------------------------------------

def preflight(d: dict, raiz: Path) -> list[str]:
    """Confere tudo antes de tocar em um único destino.

    Restaurar um arquivo e só então descobrir que o backup do outro sumiu
    deixaria o estado pior do que estava."""
    raiz = Path(raiz)
    problemas = []
    for papel, info in d["arquivos"].items():
        destino = raiz / info["destino"]
        if ".." in info["destino"] or Path(info["destino"]).is_absolute():
            problemas.append(f"{papel}: destino fora da árvore ({info['destino']})")
            continue
        if not info["existia_antes"]:
            continue                      # rollback = remover; não exige backup
        if not info.get("backup"):
            problemas.append(f"{papel}: existia antes mas não há backup registrado")
            continue
        bak = raiz / info["backup"]
        if not bak.exists():
            problemas.append(f"{papel}: backup ausente ({info['backup']})")
            continue
        if hash_arquivo(bak) != info["hash_antes"]:
            problemas.append(
                f"{papel}: backup com hash divergente do registrado "
                f"({hash_arquivo(bak)[:16]} != {info['hash_antes'][:16]})")
    return problemas


def recuperar(dir_dados: Path, raiz: Path, lote: str = "E4B") -> dict:
    """Desfaz a transação. Preflight primeiro; zero mutação se ele reprovar."""
    dir_dados, raiz = Path(dir_dados), Path(raiz)
    d = ler(caminho_journal(dir_dados, lote))
    if d is None:
        return {"acao": "nada_a_recuperar", "restaurados": [], "removidos": [],
                "ok": True}

    problemas = preflight(d, raiz)
    if problemas:
        raise RecuperacaoBloqueada(
            "preflight reprovou — NENHUM destino foi modificado:\n  "
            + "\n  ".join(problemas)
            + f"\njournal e backups preservados em {dir_dados}")

    restaurados, removidos = [], []
    for papel, info in d["arquivos"].items():
        destino = raiz / info["destino"]
        if not info["existia_antes"]:
            if destino.exists():
                destino.unlink()
                removidos.append(papel)
            continue
        bak = raiz / info["backup"]
        if hash_arquivo(destino) != info["hash_antes"] if destino.exists() else True:
            escrever_atomico(destino, bak.read_text(encoding="utf-8"))
            restaurados.append(papel)
    for p in {(raiz / i["destino"]).parent for i in d["arquivos"].values()}:
        sincronizar_diretorio(p)

    divergentes = [p for p, i in d["arquivos"].items()
                   if i["existia_antes"]
                   and hash_arquivo(raiz / i["destino"]) != i["hash_antes"]]
    if divergentes:
        raise JournalCorrompido(
            f"após restaurar, os hashes de {divergentes} ainda divergem. "
            f"Journal preservado para inspeção.")

    limpar(dir_dados, raiz, lote)
    return {"acao": "restaurado", "restaurados": restaurados,
            "removidos": removidos, "estado_encontrado": d["estado"], "ok": True}
