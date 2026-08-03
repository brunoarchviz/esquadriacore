"""Carregamento das fontes: biblioteca oficial e ficha de campo.

A biblioteca é lida pelo **contrato de consumo**, nunca por `dados/*.json`
direto (ADR-003): a composição não pode depender do formato de armazenamento.

A ficha de campo é o documento que o especialista preenche. Este módulo lê,
valida contra um schema explícito e converte — preservando **todas** as seções.
Campo em branco continua em branco; campo desconhecido reprova com sugestão do
nome certo, em vez de ser ignorado em silêncio.

Duas coisas que este módulo mantém separadas:

```text
campo preenchido     alguém escreveu algo
decisão confirmada   valor + estado confirmado + fonte + autoria do especialista
```

`extrair_campos_preenchidos` responde a primeira; `extrair_decisoes_confirmadas`
responde a segunda. Confundi-las transformaria um rascunho em decisão de
fabricação.
"""
from __future__ import annotations

import difflib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .modelos import (ESTADO_CASO_AGUARDANDO, ESTADO_CASO_PARCIAL,
                      ESTADO_CASO_RECEBIDO, FORMAS_DE_REFERENCIA,
                      FORMATO_DATA, IDENTIFICADORES_DE_CASO, TIPOS_DE_FONTE,
                      AcessorioReal, BagueteReal, CasoRealFabricacao,
                      CorteReal, EstadoConhecimento, FolgaReal, FonteEvidencia,
                      PapelComponente, PerfilNoCasoReal, ReceitaErro,
                      ReferenciaPerfilOficial, ResultadoValidacao,
                      SobreposicaoReal, VidroReal, VistaCasoReal, _RE_DATA)

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


# ---------------------------------------------------------------------------
# Schema da ficha — listas explícitas, nada é aceito por omissão
# ---------------------------------------------------------------------------

CAMPOS_RAIZ = ("versao_ficha", "tipologia", "caso_real", "vista", "perfis",
               "cortes", "vidros", "baguetes", "acessorios", "folgas",
               "sobreposicoes", "croquis", "fontes", "duvidas")
CAMPOS_TIPOLOGIA = ("codigo",)
CAMPOS_CASO_REAL = ("identificador", "largura_total_mm", "altura_total_mm")
CAMPOS_VISTA = ("lado_de_referencia", "folha_trilho_interno",
                "folha_trilho_externo", "sentidos_de_movimento",
                "posicao_do_fecho")
CAMPOS_PERFIL = ("funcao", "quantidade", "orientacao", "observacoes", "fonte")
CAMPOS_CORTE = ("perfil", "comprimento_mm", "quantidade", "angulo", "observacao")
CAMPOS_VIDRO = ("folha", "largura_mm", "altura_mm", "espessura_mm", "observacao")
CAMPOS_BAGUETE = ("perfil", "comprimento_mm", "quantidade", "lado_de_encaixe",
                  "observacao")
CAMPOS_ACESSORIO = ("item", "quantidade", "posicao", "observacao")
CAMPOS_FOLGA = ("entre", "valor_mm", "medido_por", "observacao")
CAMPOS_SOBREPOSICAO = ("entre", "valor_mm", "observacao")
CAMPOS_CROQUI = ("tipo", "referencia", "descricao")
CAMPOS_FONTE = ("tipo", "referencia", "descricao", "estado", "responsavel",
                "data", "forma_referencia")

SECOES_LISTA = ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                "sobreposicoes", "croquis", "fontes", "duvidas")

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
    """Erro de digitação não pode passar em silêncio: `largura_totall_mm` viraria
    medida perdida, e a ficha pareceria completa."""
    r = ResultadoValidacao.aprovado()
    for campo in sorted(set(bloco) - set(permitidos)):
        r = r.somar(_reprovar(f"{alvo}.{campo}",
                              f"campo desconhecido: {campo}", campo,
                              _sugestao(campo, permitidos), origem))
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


def _validar_itens_de_lista(dados: dict, secao: str,
                            origem) -> ResultadoValidacao:
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
        if secao in ("croquis", "fontes"):
            r = r.somar(_validar_referencia(item, alvo, origem,
                                            exige_tipo=(secao == "fontes")))
    return r


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
    if data is not None and not _RE_DATA.fullmatch(data):
        r = r.somar(_reprovar(f"{alvo}.data", "data fora do formato", data,
                              FORMATO_DATA, origem))
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

    caso = dados.get("caso_real")
    if caso is not None and not isinstance(caso, dict):
        r = r.somar(_reprovar("caso_real", "caso_real tem de ser mapeamento",
                              type(caso).__name__, "mapeamento", origem))
        caso = {}
    caso = caso or {}
    r = r.somar(_campos_desconhecidos(caso, CAMPOS_CASO_REAL, "caso_real",
                                      origem))
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
        r = r.somar(_campos_desconhecidos(bloco, CAMPOS_PERFIL,
                                          f"perfis.{codigo}", origem))
        funcao = _texto(bloco.get("funcao"))
        if funcao is not None:
            try:
                PapelComponente(funcao)
            except ValueError:
                r = r.somar(_reprovar(
                    f"perfis.{codigo}.funcao", "função desconhecida", funcao,
                    _sugestao(funcao, [p.value for p in PapelComponente]),
                    origem))
        _, res = _inteiro_positivo(bloco.get("quantidade"),
                                   f"perfis.{codigo}.quantidade", origem)
        r = r.somar(res)

    for secao in SECOES_LISTA:
        r = r.somar(_validar_itens_de_lista(dados, secao, origem))
    return r


