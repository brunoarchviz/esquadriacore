"""Carregamento das fontes: biblioteca oficial e ficha de campo.

A biblioteca é lida pelo **contrato de consumo**, nunca por `dados/*.json`
direto (ADR-003): a composição não pode depender do formato de armazenamento.

A ficha de campo é o documento que o especialista preenche. Este módulo lê,
valida contra um schema explícito e converte — preservando **todas** as seções.

Três regras que este módulo aplica sem exceção:

```text
evidência é citada por ID          `fontes_ids: [FONTE-001]`, nunca por tipo
cada afirmação tem sua evidência   uma fonte global não confirma seção nenhuma
extensão é explícita               conteúdo livre só dentro de dados_adicionais
```

Campo desconhecido **fora** de `dados_adicionais` reprova com sugestão do nome
certo. `largura_totall_mm` ignorado em silêncio seria uma medida perdida numa
ficha que parece completa.
"""
from __future__ import annotations

import difflib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .modelos import (ESTADO_CASO_AGUARDANDO, ESTADO_CASO_PARCIAL,
                      ESTADOS_CONFIRMADOS,
                      ESTADO_CASO_RECEBIDO, FORMAS_DE_REFERENCIA,
                      FORMATO_DATA, FORMATO_ID_FONTE, IDENTIFICADORES_DE_CASO,
                      TIPOS_DE_FONTE, AcessorioReal, Afirmacao, BagueteReal,
                      CasoRealFabricacao, CorteReal, CroquiCasoReal,
                      EstadoConhecimento, FolgaReal, FonteEvidencia,
                      PapelComponente, PerfilNoCasoReal, ReceitaErro,
                      ReferenciaPerfilOficial, ResultadoValidacao,
                      SobreposicaoReal, VidroReal, VistaCasoReal,
                      _RE_ID_FONTE, data_invalida,
                      incompatibilidades_da_afirmacao)

RAIZ = Path(__file__).resolve().parents[1]
DIR_INSUMOS = Path(__file__).resolve().parent / "insumos"
MODELO_FICHA = DIR_INSUMOS / "suprema_2f_modelo_preenchimento.yaml"

# Os oito perfis promovidos no E.4C. A receita da Suprema de correr trabalha
# sobre eles; nenhum outro entra sem curadoria própria.
PERFIS_SUPREMA_E4C = ("SU-001", "SU-002", "SU-003", "SU-039",
                      "SU-040", "SU-041", "SU-053", "SU-102")

PREFIXO_FABRICANTE = "ALCOA"

CODIGO_TIPOLOGIA_ESPERADO = "SUPREMA_CORRER_2F"
VERSAO_FICHA_SUPORTADA = 1

# Campos que toda afirmação carrega: seu estado e sua evidência, mais o bloco
# explícito de extensão.
CAMPOS_AFIRMACAO = ("estado", "fontes_ids", "dados_adicionais")


# ---------------------------------------------------------------------------
# Schema da ficha — listas explícitas, nada é aceito por omissão
# ---------------------------------------------------------------------------

CAMPOS_RAIZ = ("versao_ficha", "tipologia", "caso_real", "vista", "perfis",
               "cortes", "vidros", "baguetes", "acessorios", "folgas",
               "sobreposicoes", "croquis", "fontes", "duvidas",
               "dados_adicionais")
CAMPOS_TIPOLOGIA = ("codigo",)
CAMPOS_CASO_REAL = ("identificador", "largura_total_mm", "altura_total_mm") \
    + CAMPOS_AFIRMACAO
CAMPOS_VISTA = VistaCasoReal.CAMPOS + CAMPOS_AFIRMACAO
CAMPOS_PERFIL = ("funcao", "quantidade", "orientacao", "observacoes") \
    + CAMPOS_AFIRMACAO
CAMPOS_CORTE = ("perfil", "comprimento_mm", "quantidade", "angulo",
                "observacao") + CAMPOS_AFIRMACAO
CAMPOS_VIDRO = ("folha", "largura_mm", "altura_mm", "espessura_mm",
                "observacao") + CAMPOS_AFIRMACAO
CAMPOS_BAGUETE = ("perfil", "comprimento_mm", "quantidade", "lado_de_encaixe",
                  "observacao") + CAMPOS_AFIRMACAO
CAMPOS_ACESSORIO = ("item", "quantidade", "posicao",
                    "observacao") + CAMPOS_AFIRMACAO
CAMPOS_FOLGA = ("entre", "valor_mm", "medido_por",
                "observacao") + CAMPOS_AFIRMACAO
CAMPOS_SOBREPOSICAO = ("entre", "valor_mm", "observacao") + CAMPOS_AFIRMACAO

# Croqui é evidência visual, não decisão dimensional: ele vira uma
# `FonteEvidencia` própria quando alguém quiser citá-lo. Duas representações do
# mesmo fato — uma com estado e outra sem — entrariam em conflito.
CAMPOS_CROQUI = ("tipo", "referencia", "descricao")
CAMPOS_FONTE = ("id_fonte", "tipo", "referencia", "descricao", "estado",
                "responsavel", "data", "forma_referencia")

