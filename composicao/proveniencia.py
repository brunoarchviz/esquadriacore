"""Proveniência das evidências primárias — quem sustenta o quê, e com que peso.

Este módulo é GENÉRICO. Ele não sabe o que é uma Suprema, nem quantas baguetes
uma folha tem: sabe ler um manifesto, conferir se ele é internamente coerente e
conferir os bytes do acervo quando alguém informa onde o acervo está montado.

As afirmações concretas de uma tipologia são DADOS, não código. Escrevê-las em
Python transformaria conhecimento em revisão de diff: mudar "o SU-053 aparece
quatro vezes" viraria alteração de módulo, quando é alteração de evidência.

Duas operações separadas de propósito:

```
validar_manifesto            estrutura, ids, papéis, referências, segurança de
                             caminho. Roda em qualquer clone, sem o acervo.
verificar_acervo_do_manifesto  bytes reais: existe, é arquivo, hash e tamanho
                             batem. Exige a raiz física e REPROVA sem ela.
```

O acervo bruto não entra no Git. O que entra é metadado: rótulo do acervo,
caminho relativo, sha256 e tamanho — identidade do artefato sem o endereço da
máquina de quem o guardou.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .modelos import (ABRANGENCIA_EXEMPLAR, ABRANGENCIAS_DE_FONTE,
                      FORMA_ACERVO_EXTERNO, TIPOS_DE_FONTE,
                      TIPOS_SEM_AUTORIDADE_FISICA, ESTADOS_CONFIRMADOS,
                      EstadoConhecimento, FonteEvidencia, ReceitaErro,
                      ResultadoValidacao, _RE_ID_FONTE, _RE_RAIZ_LOGICA,
                      _referencia_de_arquivo_insegura, como_tupla,
                      fonte_compativel_com_afirmacao, indexar_fontes)
from .validar import verificar_artefato_no_acervo

# Versão do SCHEMA do manifesto, não do conteúdo. Um manifesto sem versão seria
# impossível de migrar sem adivinhar o formato de quem o escreveu.
VERSAO_MANIFESTO = 1
VERSOES_SUPORTADAS = (1,)

ORIGEM_MANIFESTO = "manifesto de proveniência"

FORMATO_ID_AFIRMACAO = "[A-Z][A-Z0-9-]*"
_RE_ID_AFIRMACAO = re.compile(r"[A-Z][A-Z0-9-]*")


class PapelDaFonte(str, Enum):
    """O que ESTA fonte faz por ESTA afirmação.

    Papel não é estado de conhecimento. O estado é da afirmação inteira e vale
    uma vez; o papel é da ligação e muda de afirmação para afirmação — a mesma
    foto pode ser prova direta de "existem duas folhas" e mera corroboração de
    "esta peça é o SU-040", porque nenhuma foto do acervo mostra código legível.

    `CONFLITANTE` existe para que discordância seja registrável. Uma fonte que
    contradiz a afirmação some do registro se o único vocabulário disponível
    for "sustenta"; e evidência que some vira evidência que ninguém revisou.
    """
    DIRETA = "DIRETA"
    CORROBORATIVA = "CORROBORATIVA"
    DERIVADA = "DERIVADA"
    CONFLITANTE = "CONFLITANTE"


# Quem pode SUSTENTAR uma afirmação confirmada. Corroboração não entra: uma
# foto que combina com a tese, ao lado de nenhuma prova direta, não é prova.
# `DERIVADA` entra porque afirmação derivada tem suporte derivado — a contagem
# de vinte ocorrências é agregação, não observação.
PAPEIS_QUE_SUSTENTAM = frozenset({PapelDaFonte.DIRETA, PapelDaFonte.DERIVADA})


def _reprovar(alvo, regra, encontrado, esperado):
    return ResultadoValidacao.reprovado(alvo, regra, encontrado, esperado,
                                        ORIGEM_MANIFESTO)


# ---------------------------------------------------------------------------
# Identidade dos artefatos
# ---------------------------------------------------------------------------

def _sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def id_de_artefato(caminho_relativo: str, prefixo: str = "FONTE") -> str:
    """`id_fonte` determinístico, legível e derivado do caminho no acervo.

    Não usa posição na lista: inserir um arquivo no meio renumeraria tudo o que
    veio depois, e citações antigas passariam a apontar para outro artefato.
    Não usa o sha256: hash é integridade de conteúdo, e reexportar a mesma foto
    trocaria a identidade da fonte sem que a fonte tivesse mudado.

    A extensão entra no id porque `croqui.pdf` e `croqui.jpeg` são dois
    artefatos."""
    limpo = _sem_acentos(caminho_relativo).upper()
    partes = [p for p in re.split(r"[^A-Z0-9]+", limpo) if p]
    if not partes:
        raise ReceitaErro(
            f"caminho não produz identificador legível: {caminho_relativo!r}")
    return f"{prefixo}-" + "-".join(partes)


def inventariar_acervo(raiz_fisica, raiz_logica: str) -> tuple[dict, ...]:
    """Metadados dos arquivos regulares do acervo. NÃO copia nem altera bytes.

    Mecânico de propósito: grupo é o primeiro segmento do caminho, e mais nada
    é inferido. Classificar `02_janela_pequena` como fotografia da janela
    pequena é decisão de curadoria e mora no manifesto, não aqui — um scanner
    que adivinha semântica produz proveniência que ninguém decidiu."""
    raiz = Path(raiz_fisica).resolve()
    if not raiz.is_dir():
        raise ReceitaErro(f"raiz física do acervo inexistente: {raiz}")
    if not _RE_RAIZ_LOGICA.fullmatch(raiz_logica or ""):
        raise ReceitaErro(
            f"raiz lógica inválida: {raiz_logica!r} — esperado "
            f"{_RE_RAIZ_LOGICA.pattern}")

    itens = []
    for caminho in sorted(p for p in raiz.rglob("*") if p.is_file()):
        if caminho.is_symlink():
            raise ReceitaErro(
                f"symlink no acervo: {caminho} — o inventário registra "
                f"artefatos, não atalhos para eles")
        relativo = caminho.relative_to(raiz).as_posix()
        dados = caminho.read_bytes()
        itens.append({
            "id_fonte": id_de_artefato(relativo),
            "grupo": relativo.split("/", 1)[0],
            "caminho_relativo": relativo,
            "sha256": hashlib.sha256(dados).hexdigest(),
            "tamanho_bytes": len(dados),
            "formato": caminho.suffix.lstrip(".").lower() or None,
        })

    ids = [i["id_fonte"] for i in itens]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        raise ReceitaErro(
            f"identificadores de artefato colidiram: {repetidos} — dois "
            f"caminhos diferentes produziram o mesmo id, e citar um deles "
            f"citaria os dois")
    return tuple(itens)


# ---------------------------------------------------------------------------
# Modelos do manifesto
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CitacaoDeFonte:
    """Uma fonte, um papel. Uma afirmação cita quantas precisar."""
    id_fonte: str
    papel: PapelDaFonte
    observacao: str | None = None

    def __post_init__(self):
        if not _RE_ID_FONTE.fullmatch(self.id_fonte or ""):
            raise ReceitaErro(f"citação com id_fonte inválido: "
                              f"{self.id_fonte!r}")
        if not isinstance(self.papel, PapelDaFonte):
            object.__setattr__(self, "papel", PapelDaFonte(self.papel))

    @property
    def sustenta(self) -> bool:
        return self.papel in PAPEIS_QUE_SUSTENTAM

    def para_dict(self) -> dict:
        return {"id_fonte": self.id_fonte, "papel": self.papel.value,
                "observacao": self.observacao}


@dataclass(frozen=True)
class AfirmacaoDeProveniencia:
    """Uma afirmação citável, com as fontes que a sustentam e as que a negam.

    `derivada_de` guarda as afirmações agregadas por esta. Sem isso, uma
    contagem total pareceria observação direta — e ninguém saberia que ela cai
    junto se uma das parcelas cair."""
    identificador: str
    texto: str
    estado: EstadoConhecimento
    citacoes: tuple[CitacaoDeFonte, ...] = ()
    derivada_de: tuple[str, ...] = ()
    observacao: str | None = None

    def __post_init__(self):
        if not _RE_ID_AFIRMACAO.fullmatch(self.identificador or ""):
            raise ReceitaErro(
                f"identificador de afirmação inválido: "
                f"{self.identificador!r} — esperado {FORMATO_ID_AFIRMACAO}")
        if not (self.texto or "").strip():
            raise ReceitaErro(f"{self.identificador}: afirmação sem texto")
        if not isinstance(self.estado, EstadoConhecimento):
            object.__setattr__(self, "estado",
                               EstadoConhecimento(self.estado))
        object.__setattr__(self, "citacoes",
                           como_tupla(self.citacoes, "citacoes"))
        object.__setattr__(self, "derivada_de",
                           como_tupla(self.derivada_de, "derivada_de"))
        vistos = [c.id_fonte for c in self.citacoes]
        repetidos = sorted({i for i in vistos if vistos.count(i) > 1})
        if repetidos:
            raise ReceitaErro(
                f"{self.identificador}: fonte citada duas vezes: {repetidos} — "
                f"a mesma fonte com dois papéis esconde qual deles vale")

    @property
    def derivada(self) -> bool:
        return bool(self.derivada_de)

    def citacoes_com_papel(self, papel: PapelDaFonte) -> tuple:
        return tuple(c for c in self.citacoes if c.papel is papel)

    def para_dict(self) -> dict:
        return {"identificador": self.identificador, "texto": self.texto,
                "estado": self.estado.value,
                "citacoes": [c.para_dict() for c in self.citacoes],
                "derivada_de": list(self.derivada_de),
                "observacao": self.observacao}


@dataclass(frozen=True)
class ConflitoRegistrado:
    """Divergência preservada, não resolvida.

    Escolher um dos valores aqui seria arbitragem disfarçada de leitura. O
    conflito fica no registro até que alguém com autoridade de domínio decida,
    e o `estado` PENDENTE impede que ele sustente qualquer cálculo."""
    identificador: str
    descricao: str
    valores: tuple[str, ...] = ()
    citacoes: tuple[CitacaoDeFonte, ...] = ()
    estado: EstadoConhecimento = EstadoConhecimento.PENDENTE

    def __post_init__(self):
        if not _RE_ID_AFIRMACAO.fullmatch(self.identificador or ""):
            raise ReceitaErro(f"identificador de conflito inválido: "
                              f"{self.identificador!r}")
        if not isinstance(self.estado, EstadoConhecimento):
            object.__setattr__(self, "estado",
                               EstadoConhecimento(self.estado))
        if self.estado in ESTADOS_CONFIRMADOS:
            raise ReceitaErro(
                f"{self.identificador}: conflito registrado como "
                f"{self.estado.value} — um conflito confirmado seria uma "
                f"escolha automática entre os valores divergentes")
        object.__setattr__(self, "valores", como_tupla(self.valores, "valores"))
        object.__setattr__(self, "citacoes",
                           como_tupla(self.citacoes, "citacoes"))

    def para_dict(self) -> dict:
        return {"identificador": self.identificador,
                "descricao": self.descricao, "valores": list(self.valores),
                "citacoes": [c.para_dict() for c in self.citacoes],
                "estado": self.estado.value}


@dataclass(frozen=True)
class ManifestoProveniencia:
    """Conjunto de evidências + afirmações que elas sustentam.

    NÃO é receita técnica: não tem componente, papel de peça, regra dimensional
    nem resultado. Registrar proveniência e registrar composição são coisas
    diferentes, e juntá-las faria a evidência herdar os gates da receita."""
    conjunto: str
    raiz_logica: str
    fontes: tuple[FonteEvidencia, ...] = ()
    afirmacoes: tuple[AfirmacaoDeProveniencia, ...] = ()
    conflitos: tuple[ConflitoRegistrado, ...] = ()
    versao: int = VERSAO_MANIFESTO
    descricao: str | None = None
    notas: tuple[str, ...] = ()

    def __post_init__(self):
        for campo in ("fontes", "afirmacoes", "conflitos", "notas"):
            object.__setattr__(self, campo,
                               como_tupla(getattr(self, campo), campo))

    @property
    def artefatos_externos(self) -> tuple[FonteEvidencia, ...]:
        return tuple(f for f in self.fontes
                     if f.forma_referencia == FORMA_ACERVO_EXTERNO)

    @property
    def total_de_bytes(self) -> int:
        return sum(f.tamanho_bytes or 0 for f in self.artefatos_externos)

    def indice_de_fontes(self) -> dict:
        return indexar_fontes(self.fontes)

    def afirmacao(self, identificador: str):
        for a in self.afirmacoes:
            if a.identificador == identificador:
                return a
        return None

    def fontes_do_tipo(self, tipo: str) -> tuple[FonteEvidencia, ...]:
        return tuple(f for f in self.fontes if f.tipo == tipo)

    def para_dict(self) -> dict:
        return {"versao_manifesto": self.versao, "conjunto": self.conjunto,
                "raiz_logica": self.raiz_logica, "descricao": self.descricao,
                "fontes": [f.para_dict() for f in self.fontes],
                "afirmacoes": [a.para_dict() for a in self.afirmacoes],
                "conflitos": [c.para_dict() for c in self.conflitos],
                "notas": list(self.notas)}


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def _texto(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def _citacoes(bruto, alvo: str) -> tuple[CitacaoDeFonte, ...]:
    saida = []
    for item in (bruto or ()):
        if not isinstance(item, dict):
            raise ReceitaErro(f"{alvo}: citação deve ser mapeamento, "
                              f"veio {type(item).__name__}")
        papel = _texto(item.get("papel"))
        try:
            papel = PapelDaFonte(papel)
        except ValueError as e:
            raise ReceitaErro(
                f"{alvo}: papel desconhecido {papel!r} "
                f"(conhecidos: {[p.value for p in PapelDaFonte]})") from e
        saida.append(CitacaoDeFonte(id_fonte=_texto(item.get("id_fonte")) or "",
                                    papel=papel,
                                    observacao=_texto(item.get("observacao"))))
    return tuple(saida)


def _fonte_do_artefato(artefato: dict, grupo: dict, raiz_logica: str,
                       conjunto: str) -> FonteEvidencia:
    """Artefato + semântica do grupo -> `FonteEvidencia`.

    O grupo carrega tipo, estado e abrangência para que 112 artefatos não
    repitam a mesma decisão 112 vezes — e para que mudar a classificação de um
    grupo seja uma linha, revisável, e não um achado perdido no meio da lista."""
    descricao = (_texto(artefato.get("descricao"))
                 or _texto(grupo.get("descricao")) or "")
    caso = _texto(artefato.get("caso")) or _texto(grupo.get("caso"))
    if caso:
        descricao = f"{descricao} [{caso}]" if descricao else f"[{caso}]"
    return FonteEvidencia(
        id_fonte=_texto(artefato.get("id_fonte")) or "",
        tipo=_texto(artefato.get("tipo")) or _texto(grupo.get("tipo")) or "",
        referencia=_texto(artefato.get("caminho_relativo")) or "",
        descricao=descricao,
        estado=EstadoConhecimento(
            _texto(artefato.get("estado")) or _texto(grupo.get("estado"))
            or EstadoConhecimento.PENDENTE.value),
        responsavel=(_texto(artefato.get("responsavel"))
                     or _texto(grupo.get("responsavel"))),
        data=_texto(artefato.get("data")) or _texto(grupo.get("data")),
        forma_referencia=FORMA_ACERVO_EXTERNO,
        sha256=_texto(artefato.get("sha256")),
        tamanho_bytes=artefato.get("tamanho_bytes"),
        raiz_logica=raiz_logica,
        abrangencia=(_texto(artefato.get("abrangencia"))
                     or _texto(grupo.get("abrangencia"))
                     or ABRANGENCIA_EXEMPLAR),
    )


def manifesto_de_dict(dados: dict) -> ManifestoProveniencia:
    """Constrói o manifesto a partir do documento cru. Recusa o malformado."""
    if not isinstance(dados, dict):
        raise ReceitaErro("manifesto: raiz tem de ser um mapeamento")
    versao = dados.get("versao_manifesto")
    if versao not in VERSOES_SUPORTADAS:
        raise ReceitaErro(
            f"manifesto: versao_manifesto {versao!r} não suportada "
            f"(suportadas: {list(VERSOES_SUPORTADAS)})")
    raiz_logica = _texto(dados.get("raiz_logica")) or ""
    conjunto = _texto(dados.get("conjunto")) or ""

    grupos = {}
    for g in (dados.get("grupos") or ()):
        if not isinstance(g, dict):
            raise ReceitaErro("manifesto: grupo deve ser mapeamento")
        nome = _texto(g.get("grupo"))
        if not nome:
            raise ReceitaErro("manifesto: grupo sem nome")
        if nome in grupos:
            raise ReceitaErro(f"manifesto: grupo repetido: {nome!r}")
        grupos[nome] = g

    fontes = []
    for a in (dados.get("artefatos") or ()):
        if not isinstance(a, dict):
            raise ReceitaErro("manifesto: artefato deve ser mapeamento")
        nome_grupo = _texto(a.get("grupo")) or ""
        if nome_grupo not in grupos:
            raise ReceitaErro(
                f"manifesto: artefato {a.get('id_fonte')!r} referencia grupo "
                f"desconhecido {nome_grupo!r} (conhecidos: {sorted(grupos)})")
        fontes.append(_fonte_do_artefato(a, grupos[nome_grupo], raiz_logica,
                                         conjunto))

    for f in (dados.get("fontes_no_repositorio") or ()):
        if not isinstance(f, dict):
            raise ReceitaErro("manifesto: fonte deve ser mapeamento")
        fontes.append(FonteEvidencia(
            id_fonte=_texto(f.get("id_fonte")) or "",
            tipo=_texto(f.get("tipo")) or "",
            referencia=_texto(f.get("referencia")) or "",
            descricao=_texto(f.get("descricao")) or "",
            estado=EstadoConhecimento(_texto(f.get("estado"))
                                      or EstadoConhecimento.PENDENTE.value),
            responsavel=_texto(f.get("responsavel")),
            data=_texto(f.get("data")),
            forma_referencia=_texto(f.get("forma_referencia")) or "arquivo",
            sha256=_texto(f.get("sha256")),
            tamanho_bytes=f.get("tamanho_bytes"),
            abrangencia=(_texto(f.get("abrangencia"))
                         or ABRANGENCIA_EXEMPLAR)))

    afirmacoes = []
    for a in (dados.get("afirmacoes") or ()):
        if not isinstance(a, dict):
            raise ReceitaErro("manifesto: afirmação deve ser mapeamento")
        ident = _texto(a.get("identificador")) or ""
        afirmacoes.append(AfirmacaoDeProveniencia(
            identificador=ident, texto=_texto(a.get("texto")) or "",
            estado=EstadoConhecimento(_texto(a.get("estado"))
                                      or EstadoConhecimento.PENDENTE.value),
            citacoes=_citacoes(a.get("citacoes"), f"afirmação {ident}"),
            derivada_de=tuple(_texto(x) for x in (a.get("derivada_de") or ())),
            observacao=_texto(a.get("observacao"))))

    conflitos = []
    for c in (dados.get("conflitos") or ()):
        if not isinstance(c, dict):
            raise ReceitaErro("manifesto: conflito deve ser mapeamento")
        ident = _texto(c.get("identificador")) or ""
        conflitos.append(ConflitoRegistrado(
            identificador=ident, descricao=_texto(c.get("descricao")) or "",
            valores=tuple(str(v) for v in (c.get("valores") or ())),
            citacoes=_citacoes(c.get("citacoes"), f"conflito {ident}"),
            estado=EstadoConhecimento(_texto(c.get("estado"))
                                      or EstadoConhecimento.PENDENTE.value)))

    return ManifestoProveniencia(
        conjunto=conjunto, raiz_logica=raiz_logica, versao=versao,
        descricao=_texto(dados.get("descricao")),
        fontes=tuple(fontes), afirmacoes=tuple(afirmacoes),
        conflitos=tuple(conflitos),
        notas=tuple(str(n) for n in (dados.get("notas") or ())))


def carregar_manifesto(caminho) -> ManifestoProveniencia:
    """Lê o manifesto do disco. Não precisa do acervo externo montado."""
    p = Path(caminho)
    if not p.exists():
        raise ReceitaErro(f"manifesto ausente: {p}")
    texto = p.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError as e:                              # pragma: no cover
        raise ReceitaErro(
            f"manifesto em YAML exige PyYAML (requirements.txt): {e}") from e
    try:
        dados = yaml.safe_load(texto)
    except yaml.YAMLError as e:
        raise ReceitaErro(f"YAML inválido em {p}: {e}") from e
    return manifesto_de_dict(dados or {})


# ---------------------------------------------------------------------------
# A. Validação estrutural — roda sem o acervo
# ---------------------------------------------------------------------------

def validar_manifesto(manifesto: ManifestoProveniencia) -> ResultadoValidacao:
    """Coerência interna. Nenhum byte do acervo é lido aqui.

    É a validação que sobrevive ao clone: quem baixa o repositório sem o acervo
    ainda consegue dizer se o manifesto é bem formado, se as citações apontam
    para fontes que existem e se nenhum caminho de máquina vazou para dentro do
    Git."""
    r = ResultadoValidacao.aprovado()

    if manifesto.versao not in VERSOES_SUPORTADAS:
        r = r.somar(_reprovar(manifesto.conjunto or "-",
                              "versão de manifesto não suportada",
                              manifesto.versao, list(VERSOES_SUPORTADAS)))
    if not _RE_RAIZ_LOGICA.fullmatch(manifesto.raiz_logica or ""):
        r = r.somar(_reprovar(manifesto.conjunto or "-",
                              "raiz lógica fora do formato",
                              manifesto.raiz_logica, _RE_RAIZ_LOGICA.pattern))
    try:
        indice = manifesto.indice_de_fontes()
    except ReceitaErro as e:
        return r.somar(_reprovar(manifesto.conjunto or "-",
                                 "registro de fontes inconsistente", str(e),
                                 "um id_fonte por artefato"))

    hashes: dict = {}
    for f in manifesto.artefatos_externos:
        alvo = f.id_fonte
        if f.raiz_logica != manifesto.raiz_logica:
            r = r.somar(_reprovar(alvo, "artefato em outra raiz lógica",
                                  f.raiz_logica, manifesto.raiz_logica))
        motivo = _referencia_de_arquivo_insegura(f.referencia)
        if motivo:
            r = r.somar(_reprovar(alvo, f"caminho inseguro: {motivo}",
                                  f.referencia,
                                  "caminho relativo à raiz lógica"))
        if not f.sha256:
            r = r.somar(_reprovar(alvo, "artefato externo sem sha256", None,
                                  "sha256 do conteúdo"))
        if not f.tamanho_bytes:
            r = r.somar(_reprovar(alvo, "artefato externo sem tamanho", None,
                                  "tamanho em bytes"))
        if f.tipo not in TIPOS_DE_FONTE:
            r = r.somar(_reprovar(alvo, "tipo de fonte desconhecido", f.tipo,
                                  sorted(TIPOS_DE_FONTE)))
        if f.abrangencia not in ABRANGENCIAS_DE_FONTE:
            r = r.somar(_reprovar(alvo, "abrangência desconhecida",
                                  f.abrangencia, sorted(ABRANGENCIAS_DE_FONTE)))
        if f.sha256:
            anterior = hashes.get(f.sha256)
            if anterior:
                r = r.somar(_reprovar(
                    alvo, "dois artefatos com o mesmo conteúdo", f.sha256[:16],
                    f"conteúdo distinto (igual ao de {anterior})"))
            hashes[f.sha256] = alvo

    identificadores = [a.identificador for a in manifesto.afirmacoes]
    repetidos = sorted({i for i in identificadores
                        if identificadores.count(i) > 1})
    if repetidos:
        r = r.somar(_reprovar(manifesto.conjunto or "-",
                              "afirmação repetida", repetidos,
                              "um identificador por afirmação"))

    for a in manifesto.afirmacoes:
        r = r.somar(_validar_afirmacao(a, indice, set(identificadores)))
    for c in manifesto.conflitos:
        for cit in c.citacoes:
            if cit.id_fonte not in indice:
                r = r.somar(_reprovar(c.identificador,
                                      "conflito cita fonte inexistente",
                                      cit.id_fonte, "id_fonte do manifesto"))
    return r


def _validar_afirmacao(a: AfirmacaoDeProveniencia, indice: dict,
                       identificadores: set) -> ResultadoValidacao:
    r = ResultadoValidacao.aprovado()
    for cit in a.citacoes:
        if cit.id_fonte not in indice:
            r = r.somar(_reprovar(a.identificador, "cita fonte inexistente",
                                  cit.id_fonte, "id_fonte do manifesto"))
    for origem in a.derivada_de:
        if origem not in identificadores:
            r = r.somar(_reprovar(a.identificador,
                                  "deriva de afirmação inexistente", origem,
                                  "identificador de afirmação do manifesto"))
        if origem == a.identificador:
            r = r.somar(_reprovar(a.identificador, "afirmação deriva de si",
                                  origem, "outra afirmação"))

    if a.estado not in ESTADOS_CONFIRMADOS:
        return r          # pendente e hipótese não precisam sustentação

    sustentacao = [c for c in a.citacoes if c.sustenta
                   and c.id_fonte in indice
                   and fonte_compativel_com_afirmacao(indice[c.id_fonte],
                                                      a.estado)]
    if not sustentacao:
        r = r.somar(_reprovar(
            a.identificador, "afirmação confirmada sem fonte que a sustente",
            [f"{c.id_fonte}:{c.papel.value}" for c in a.citacoes],
            f"ao menos uma citação {sorted(p.value for p in PAPEIS_QUE_SUSTENTAM)} "
            f"cuja fonte sustente {a.estado.value}"))

    sem_autoridade = [c.id_fonte for c in a.citacoes if c.sustenta
                      and c.id_fonte in indice
                      and indice[c.id_fonte].tipo in TIPOS_SEM_AUTORIDADE_FISICA]
    if sem_autoridade:
        r = r.somar(_reprovar(
            a.identificador, "benchmark ou sistema anterior sustentando "
            "afirmação", sem_autoridade,
            f"papel {PapelDaFonte.CORROBORATIVA.value} — nenhum dos dois viu "
            f"a peça física"))
    return r


# ---------------------------------------------------------------------------
# B. Verificação física — exige o acervo montado
# ---------------------------------------------------------------------------

def verificar_acervo_do_manifesto(manifesto: ManifestoProveniencia,
                                  raizes_fisicas=None) -> ResultadoValidacao:
    """Confere os bytes reais de cada artefato externo. Raiz ausente REPROVA.

    Sem raiz não existe "não deu para conferir": existe "não conferido", que é
    uma reprovação. Devolver aprovado aqui produziria um relatório dizendo que
    112 artefatos foram verificados quando nenhum foi aberto."""
    from .validar import raizes_fisicas_do_ambiente
    raizes = (raizes_fisicas_do_ambiente() if raizes_fisicas is None
              else dict(raizes_fisicas))
    r = ResultadoValidacao.aprovado()
    for f in manifesto.artefatos_externos:
        r = r.somar(verificar_artefato_no_acervo(f, raizes))
    return r
