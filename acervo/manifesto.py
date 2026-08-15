"""MANIFESTO_ACERVO — inventário do acervo compartilhado (Google Drive).

Este módulo é independente de `composicao` e `domain`: o acervo é sobre QUAIS
binários/coleções existem e onde, não sobre proveniência de afirmação técnica
nem sobre geometria de perfil. Misturar os dois faria um manifesto herdar gates
que não são dele.

Arquitetura vigente (handoff 2026-08-15, seção 22):

```
Drive   binários
Git     este arquivo (MANIFESTO_ACERVO.yaml) + este validador
cache   cópia local reconstruível, nunca autoridade
```

Duas operações, propósito separado:

```
manifesto_de_dict / carregar_manifesto   constrói os itens; recusa o item
                                          estruturalmente malformado (campo
                                          obrigatório ausente, enum
                                          desconhecido) assim que ele nasce.
validar_manifesto                        checagem que só existe em relação ao
                                          conjunto: id duplicado, referência
                                          para outro item que não existe,
                                          localizador do Drive ausente quando
                                          o próprio item afirma estar lá.
```

Não lê nem baixa bytes do Drive — só a folha de metadados do Git. Confirmar o
byte real é responsabilidade de outra rodada, do mesmo jeito que
`proveniencia.py` separa validação estrutural de verificação física.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ManifestoAcervoErro(RuntimeError):
    """Item ou manifesto estruturalmente malformado — não chega a existir."""


VERSAO_MANIFESTO = 1
VERSOES_SUPORTADAS = (1,)

_RE_ID_ITEM = re.compile(r"^ACV-[A-Z0-9]+(?:-[A-Z0-9]+)+$")
_RE_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Granularidade(str, Enum):
    ARQUIVO = "arquivo"
    COLECAO = "colecao"


class LeituraBootstrap(str, Enum):
    """Quando o GPT deve puxar este item para dentro do contexto do bootstrap.

    `SEMPRE` é excepcional por desenho (handoff seção 22) — a maioria dos itens
    é `sob_demanda`, consultada só quando a tarefa em curso precisar dela."""
    NUNCA = "nunca"
    SOB_DEMANDA = "sob_demanda"
    SEMPRE = "sempre"


class StatusEpistemologico(str, Enum):
    """Vocabulário editorial do bootstrap (seção 15), aplicado ao item de
    acervo em vez de a uma afirmação de handoff — mesma pergunta ("isto ainda
    vale, ou é passado preservado?"), aplicada a um binário em vez de um fato."""
    VIGENTE = "VIGENTE"
    HISTORICO = "HISTORICO"
    CONGELADO = "CONGELADO"
    INCERTO_SEM_ARBITRAGEM = "INCERTO_SEM_ARBITRAGEM"
    SUGESTAO = "SUGESTAO"


def _texto(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def _tags(valor) -> tuple[str, ...]:
    if not valor:
        return ()
    if not isinstance(valor, (list, tuple)):
        raise ManifestoAcervoErro(
            f"tags: deve ser lista de strings, veio {type(valor).__name__}")
    saida = []
    for t in valor:
        if not isinstance(t, str) or not t.strip():
            raise ManifestoAcervoErro(f"tags: entrada inválida {t!r}")
        saida.append(t.strip())
    return tuple(saida)


@dataclass(frozen=True)
class ItemAcervo:
    """Um item do acervo — arquivo único ou coleção — e o que se sabe dele.

    Campos obrigatórios são os mínimos para que o item seja identificável,
    localizável em intenção (mesmo que `drive_file_id` ainda seja `None`) e
    classificado epistemologicamente. Tudo o mais é opcional porque nem todo
    item tem hash de coleção, homologação ou fabricante conhecido — forçar
    esses campos inventaria dado que ninguém verificou."""
    id: str
    nome: str
    granularidade: Granularidade
    tipo: str
    presente_no_drive: bool
    leitura_bootstrap: LeituraBootstrap
    status_epistemologico: StatusEpistemologico
    resumo_uma_linha: str
    drive_file_id: str | None = None
    caminho_drive: str | None = None
    categoria: str | None = None
    tags: tuple[str, ...] = ()
    fabricante: str | None = None
    linha: str | None = None
    origem: str | None = None
    autoridade: str | None = None
    evidencia_primaria: bool | None = None
    homologado_por: str | None = None
    data_homologacao: str | None = None
    sha256: str | None = None
    tamanho_bytes: int | None = None
    mtime_origem: str | None = None
    hash_calculado_em: str | None = None
    substitui: str | None = None
    duplicata_de: str | None = None
    referencia_repo: str | None = None
    observacao: str | None = None

    def __post_init__(self):
        if not self.id or not self.id.strip():
            raise ManifestoAcervoErro("item sem id")
        if not _RE_ID_ITEM.fullmatch(self.id):
            raise ManifestoAcervoErro(
                f"{self.id}: id fora do formato ACV-<TIPO>-<SLUG> "
                f"(esperado {_RE_ID_ITEM.pattern})")
        if not (self.nome or "").strip():
            raise ManifestoAcervoErro(f"{self.id}: nome ausente")
        if not (self.tipo or "").strip():
            raise ManifestoAcervoErro(f"{self.id}: tipo ausente")
        if not (self.resumo_uma_linha or "").strip():
            raise ManifestoAcervoErro(f"{self.id}: resumo_uma_linha ausente")
        if not isinstance(self.granularidade, Granularidade):
            try:
                object.__setattr__(self, "granularidade",
                                   Granularidade(self.granularidade))
            except ValueError as e:
                raise ManifestoAcervoErro(
                    f"{self.id}: granularidade desconhecida "
                    f"{self.granularidade!r} (conhecidas: "
                    f"{[g.value for g in Granularidade]})") from e
        if not isinstance(self.leitura_bootstrap, LeituraBootstrap):
            try:
                object.__setattr__(self, "leitura_bootstrap",
                                   LeituraBootstrap(self.leitura_bootstrap))
            except ValueError as e:
                raise ManifestoAcervoErro(
                    f"{self.id}: leitura_bootstrap desconhecida "
                    f"{self.leitura_bootstrap!r} (conhecidas: "
                    f"{[v.value for v in LeituraBootstrap]})") from e
        if not isinstance(self.status_epistemologico, StatusEpistemologico):
            try:
                object.__setattr__(
                    self, "status_epistemologico",
                    StatusEpistemologico(self.status_epistemologico))
            except ValueError as e:
                raise ManifestoAcervoErro(
                    f"{self.id}: status_epistemologico desconhecido "
                    f"{self.status_epistemologico!r} (conhecidos: "
                    f"{[v.value for v in StatusEpistemologico]})") from e
        if not isinstance(self.presente_no_drive, bool):
            raise ManifestoAcervoErro(
                f"{self.id}: presente_no_drive deve ser booleano, veio "
                f"{type(self.presente_no_drive).__name__}")
        if self.evidencia_primaria is not None and not isinstance(
                self.evidencia_primaria, bool):
            raise ManifestoAcervoErro(
                f"{self.id}: evidencia_primaria deve ser booleano, veio "
                f"{type(self.evidencia_primaria).__name__}")
        object.__setattr__(self, "tags", _tags(self.tags))
        if self.tamanho_bytes is not None:
            if isinstance(self.tamanho_bytes, bool) or not isinstance(
                    self.tamanho_bytes, int):
                raise ManifestoAcervoErro(
                    f"{self.id}: tamanho_bytes deve ser inteiro, veio "
                    f"{type(self.tamanho_bytes).__name__}")
            if self.tamanho_bytes < 0:
                raise ManifestoAcervoErro(
                    f"{self.id}: tamanho_bytes negativo ({self.tamanho_bytes})")
        if self.sha256 is not None and not _RE_SHA256.fullmatch(self.sha256):
            raise ManifestoAcervoErro(
                f"{self.id}: sha256 fora do formato esperado (64 hex), veio "
                f"{self.sha256!r}")

    def para_dict(self) -> dict:
        return {
            "id": self.id, "nome": self.nome,
            "granularidade": self.granularidade.value, "tipo": self.tipo,
            "categoria": self.categoria, "tags": list(self.tags),
            "fabricante": self.fabricante, "linha": self.linha,
            "origem": self.origem,
            "status_epistemologico": self.status_epistemologico.value,
            "autoridade": self.autoridade,
            "evidencia_primaria": self.evidencia_primaria,
            "homologado_por": self.homologado_por,
            "data_homologacao": self.data_homologacao,
            "drive_file_id": self.drive_file_id,
            "caminho_drive": self.caminho_drive, "sha256": self.sha256,
            "tamanho_bytes": self.tamanho_bytes,
            "mtime_origem": self.mtime_origem,
            "hash_calculado_em": self.hash_calculado_em,
            "substitui": self.substitui, "duplicata_de": self.duplicata_de,
            "presente_no_drive": self.presente_no_drive,
            "leitura_bootstrap": self.leitura_bootstrap.value,
            "referencia_repo": self.referencia_repo,
            "resumo_uma_linha": self.resumo_uma_linha,
            "observacao": self.observacao,
        }


@dataclass(frozen=True)
class VarreduraAcervo:
    data: str | None = None
    locais_cobertos: tuple[str, ...] = ()
    pontos_cegos_conhecidos: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "locais_cobertos",
                           tuple(str(x) for x in (self.locais_cobertos or ())))
        object.__setattr__(
            self, "pontos_cegos_conhecidos",
            tuple(str(x) for x in (self.pontos_cegos_conhecidos or ())))


@dataclass(frozen=True)
class ManifestoAcervo:
    """`NÃO ENCONTRADO != NÃO EXISTE` (bootstrap seção 24): `ultima_varredura`
    existe para que o manifesto declare sua própria cobertura, em vez de deixar
    quem lê presumir que a lista de itens é exaustiva."""
    versao: int = VERSAO_MANIFESTO
    ultima_varredura: VarreduraAcervo | None = None
    itens: tuple[ItemAcervo, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "itens", tuple(self.itens or ()))

    def item(self, id_item: str) -> ItemAcervo | None:
        for i in self.itens:
            if i.id == id_item:
                return i
        return None


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def _item_de_dict(bruto: dict) -> ItemAcervo:
    if not isinstance(bruto, dict):
        raise ManifestoAcervoErro(
            f"item deve ser mapeamento, veio {type(bruto).__name__}")
    return ItemAcervo(
        id=_texto(bruto.get("id")) or "",
        nome=_texto(bruto.get("nome")) or "",
        granularidade=_texto(bruto.get("granularidade")) or "",
        tipo=_texto(bruto.get("tipo")) or "",
        presente_no_drive=bool(bruto.get("presente_no_drive", False)),
        leitura_bootstrap=_texto(bruto.get("leitura_bootstrap"))
                          or LeituraBootstrap.SOB_DEMANDA.value,
        status_epistemologico=_texto(bruto.get("status_epistemologico")) or "",
        resumo_uma_linha=_texto(bruto.get("resumo_uma_linha")) or "",
        drive_file_id=_texto(bruto.get("drive_file_id")),
        caminho_drive=_texto(bruto.get("caminho_drive")),
        categoria=_texto(bruto.get("categoria")),
        tags=tuple(bruto.get("tags") or ()),
        fabricante=_texto(bruto.get("fabricante")),
        linha=_texto(bruto.get("linha")),
        origem=_texto(bruto.get("origem")),
        autoridade=_texto(bruto.get("autoridade")),
        evidencia_primaria=bruto.get("evidencia_primaria"),
        homologado_por=_texto(bruto.get("homologado_por")),
        data_homologacao=_texto(bruto.get("data_homologacao")),
        sha256=_texto(bruto.get("sha256")),
        tamanho_bytes=bruto.get("tamanho_bytes"),
        mtime_origem=_texto(bruto.get("mtime_origem")),
        hash_calculado_em=_texto(bruto.get("hash_calculado_em")),
        substitui=_texto(bruto.get("substitui")),
        duplicata_de=_texto(bruto.get("duplicata_de")),
        referencia_repo=_texto(bruto.get("referencia_repo")),
        observacao=_texto(bruto.get("observacao")),
    )


def manifesto_de_dict(dados: dict) -> ManifestoAcervo:
    if not isinstance(dados, dict):
        raise ManifestoAcervoErro("manifesto: raiz tem de ser um mapeamento")
    versao = dados.get("versao_manifesto")
    if versao not in VERSOES_SUPORTADAS:
        raise ManifestoAcervoErro(
            f"manifesto: versao_manifesto {versao!r} não suportada "
            f"(suportadas: {list(VERSOES_SUPORTADAS)})")

    varredura = None
    bruta = dados.get("ultima_varredura")
    if bruta is not None:
        if not isinstance(bruta, dict):
            raise ManifestoAcervoErro(
                "manifesto: ultima_varredura deve ser mapeamento")
        varredura = VarreduraAcervo(
            data=_texto(bruta.get("data")),
            locais_cobertos=tuple(bruta.get("locais_cobertos") or ()),
            pontos_cegos_conhecidos=tuple(
                bruta.get("pontos_cegos_conhecidos") or ()))

    itens = tuple(_item_de_dict(i) for i in (dados.get("itens") or ()))
    return ManifestoAcervo(versao=versao, ultima_varredura=varredura,
                           itens=itens)


def carregar_manifesto(caminho) -> ManifestoAcervo:
    p = Path(caminho)
    if not p.exists():
        raise ManifestoAcervoErro(f"manifesto ausente: {p}")
    texto = p.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError as e:                              # pragma: no cover
        raise ManifestoAcervoErro(
            f"manifesto em YAML exige PyYAML (requirements.txt): {e}") from e
    try:
        dados = yaml.safe_load(texto)
    except yaml.YAMLError as e:
        raise ManifestoAcervoErro(f"YAML inválido em {p}: {e}") from e
    return manifesto_de_dict(dados or {})


# ---------------------------------------------------------------------------
# Validação — checagens que só existem em relação ao conjunto
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProblemaValidacao:
    item_id: str
    regra: str
    encontrado: object
    esperado: object

    def __str__(self) -> str:
        return (f"{self.item_id}: {self.regra} "
                f"(encontrado={self.encontrado!r}, esperado={self.esperado!r})")


def validar_manifesto(manifesto: ManifestoAcervo) -> tuple[ProblemaValidacao, ...]:
    """Roda sem o Drive montado — só o que o próprio manifesto contradiz.

    Cada item já chegou aqui bem formado (`ItemAcervo` recusa o resto na
    construção); o que resta é o que só existe em relação aos OUTROS itens:
    identidade única, referência que aponta para algo que existe, e a
    consistência interna entre `presente_no_drive` e `drive_file_id`."""
    problemas: list[ProblemaValidacao] = []

    ids = [i.id for i in manifesto.itens]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    for rid in repetidos:
        problemas.append(ProblemaValidacao(
            rid, "id duplicado no manifesto", rid, "um id por item"))

    indice = {i.id: i for i in manifesto.itens}

    for item in manifesto.itens:
        if item.presente_no_drive and not item.drive_file_id:
            problemas.append(ProblemaValidacao(
                item.id, "presente_no_drive=true sem drive_file_id", None,
                "drive_file_id do item no Drive"))
        for campo in ("substitui", "duplicata_de"):
            alvo = getattr(item, campo)
            if alvo is None:
                continue
            if alvo == item.id:
                problemas.append(ProblemaValidacao(
                    item.id, f"{campo} aponta para si mesmo", alvo,
                    "id de outro item"))
            elif alvo not in indice:
                problemas.append(ProblemaValidacao(
                    item.id, f"{campo} referencia item inexistente", alvo,
                    "id presente no manifesto"))

    return tuple(problemas)