SECOES_LISTA = ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                "sobreposicoes", "croquis", "fontes", "duvidas")

# Seções cujos itens são afirmações — cada uma com estado e evidência próprios.
SECOES_DE_AFIRMACAO = ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                       "sobreposicoes")

# Campos numéricos por seção — presentes, têm de ser Decimal positivo.
MEDIDAS_POR_SECAO = {
    "cortes": ("comprimento_mm",),
    "vidros": ("largura_mm", "altura_mm", "espessura_mm"),
    "baguetes": ("comprimento_mm",),
    "folgas": ("valor_mm",),
    "sobreposicoes": ("valor_mm",),
}
QUANTIDADES_POR_SECAO = {
    "cortes": ("quantidade",), "baguetes": ("quantidade",),
    "acessorios": ("quantidade",),
}
CAMPOS_POR_SECAO = {
    "cortes": CAMPOS_CORTE, "vidros": CAMPOS_VIDRO, "baguetes": CAMPOS_BAGUETE,
    "acessorios": CAMPOS_ACESSORIO, "folgas": CAMPOS_FOLGA,
    "sobreposicoes": CAMPOS_SOBREPOSICAO, "croquis": CAMPOS_CROQUI,
    "fontes": CAMPOS_FONTE,
}

# Campos "de conteúdo" por seção: usados para saber se a afirmação diz algo.
CONTEUDO_POR_SECAO = {
    "cortes": ("perfil", "comprimento_mm", "quantidade", "angulo"),
    "vidros": ("folha", "largura_mm", "altura_mm", "espessura_mm"),
    "baguetes": ("perfil", "comprimento_mm", "quantidade", "lado_de_encaixe"),
    "acessorios": ("item", "quantidade", "posicao"),
    "folgas": ("entre", "valor_mm", "medido_por"),
    "sobreposicoes": ("entre", "valor_mm"),
}


def id_geometria(codigo_perfil: str) -> str:
    return f"GEO-{codigo_perfil}"


def perfil_id_oficial(codigo_perfil: str) -> str:
    return f"{PREFIXO_FABRICANTE}-{codigo_perfil}"


def referencia_oficial(codigo_perfil: str) -> ReferenciaPerfilOficial:
    return ReferenciaPerfilOficial(
        codigo_perfil=codigo_perfil,
        id_geometria=id_geometria(codigo_perfil),
        perfil_id_oficial=perfil_id_oficial(codigo_perfil))


# ---------------------------------------------------------------------------
# Biblioteca oficial (pelo contrato de consumo)
# ---------------------------------------------------------------------------

def carregar_biblioteca_oficial(caminho_geometrias: str | None = None,
                                caminho_associacoes: str | None = None):
    """Biblioteca imutável pela fronteira pública. Sem tocar em `dados/`."""
    from contrato.consumo import (CAMINHO_ASSOCIACOES, CAMINHO_GEOMETRIAS,
                                  carregar_biblioteca)
    return carregar_biblioteca(caminho_geometrias or CAMINHO_GEOMETRIAS,
                               caminho_associacoes or CAMINHO_ASSOCIACOES)


def indice_de_associacoes(biblioteca) -> dict:
    return {a.perfil_id: a.geometria_padrao_id for a in biblioteca.associacoes}


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def _ler_documento(caminho: Path) -> dict:
    p = Path(caminho)
    if not p.exists():
        raise ReceitaErro(f"ficha ausente: {p}")
    texto = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:                      # pragma: no cover
            raise ReceitaErro(
                f"ficha em YAML exige PyYAML (declarado em "
                f"requirements.txt): {e}") from e
        try:
            dados = yaml.safe_load(texto)
        except yaml.YAMLError as e:
            raise ReceitaErro(f"YAML inválido em {p}: {e}") from e
    else:
        try:
            dados = json.loads(texto)
        except json.JSONDecodeError as e:
            raise ReceitaErro(f"JSON inválido em {p}: {e}") from e
    if dados is None:
        dados = {}
    if not isinstance(dados, dict):
        raise ReceitaErro(f"ficha {p}: raiz tem de ser um mapeamento")
    return dados


def carregar_ficha_campo(caminho: Path) -> dict:
    """Lê a ficha do especialista. NÃO altera o arquivo e não preenche nada."""
    return _ler_documento(Path(caminho))


# ---------------------------------------------------------------------------
# Validação estrutural
# ---------------------------------------------------------------------------

def _reprovar(alvo, regra, encontrado, esperado, origem):
    return ResultadoValidacao.reprovado(alvo, regra, encontrado, esperado,
                                        str(origem))


def _vazio(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, tuple, dict)):
        return not v
    return False


def _sugestao(campo: str, permitidos) -> str:
    perto = difflib.get_close_matches(campo, list(permitidos), n=1, cutoff=0.6)
    return perto[0] if perto else ", ".join(sorted(permitidos))