# ---------------------------------------------------------------------------
# Conversão — preserva TODAS as seções
# ---------------------------------------------------------------------------

def _extras(item: dict, permitidos) -> tuple:
    """O que a ficha trouxe fora do schema. Guardado, nunca descartado."""
    return tuple(sorted((k, item[k]) for k in set(item) - set(permitidos)))


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
    `CASO_A_PEQUENO`. Todas as seções preenchidas sobrevivem à conversão; o que
    vier fora do schema fica em `dados_adicionais`."""
    estrutura = validar_estrutura_ficha(dados, origem)
    if not estrutura.ok:
        raise ReceitaErro("ficha estruturalmente inválida:\n"
                          + estrutura.descrever())

    caso = dados.get("caso_real") or {}
    vista_bruta = dados.get("vista") or {}
    vista = VistaCasoReal(**{c: _texto(vista_bruta.get(c)) for c in CAMPOS_VISTA})

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
            fonte=_texto(bloco.get("fonte"))))

    cortes = _converter_lista(dados, "cortes", lambda i: CorteReal(
        perfil=_texto(i.get("perfil")),
        comprimento_mm=_dec(i.get("comprimento_mm")),
        quantidade=_int(i.get("quantidade")),
        angulo=_texto(i.get("angulo")), observacao=_texto(i.get("observacao")),
        dados_adicionais=_extras(i, CAMPOS_CORTE)))
    vidros = _converter_lista(dados, "vidros", lambda i: VidroReal(
        folha=_texto(i.get("folha")), largura_mm=_dec(i.get("largura_mm")),
        altura_mm=_dec(i.get("altura_mm")),
        espessura_mm=_dec(i.get("espessura_mm")),
        observacao=_texto(i.get("observacao")),
        dados_adicionais=_extras(i, CAMPOS_VIDRO)))
    baguetes = _converter_lista(dados, "baguetes", lambda i: BagueteReal(
        perfil=_texto(i.get("perfil")),
        comprimento_mm=_dec(i.get("comprimento_mm")),
        quantidade=_int(i.get("quantidade")),
        lado_de_encaixe=_texto(i.get("lado_de_encaixe")),
        observacao=_texto(i.get("observacao")),
        dados_adicionais=_extras(i, CAMPOS_BAGUETE)))
    acessorios = _converter_lista(dados, "acessorios", lambda i: AcessorioReal(
        item=_texto(i.get("item")), quantidade=_int(i.get("quantidade")),
        posicao=_texto(i.get("posicao")), observacao=_texto(i.get("observacao")),
        dados_adicionais=_extras(i, CAMPOS_ACESSORIO)))
    folgas = _converter_lista(dados, "folgas", lambda i: FolgaReal(
        entre=_texto(i.get("entre")), valor_mm=_dec(i.get("valor_mm")),
        medido_por=_texto(i.get("medido_por")),
        observacao=_texto(i.get("observacao")),
        dados_adicionais=_extras(i, CAMPOS_FOLGA)))
    sobreposicoes = _converter_lista(dados, "sobreposicoes",
                                     lambda i: SobreposicaoReal(
        entre=_texto(i.get("entre")), valor_mm=_dec(i.get("valor_mm")),
        observacao=_texto(i.get("observacao")),
        dados_adicionais=_extras(i, CAMPOS_SOBREPOSICAO)))

    croquis = tuple(dict(i) for i in (dados.get("croquis") or [])
                    if isinstance(i, dict))
    fontes = []
    for f in (dados.get("fontes") or []):
        if not isinstance(f, dict) or not _texto(f.get("tipo")):
            continue
        fontes.append(FonteEvidencia(
            tipo=_texto(f["tipo"]), referencia=_texto(f.get("referencia")) or "",
            descricao=_texto(f.get("descricao")) or "",
            estado=EstadoConhecimento(_texto(f.get("estado"))
                                      or EstadoConhecimento.PENDENTE.value),
            responsavel=_texto(f.get("responsavel")), data=_texto(f.get("data")),
            forma_referencia=_texto(f.get("forma_referencia")) or "arquivo"))
    duvidas = tuple(str(d) for d in (dados.get("duvidas") or []) if not _vazio(d))

    parcial = CasoRealFabricacao(
        identificador=_texto(caso.get("identificador")),
        largura_total_mm=_dec(caso.get("largura_total_mm")),
        altura_total_mm=_dec(caso.get("altura_total_mm")),
        vista=vista, perfis=tuple(perfis), cortes=cortes, vidros=vidros,
        baguetes=baguetes, acessorios=acessorios, folgas=folgas,
        sobreposicoes=sobreposicoes, croquis=croquis, fontes=tuple(fontes),
        duvidas=duvidas, estado_validacao=ESTADO_CASO_AGUARDANDO)

    # Uma ficha só com folgas medidas e fotos trouxe dado de campo real. Chamá-la
    # de AGUARDANDO_DADOS apagaria a visita à serralheria.
    if not parcial.secoes_preenchidas:
        estado = ESTADO_CASO_AGUARDANDO
    elif parcial.completo_para_derivacao and parcial.identificador:
        estado = ESTADO_CASO_RECEBIDO
    else:
        estado = ESTADO_CASO_PARCIAL

    from dataclasses import replace
    return replace(parcial, estado_validacao=estado)


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
                                        "campo": campo, "valor": bloco[campo],
                                        "fonte": bloco.get("fonte")})
    for secao in SECOES_LISTA:
        itens = dados.get(secao)
        if not isinstance(itens, list):
            continue
        for i, item in enumerate(itens):
            preenchidos.append({"escopo": secao, "campo": f"[{i}]",
                                "valor": item})
    return tuple(preenchidos)


def extrair_decisoes_confirmadas(dados: dict) -> tuple[dict, ...]:
    """Só o que tem valor, estado confirmado E fonte — e autoria, quando a
    decisão é do especialista.

    Um campo preenchido sem fonte é rascunho; tratá-lo como decisão faria uma
    anotação virar ordem de corte."""
    if not isinstance(dados, dict):
        return ()
    por_tipo = {}
    for f in (dados.get("fontes") or []):
        if isinstance(f, dict) and _texto(f.get("tipo")):
            por_tipo[_texto(f["tipo"])] = f

    confirmadas = []
    perfis = dados.get("perfis")
    if isinstance(perfis, dict):
        for codigo, bloco in perfis.items():
            if not isinstance(bloco, dict):
                continue
            tipo_fonte = _texto(bloco.get("fonte"))
            if not tipo_fonte:
                continue
            fonte = por_tipo.get(tipo_fonte)
            estado = _texto((fonte or {}).get("estado"))
            if not estado:
                continue
            try:
                estado_enum = EstadoConhecimento(estado)
            except ValueError:
                continue
            from .modelos import ESTADOS_CONFIRMADOS
            if estado_enum not in ESTADOS_CONFIRMADOS:
                continue
            if (estado_enum is EstadoConhecimento.CONFIRMADO_ESPECIALISTA
                    and not _texto(fonte.get("responsavel"))):
                continue
            for campo in ("funcao", "quantidade", "orientacao"):
                if not _vazio(bloco.get(campo)):
                    confirmadas.append({
                        "escopo": f"perfis.{codigo}", "campo": campo,
                        "valor": bloco[campo], "fonte": tipo_fonte,
                        "estado": estado, "responsavel": fonte.get("responsavel")})
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
    for campo in CAMPOS_CASO_REAL:
        if _vazio(caso.get(campo)):
            pendencias.append({"escopo": "caso_real", "campo": campo})

    vista = dados.get("vista")
    vista = vista if isinstance(vista, dict) else {}
    for campo in CAMPOS_VISTA:
        if _vazio(vista.get(campo)):
            pendencias.append({"escopo": "vista", "campo": campo})

    perfis = dados.get("perfis")
    perfis = perfis if isinstance(perfis, dict) else {}
    for codigo in PERFIS_SUPREMA_E4C:
        bloco = perfis.get(codigo)
        bloco = bloco if isinstance(bloco, dict) else {}
        for campo in ("funcao", "quantidade", "orientacao", "fonte"):
            if _vazio(bloco.get(campo)):
                pendencias.append({"escopo": f"perfis.{codigo}",
                                   "campo": campo})

    for secao in ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                  "sobreposicoes"):
        if _vazio(dados.get(secao)):
            pendencias.append({"escopo": secao, "campo": "(seção vazia)"})

    duvidas = dados.get("duvidas")
    if isinstance(duvidas, list):
        for i, duvida in enumerate(duvidas):
            pendencias.append({"escopo": "duvidas", "campo": f"[{i}]",
                               "detalhe": duvida})
    return tuple(pendencias)