def _campos_desconhecidos(bloco: dict, permitidos, alvo: str,
                          origem) -> ResultadoValidacao:
    """Erro de digitação não pode passar em silêncio.

    Conteúdo livre legítimo tem lugar próprio: `dados_adicionais`. Fora dele,
    campo desconhecido reprova."""
    r = ResultadoValidacao.aprovado()
    for campo in sorted(set(bloco) - set(permitidos)):
        r = r.somar(_reprovar(
            f"{alvo}.{campo}", f"campo desconhecido: {campo}", campo,
            f"{_sugestao(campo, permitidos)} (conteúdo livre vai em "
            f"dados_adicionais)", origem))
    return r


def _decimal_positivo(valor, alvo, origem):
    """Devolve (Decimal|None, ResultadoValidacao).

    Vazio é NÃO INFORMADO e passa como `None`. O que reprova é valor presente e
    inválido — texto sem número, zero ou negativo."""
    if _vazio(valor):
        return None, ResultadoValidacao.aprovado()
    try:
        d = Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None, _reprovar(alvo, "medida não numérica", valor,
                               "número em mm", origem)
    if not d.is_finite() or d <= 0:
        return None, _reprovar(alvo, "medida não positiva", str(valor),
                               "> 0 (desconhecida = em branco)", origem)
    return d, ResultadoValidacao.aprovado()


def _inteiro_positivo(valor, alvo, origem):
    if _vazio(valor):
        return None, ResultadoValidacao.aprovado()
    try:
        n = int(str(valor).strip())
        if n <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, _reprovar(alvo, "quantidade inválida", valor,
                               "inteiro > 0 (desconhecida = em branco)", origem)
    return n, ResultadoValidacao.aprovado()


def _texto(valor) -> str | None:
    if _vazio(valor):
        return None
    return str(valor).strip()


def _ids_de_fontes(bloco: dict) -> tuple[str, ...]:
    v = bloco.get("fontes_ids")
    if not isinstance(v, list):
        return ()
    return tuple(str(x).strip() for x in v if not _vazio(x))


def _validar_afirmacao(bloco: dict, alvo: str, ids_disponiveis,
                       origem, fontes_tipadas=None) -> ResultadoValidacao:
    """Estado, evidência e bloco de extensão de uma afirmação qualquer.

    Quando as fontes já foram tipadas, cobra também a compatibilidade
    semântica: uma afirmação `CONFIRMADO_CASO_REAL` apoiada só num catálogo é
    erro visível, não uma confirmação que some da lista."""
    r = ResultadoValidacao.aprovado()

    estado = _texto(bloco.get("estado"))
    if estado is not None:
        try:
            EstadoConhecimento(estado)
        except ValueError:
            r = r.somar(_reprovar(
                f"{alvo}.estado", "estado de conhecimento desconhecido", estado,
                _sugestao(estado, [e.value for e in EstadoConhecimento]),
                origem))

    v = bloco.get("fontes_ids")
    if v is not None and not isinstance(v, list):
        r = r.somar(_reprovar(f"{alvo}.fontes_ids",
                              "fontes_ids tem de ser lista",
                              type(v).__name__, "lista de IDs", origem))
    else:
        ids = _ids_de_fontes(bloco)
        vistos = set()
        for i in ids:
            if i in vistos:
                r = r.somar(_reprovar(
                    f"{alvo}.fontes_ids", "fonte repetida na mesma afirmação",
                    i, "cada evidência citada uma vez", origem))
            vistos.add(i)
            if i not in ids_disponiveis:
                r = r.somar(_reprovar(
                    f"{alvo}.fontes_ids", "fonte inexistente", i,
                    sorted(ids_disponiveis) or "nenhuma fonte declarada",
                    origem))

    extra = bloco.get("dados_adicionais")
    if extra is not None and not isinstance(extra, dict):
        r = r.somar(_reprovar(f"{alvo}.dados_adicionais",
                              "dados_adicionais tem de ser mapeamento",
                              type(extra).__name__, "mapeamento", origem))

    if fontes_tipadas and estado is not None and r.ok:
        try:
            estado_enum = EstadoConhecimento(estado)
        except ValueError:
            return r
        if estado_enum in ESTADOS_CONFIRMADOS:
            problemas = incompatibilidades_da_afirmacao(
                estado_enum, _ids_de_fontes(bloco), fontes_tipadas)
            for motivo in problemas:
                r = r.somar(_reprovar(
                    f"{alvo}.fontes_ids", f"evidência não sustenta o estado: "
                    f"{motivo}", estado, "fonte compatível com o estado",
                    origem))
    return r


def _validar_fontes_declaradas(dados: dict, origem) -> tuple[set, ResultadoValidacao]:
    """IDs disponíveis e os problemas do bloco `fontes`."""
    r = ResultadoValidacao.aprovado()
    itens = dados.get("fontes")
    if itens is None:
        return set(), r
    if not isinstance(itens, list):
        return set(), _reprovar("fontes", "seção tem de ser lista",
                                type(itens).__name__, "lista", origem)
    ids = set()
    for i, item in enumerate(itens):
        alvo = f"fontes[{i}]"
        if not isinstance(item, dict):
            r = r.somar(_reprovar(alvo, "item tem de ser mapeamento",
                                  type(item).__name__, "mapeamento", origem))
            continue
        r = r.somar(_campos_desconhecidos(item, CAMPOS_FONTE, alvo, origem))
        id_fonte = _texto(item.get("id_fonte"))
        if id_fonte is None:
            r = r.somar(_reprovar(
                f"{alvo}.id_fonte", "fonte sem id_fonte", None,
                f"{FORMATO_ID_FONTE} — sem ID automático: duas fontes iguais "
                f"ficariam indistinguíveis", origem))
        elif not _RE_ID_FONTE.fullmatch(id_fonte):
            r = r.somar(_reprovar(f"{alvo}.id_fonte", "id_fonte fora do formato",
                                  id_fonte, FORMATO_ID_FONTE, origem))
        elif id_fonte in ids:
            r = r.somar(_reprovar(f"{alvo}.id_fonte", "id_fonte duplicado",
                                  id_fonte, "identificador único", origem))
        else:
            ids.add(id_fonte)
        r = r.somar(_validar_referencia(item, alvo, origem, exige_tipo=True))
    return ids, r


def _validar_referencia(item: dict, alvo: str, origem,
                        exige_tipo: bool) -> ResultadoValidacao:
    r = ResultadoValidacao.aprovado()
    tipo = _texto(item.get("tipo"))
    if tipo and tipo not in TIPOS_DE_FONTE:
        r = r.somar(_reprovar(f"{alvo}.tipo", "tipo de fonte desconhecido",
                              tipo, _sugestao(tipo, TIPOS_DE_FONTE), origem))
    if exige_tipo and not tipo:
        r = r.somar(_reprovar(f"{alvo}.tipo", "fonte sem tipo", None,
                              sorted(TIPOS_DE_FONTE), origem))
    estado = _texto(item.get("estado"))
    if estado is not None:
        try:
            EstadoConhecimento(estado)
        except ValueError:
            r = r.somar(_reprovar(
                f"{alvo}.estado", "estado de conhecimento desconhecido", estado,
                _sugestao(estado, [e.value for e in EstadoConhecimento]),
                origem))
    forma = _texto(item.get("forma_referencia")) or "arquivo"
    if forma not in FORMAS_DE_REFERENCIA:
        r = r.somar(_reprovar(f"{alvo}.forma_referencia",
                              "forma de referência desconhecida", forma,
                              sorted(FORMAS_DE_REFERENCIA), origem))
        forma = "arquivo"
    referencia = _texto(item.get("referencia"))
    if referencia is None:
        r = r.somar(_reprovar(f"{alvo}.referencia", "referência vazia", None,
                              "caminho relativo, identificador ou URL", origem))
    elif forma == "arquivo":
        from .modelos import _referencia_de_arquivo_insegura
        motivo = _referencia_de_arquivo_insegura(referencia)
        if motivo:
            r = r.somar(_reprovar(f"{alvo}.referencia",
                                  f"referência insegura: {motivo}", referencia,
                                  "caminho relativo à raiz do repositório",
                                  origem))
    data = _texto(item.get("data"))
    if data is not None:
        motivo = data_invalida(data)
        if motivo:
            r = r.somar(_reprovar(f"{alvo}.data", f"data {motivo}", data,
                                  f"{FORMATO_DATA} real", origem))
    return r


def fontes_tipadas_da_ficha(dados: dict) -> dict:
    """`id_fonte` -> FonteEvidencia, ignorando as malformadas.

    Fonte malformada já reprovou na validação do bloco `fontes`; aqui ela
    simplesmente não sustenta nada."""
    tipadas = {}
    for f in (dados.get("fontes") or []):
        if not isinstance(f, dict):
            continue
        ident = _texto(f.get("id_fonte"))
        if not ident or ident in tipadas:
            continue
        try:
            tipadas[ident] = FonteEvidencia(
                id_fonte=ident, tipo=_texto(f.get("tipo")) or "",
                referencia=_texto(f.get("referencia")) or "",
                descricao=_texto(f.get("descricao")) or "",
                estado=EstadoConhecimento(_texto(f.get("estado"))
                                          or EstadoConhecimento.PENDENTE.value),
                responsavel=_texto(f.get("responsavel")),
                data=_texto(f.get("data")),
                forma_referencia=(_texto(f.get("forma_referencia"))
                                  or "arquivo"))
        except (ReceitaErro, ValueError):
            continue
    return tipadas


def _validar_itens_de_lista(dados: dict, secao: str, ids_disponiveis,
                            origem, fontes_tipadas=None) -> ResultadoValidacao:
    r = ResultadoValidacao.aprovado()
    itens = dados.get(secao)
    if itens is None:
        return r
    if not isinstance(itens, list):
        return _reprovar(secao, "seção tem de ser lista",
                         type(itens).__name__, "lista", origem)
    if secao == "duvidas":
        return r                       # texto livre: é a voz de quem mediu
    permitidos = CAMPOS_POR_SECAO[secao]
    for i, item in enumerate(itens):
        alvo = f"{secao}[{i}]"
        if not isinstance(item, dict):
            r = r.somar(_reprovar(alvo, "item tem de ser mapeamento",
                                  type(item).__name__, "mapeamento", origem))
            continue
        r = r.somar(_campos_desconhecidos(item, permitidos, alvo, origem))
        for campo in MEDIDAS_POR_SECAO.get(secao, ()):
            _, res = _decimal_positivo(item.get(campo), f"{alvo}.{campo}", origem)
            r = r.somar(res)
        for campo in QUANTIDADES_POR_SECAO.get(secao, ()):
            _, res = _inteiro_positivo(item.get(campo), f"{alvo}.{campo}", origem)
            r = r.somar(res)
        if secao in SECOES_DE_AFIRMACAO:
            r = r.somar(_validar_afirmacao(item, alvo, ids_disponiveis, origem,
                                           fontes_tipadas))
        if secao == "croquis":
            r = r.somar(_validar_referencia(item, alvo, origem,
                                            exige_tipo=False))
    return r


def validar_estrutura_ficha(dados: dict,
                            origem: str = "ficha") -> ResultadoValidacao:
    """Estrutura, não conteúdo. Campo em branco é legítimo; campo inventado não.

    Acumula TODOS os erros: quem preencheu a ficha à mão precisa da lista
    inteira de uma vez, não de um erro por rodada."""
    if not isinstance(dados, dict):
        return _reprovar("raiz", "ficha tem de ser um mapeamento",
                         type(dados).__name__, "mapeamento", origem)
    r = _campos_desconhecidos(dados, CAMPOS_RAIZ, "raiz", origem)

    versao = dados.get("versao_ficha")
    if versao is None:
        r = r.somar(_reprovar("versao_ficha", "ficha sem versao_ficha", None,
                              VERSAO_FICHA_SUPORTADA, origem))
    elif versao != VERSAO_FICHA_SUPORTADA:
        r = r.somar(_reprovar("versao_ficha", "versão de ficha não suportada",
                              versao, VERSAO_FICHA_SUPORTADA, origem))

    tip = dados.get("tipologia")
    if not isinstance(tip, dict):
        r = r.somar(_reprovar("tipologia", "ficha sem bloco tipologia", tip,
                              {"codigo": CODIGO_TIPOLOGIA_ESPERADO}, origem))
    else:
        r = r.somar(_campos_desconhecidos(tip, CAMPOS_TIPOLOGIA, "tipologia",
                                          origem))
        if _texto(tip.get("codigo")) != CODIGO_TIPOLOGIA_ESPERADO:
            r = r.somar(_reprovar("tipologia.codigo",
                                  "código de tipologia divergente",
                                  tip.get("codigo"),
                                  CODIGO_TIPOLOGIA_ESPERADO, origem))

    ids_disponiveis, res_fontes = _validar_fontes_declaradas(dados, origem)
    r = r.somar(res_fontes)
    fontes_tipadas = fontes_tipadas_da_ficha(dados)

    extra_raiz = dados.get("dados_adicionais")
    if extra_raiz is not None and not isinstance(extra_raiz, dict):
        r = r.somar(_reprovar("dados_adicionais",
                              "dados_adicionais tem de ser mapeamento",
                              type(extra_raiz).__name__, "mapeamento", origem))

    caso = dados.get("caso_real")
    if caso is not None and not isinstance(caso, dict):
        r = r.somar(_reprovar("caso_real", "caso_real tem de ser mapeamento",
                              type(caso).__name__, "mapeamento", origem))
        caso = {}
    caso = caso or {}
    r = r.somar(_campos_desconhecidos(caso, CAMPOS_CASO_REAL, "caso_real",
                                      origem))
    r = r.somar(_validar_afirmacao(caso, "caso_real", ids_disponiveis, origem,
                                   fontes_tipadas))
    ident = _texto(caso.get("identificador"))
    if ident is not None and ident not in IDENTIFICADORES_DE_CASO:
        r = r.somar(_reprovar("caso_real.identificador",
                              "identificador de caso desconhecido", ident,
                              list(IDENTIFICADORES_DE_CASO), origem))
    for campo in ("largura_total_mm", "altura_total_mm"):
        _, res = _decimal_positivo(caso.get(campo), f"caso_real.{campo}", origem)
        r = r.somar(res)

    vista = dados.get("vista")
    if vista is not None and not isinstance(vista, dict):
        r = r.somar(_reprovar("vista", "vista tem de ser mapeamento",
                              type(vista).__name__, "mapeamento", origem))
    elif isinstance(vista, dict):
        r = r.somar(_campos_desconhecidos(vista, CAMPOS_VISTA, "vista", origem))
        r = r.somar(_validar_afirmacao(vista, "vista", ids_disponiveis, origem,
                                       fontes_tipadas))

    perfis = dados.get("perfis")
    if perfis is not None and not isinstance(perfis, dict):
        r = r.somar(_reprovar("perfis", "perfis tem de ser mapeamento",
                              type(perfis).__name__, "mapeamento", origem))
        perfis = {}
    for codigo, bloco in (perfis or {}).items():
        if codigo not in PERFIS_SUPREMA_E4C:
            r = r.somar(_reprovar(f"perfis.{codigo}",
                                  "perfil fora do microlote oficial", codigo,
                                  _sugestao(str(codigo), PERFIS_SUPREMA_E4C),
                                  origem))
            continue
        if bloco is None:
            continue                       # bloco inteiro em branco é legítimo
        if not isinstance(bloco, dict):
            r = r.somar(_reprovar(f"perfis.{codigo}",
                                  "bloco do perfil tem de ser mapeamento",
                                  type(bloco).__name__, "mapeamento", origem))
            continue
        alvo = f"perfis.{codigo}"
        r = r.somar(_campos_desconhecidos(bloco, CAMPOS_PERFIL, alvo, origem))
        r = r.somar(_validar_afirmacao(bloco, alvo, ids_disponiveis, origem,
                                       fontes_tipadas))
        funcao = _texto(bloco.get("funcao"))
        if funcao is not None:
            try:
                PapelComponente(funcao)
            except ValueError:
                r = r.somar(_reprovar(
                    f"{alvo}.funcao", "função desconhecida", funcao,
                    _sugestao(funcao, [p.value for p in PapelComponente]),
                    origem))
        _, res = _inteiro_positivo(bloco.get("quantidade"),
                                   f"{alvo}.quantidade", origem)
        r = r.somar(res)

    for secao in SECOES_LISTA:
        if secao == "fontes":
            continue                       # já validada acima
        r = r.somar(_validar_itens_de_lista(dados, secao, ids_disponiveis,
                                            origem, fontes_tipadas))
    return r


# ---------------------------------------------------------------------------
# Conversão — preserva TODAS as seções
# ---------------------------------------------------------------------------

def _afirmacao_kwargs(item: dict) -> dict:
    estado = _texto(item.get("estado"))
    extra = item.get("dados_adicionais")
    return {
        "estado": EstadoConhecimento(estado) if estado else None,
        "fontes_ids": _ids_de_fontes(item),
        "dados_adicionais": dict(extra) if isinstance(extra, dict) else {},
    }


def _converter_lista(dados: dict, secao: str, construir) -> tuple:
    itens = dados.get(secao)
    if not isinstance(itens, list):
        return ()
    return tuple(construir(i) for i in itens if isinstance(i, dict))


def _dec(valor):
    d, _ = _decimal_positivo(valor, "-", "-")
    return d


def _int(valor):
    n, _ = _inteiro_positivo(valor, "-", "-")
    return n


def converter_ficha_em_caso_real(dados: dict,
                                 origem: str = "ficha") -> CasoRealFabricacao:
    """Converte SEM completar e SEM descartar.

    Ficha sem identificador vira caso com `identificador=None` — jamais
    `CASO_A_PEQUENO`. Todas as seções preenchidas sobrevivem à conversão,
    inclusive o conteúdo de `dados_adicionais`, que é preservado **sem
    interpretação**."""
    estrutura = validar_estrutura_ficha(dados, origem)
    if not estrutura.ok:
        raise ReceitaErro("ficha estruturalmente inválida:\n"
                          + estrutura.descrever())

    caso = dados.get("caso_real") or {}
    vista_bruta = dados.get("vista") or {}
    vista = VistaCasoReal(
        **{c: _texto(vista_bruta.get(c)) for c in VistaCasoReal.CAMPOS},
        **_afirmacao_kwargs(vista_bruta))

    perfis = []
    for codigo in PERFIS_SUPREMA_E4C:
        bloco = (dados.get("perfis") or {}).get(codigo) or {}
        if not isinstance(bloco, dict):
            bloco = {}
        funcao = _texto(bloco.get("funcao"))
        perfis.append(PerfilNoCasoReal(
            codigo_perfil=codigo,
            funcao=PapelComponente(funcao) if funcao else None,
            quantidade=_int(bloco.get("quantidade")),
            orientacao=_texto(bloco.get("orientacao")),
            observacoes=_texto(bloco.get("observacoes")),
            **_afirmacao_kwargs(bloco)))

    cortes = _converter_lista(dados, "cortes", lambda i: CorteReal(
        perfil=_texto(i.get("perfil")),
        comprimento_mm=_dec(i.get("comprimento_mm")),
        quantidade=_int(i.get("quantidade")),
        angulo=_texto(i.get("angulo")), observacao=_texto(i.get("observacao")),
        **_afirmacao_kwargs(i)))
    vidros = _converter_lista(dados, "vidros", lambda i: VidroReal(
        folha=_texto(i.get("folha")), largura_mm=_dec(i.get("largura_mm")),
        altura_mm=_dec(i.get("altura_mm")),
        espessura_mm=_dec(i.get("espessura_mm")),
        observacao=_texto(i.get("observacao")), **_afirmacao_kwargs(i)))
    baguetes = _converter_lista(dados, "baguetes", lambda i: BagueteReal(
        perfil=_texto(i.get("perfil")),
        comprimento_mm=_dec(i.get("comprimento_mm")),
        quantidade=_int(i.get("quantidade")),
        lado_de_encaixe=_texto(i.get("lado_de_encaixe")),
        observacao=_texto(i.get("observacao")), **_afirmacao_kwargs(i)))
    acessorios = _converter_lista(dados, "acessorios", lambda i: AcessorioReal(
        item=_texto(i.get("item")), quantidade=_int(i.get("quantidade")),
        posicao=_texto(i.get("posicao")), observacao=_texto(i.get("observacao")),
        **_afirmacao_kwargs(i)))
    folgas = _converter_lista(dados, "folgas", lambda i: FolgaReal(
        entre=_texto(i.get("entre")), valor_mm=_dec(i.get("valor_mm")),
        medido_por=_texto(i.get("medido_por")),
        observacao=_texto(i.get("observacao")), **_afirmacao_kwargs(i)))
    sobreposicoes = _converter_lista(dados, "sobreposicoes",
                                     lambda i: SobreposicaoReal(
        entre=_texto(i.get("entre")), valor_mm=_dec(i.get("valor_mm")),
        observacao=_texto(i.get("observacao")), **_afirmacao_kwargs(i)))
    croquis = _converter_lista(dados, "croquis", lambda i: CroquiCasoReal(
        tipo=_texto(i.get("tipo")), referencia=_texto(i.get("referencia")),
        descricao=_texto(i.get("descricao"))))

    fontes = []
    for f in (dados.get("fontes") or []):
        if not isinstance(f, dict) or not _texto(f.get("id_fonte")):
            continue
        fontes.append(FonteEvidencia(
            id_fonte=_texto(f["id_fonte"]),
            tipo=_texto(f.get("tipo")) or "",
            referencia=_texto(f.get("referencia")) or "",
            descricao=_texto(f.get("descricao")) or "",
            estado=EstadoConhecimento(_texto(f.get("estado"))
                                      or EstadoConhecimento.PENDENTE.value),
            responsavel=_texto(f.get("responsavel")), data=_texto(f.get("data")),
            forma_referencia=_texto(f.get("forma_referencia")) or "arquivo"))
    duvidas = tuple(str(d) for d in (dados.get("duvidas") or []) if not _vazio(d))
    extra_raiz = dados.get("dados_adicionais")

    estado_dim = _texto(caso.get("estado"))
    parcial = CasoRealFabricacao(
        identificador=_texto(caso.get("identificador")),
        largura_total_mm=_dec(caso.get("largura_total_mm")),
        altura_total_mm=_dec(caso.get("altura_total_mm")),
        estado_dimensoes=EstadoConhecimento(estado_dim) if estado_dim else None,
        fontes_ids_dimensoes=_ids_de_fontes(caso),
        vista=vista, perfis=tuple(perfis), cortes=cortes, vidros=vidros,
        baguetes=baguetes, acessorios=acessorios, folgas=folgas,
        sobreposicoes=sobreposicoes, croquis=croquis, fontes=tuple(fontes),
        duvidas=duvidas,
        dados_adicionais=dict(extra_raiz) if isinstance(extra_raiz, dict) else {},
        estado_recebimento=ESTADO_CASO_AGUARDANDO)

    # Uma ficha só com folgas medidas e fotos trouxe dado de campo real. Chamá-la
    # de AGUARDANDO_DADOS apagaria a visita à serralheria.
    if not parcial.secoes_preenchidas:
        estado = ESTADO_CASO_AGUARDANDO
    elif parcial.completo_para_derivacao and parcial.identificador:
        estado = ESTADO_CASO_RECEBIDO
    else:
        estado = ESTADO_CASO_PARCIAL

    from dataclasses import replace
    return replace(parcial, estado_recebimento=estado)


# ---------------------------------------------------------------------------
# Extração — preenchido ≠ confirmado
# ---------------------------------------------------------------------------

def extrair_campos_preenchidos(dados: dict) -> tuple[dict, ...]:
    """Tudo o que alguém escreveu na ficha. Defensivo: tipo errado não derruba.

    Preenchimento **não** é confirmação — ver `extrair_decisoes_confirmadas`."""
    preenchidos = []
    if not isinstance(dados, dict):
        return ()
    caso = dados.get("caso_real")
    if isinstance(caso, dict):
        for campo in CAMPOS_CASO_REAL:
            if not _vazio(caso.get(campo)):
                preenchidos.append({"escopo": "caso_real", "campo": campo,
                                    "valor": caso[campo]})
    vista = dados.get("vista")
    if isinstance(vista, dict):
        for campo, valor in vista.items():
            if not _vazio(valor):
                preenchidos.append({"escopo": "vista", "campo": str(campo),
                                    "valor": valor})
    perfis = dados.get("perfis")
    if isinstance(perfis, dict):
        for codigo, bloco in perfis.items():
            if not isinstance(bloco, dict):
                continue
            for campo in CAMPOS_PERFIL:
                if not _vazio(bloco.get(campo)):
                    preenchidos.append({"escopo": f"perfis.{codigo}",
                                        "campo": campo, "valor": bloco[campo]})
    for secao in SECOES_LISTA:
        itens = dados.get(secao)
        if not isinstance(itens, list):
            continue
        for i, item in enumerate(itens):
            preenchidos.append({"escopo": secao, "campo": f"[{i}]",
                                "valor": item})
    return tuple(preenchidos)


def _indice_de_fontes_da_ficha(dados: dict) -> dict:
    """`id_fonte` -> FonteEvidencia. Duas fontes do mesmo tipo continuam duas."""
    return fontes_tipadas_da_ficha(dados)


def _fonte_valida_para(indice: dict, ids, estado_texto) -> bool:
    """Evidência existente, apta e compatível com o estado da afirmação.

    Uma fonte malformada no documento não confirma nada — e também não pode
    derrubar a extração."""
    try:
        estado = EstadoConhecimento(estado_texto)
    except (ValueError, TypeError):
        return False
    return not incompatibilidades_da_afirmacao(estado, tuple(ids), indice)


def _registrar_confirmacoes(destino: list, escopo: str, bloco: dict,
                            campos, indice: dict) -> None:
    if not isinstance(bloco, dict):
        return
    ids = _ids_de_fontes(bloco)
    estado = _texto(bloco.get("estado"))
    if not _fonte_valida_para(indice, ids, estado):
        return
    for campo in campos:
        if not _vazio(bloco.get(campo)):
            destino.append({"escopo": escopo, "campo": campo,
                            "valor": bloco[campo], "estado": estado,
                            "fontes_ids": list(ids),
                            "responsavel": getattr(indice.get(ids[0]),
                                                   "responsavel", None)})


def extrair_decisoes_confirmadas(dados: dict) -> tuple[dict, ...]:
    """Afirmações confirmadas em TODAS as seções da ficha.

    Uma afirmação só conta quando tem conteúdo, estado confirmado e evidência
    própria existente — e, se for decisão de especialista, autoria completa.
    Uma fonte global no documento não confirma seção nenhuma."""
    if not isinstance(dados, dict):
        return ()
    indice = _indice_de_fontes_da_ficha(dados)
    confirmadas: list[dict] = []

    caso = dados.get("caso_real")
    _registrar_confirmacoes(confirmadas, "caso_real", caso,
                            ("largura_total_mm", "altura_total_mm"), indice)
    _registrar_confirmacoes(confirmadas, "vista", dados.get("vista"),
                            VistaCasoReal.CAMPOS, indice)

    perfis = dados.get("perfis")
    if isinstance(perfis, dict):
        for codigo, bloco in perfis.items():
            _registrar_confirmacoes(confirmadas, f"perfis.{codigo}", bloco,
                                    ("funcao", "quantidade", "orientacao"),
                                    indice)

    for secao in SECOES_DE_AFIRMACAO:
        itens = dados.get(secao)
        if not isinstance(itens, list):
            continue
        for i, item in enumerate(itens):
            _registrar_confirmacoes(confirmadas, f"{secao}[{i}]", item,
                                    CONTEUDO_POR_SECAO[secao], indice)
    return tuple(confirmadas)


def extrair_pendencias(dados: dict) -> tuple[dict, ...]:
    """O que continua sem resposta. Silêncio é pendência, nunca default.

    Defensivo por contrato: recebe ficha malformada e devolve pendências, sem
    `AttributeError` — a CLI não pode explodir por erro de preenchimento."""
    pendencias = []
    if not isinstance(dados, dict):
        return ({"escopo": "raiz", "campo": "(ficha ilegível)"},)

    caso = dados.get("caso_real")
    caso = caso if isinstance(caso, dict) else {}
    for campo in ("identificador", "largura_total_mm", "altura_total_mm"):
        if _vazio(caso.get(campo)):
            pendencias.append({"escopo": "caso_real", "campo": campo})

    vista = dados.get("vista")
    vista = vista if isinstance(vista, dict) else {}
    for campo in VistaCasoReal.CAMPOS:
        if _vazio(vista.get(campo)):
            pendencias.append({"escopo": "vista", "campo": campo})

    perfis = dados.get("perfis")
    perfis = perfis if isinstance(perfis, dict) else {}
    for codigo in PERFIS_SUPREMA_E4C:
        bloco = perfis.get(codigo)
        bloco = bloco if isinstance(bloco, dict) else {}
        for campo in ("funcao", "quantidade", "orientacao", "fontes_ids"):
            if _vazio(bloco.get(campo)):
                pendencias.append({"escopo": f"perfis.{codigo}",
                                   "campo": campo})

    for secao in SECOES_DE_AFIRMACAO:
        if _vazio(dados.get(secao)):
            pendencias.append({"escopo": secao, "campo": "(seção vazia)"})

    duvidas = dados.get("duvidas")
    if isinstance(duvidas, list):
        for i, duvida in enumerate(duvidas):
            pendencias.append({"escopo": "duvidas", "campo": f"[{i}]",
                               "detalhe": duvida})
    return tuple(pendencias)
