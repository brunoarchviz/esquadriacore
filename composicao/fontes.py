"""Carregamento das fontes: biblioteca oficial e ficha de campo.

A biblioteca é lida pelo **contrato de consumo**, nunca por `dados/*.json`
direto (ADR-003): a composição não pode depender do formato de armazenamento,
e o contrato já devolve DTOs imutáveis com bounding box resolvida.

A ficha de campo é o documento que o especialista preenche. Este módulo lê,
valida a ESTRUTURA e converte — e nada mais. Campo em branco continua em
branco: preencher um vazio com default seria inventar decisão de fabricação.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .modelos import (IDENTIFICADORES_DE_CASO, CasoRealFabricacao,
                      EstadoConhecimento, FonteEvidencia, ReceitaErro,
                      ReferenciaPerfilOficial, ResultadoValidacao,
                      ESTADO_CASO_AGUARDANDO, ESTADO_CASO_RECEBIDO)

RAIZ = Path(__file__).resolve().parents[1]
DIR_INSUMOS = Path(__file__).resolve().parent / "insumos"
MODELO_FICHA = DIR_INSUMOS / "suprema_2f_modelo_preenchimento.yaml"

# Os oito perfis promovidos no E.4C. A receita da Suprema de correr trabalha
# sobre eles; nenhum outro entra sem curadoria própria.
PERFIS_SUPREMA_E4C = ("SU-001", "SU-002", "SU-003", "SU-039",
                      "SU-040", "SU-041", "SU-053", "SU-102")

PREFIXO_FABRICANTE = "ALCOA"

# Campos que a ficha PODE deixar em branco — e que continuarão em branco.
CAMPOS_PERFIL = ("funcao", "quantidade", "orientacao", "observacoes", "fonte")

SECOES_LISTA = ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                "sobreposicoes", "duvidas")


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
# Ficha de campo
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
                f"requirements-curadoria.txt): {e}") from e
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


def _reprovar(alvo, regra, encontrado, esperado, origem):
    return ResultadoValidacao.reprovado(alvo, regra, encontrado, esperado,
                                        str(origem))


def _decimal_positivo(valor, alvo, origem):
    """Devolve (Decimal|None, ResultadoValidacao).

    Vazio é NÃO INFORMADO e passa como `None`. O que reprova é valor presente e
    inválido — texto sem número, zero ou negativo."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, ResultadoValidacao.aprovado()
    try:
        d = Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None, _reprovar(alvo, "medida não numérica", valor,
                               "número em mm", origem)
    if d <= 0:
        return None, _reprovar(alvo, "medida não positiva", str(d),
                               "> 0 (desconhecida = em branco)", origem)
    return d, ResultadoValidacao.aprovado()


def validar_estrutura_ficha(dados: dict, origem: str = "ficha") -> ResultadoValidacao:
    """Estrutura, não conteúdo. Campo em branco é legítimo; campo inventado não."""
    r = ResultadoValidacao.aprovado()

    tip = dados.get("tipologia")
    if not isinstance(tip, dict) or not tip.get("codigo"):
        return _reprovar("tipologia", "ficha sem tipologia.codigo",
                         tip, "{codigo: SUPREMA_CORRER_2F}", origem)

    caso = dados.get("caso_real")
    if caso is not None and not isinstance(caso, dict):
        r = r.somar(_reprovar("caso_real", "caso_real tem de ser mapeamento",
                              type(caso).__name__, "mapeamento", origem))
        caso = {}
    caso = caso or {}
    ident = (caso.get("identificador") or "").strip() or None
    if ident is not None and ident not in IDENTIFICADORES_DE_CASO:
        r = r.somar(_reprovar("caso_real.identificador",
                              "identificador de caso desconhecido", ident,
                              list(IDENTIFICADORES_DE_CASO), origem))
    for campo in ("largura_total_mm", "altura_total_mm"):
        _, res = _decimal_positivo(caso.get(campo), f"caso_real.{campo}", origem)
        r = r.somar(res)

    perfis = dados.get("perfis")
    if perfis is not None and not isinstance(perfis, dict):
        r = r.somar(_reprovar("perfis", "perfis tem de ser mapeamento",
                              type(perfis).__name__, "mapeamento", origem))
        perfis = {}
    for codigo, bloco in (perfis or {}).items():
        if codigo not in PERFIS_SUPREMA_E4C:
            r = r.somar(_reprovar(f"perfis.{codigo}",
                                  "perfil fora do microlote oficial", codigo,
                                  list(PERFIS_SUPREMA_E4C), origem))
            continue
        if bloco is None:
            continue                       # bloco inteiro em branco é legítimo
        if not isinstance(bloco, dict):
            r = r.somar(_reprovar(f"perfis.{codigo}",
                                  "bloco do perfil tem de ser mapeamento",
                                  type(bloco).__name__, "mapeamento", origem))
            continue
        desconhecidos = sorted(set(bloco) - set(CAMPOS_PERFIL))
        if desconhecidos:
            r = r.somar(_reprovar(f"perfis.{codigo}", "campos desconhecidos",
                                  desconhecidos, list(CAMPOS_PERFIL), origem))
        q = bloco.get("quantidade")
        if q is not None and str(q).strip():
            try:
                if int(str(q).strip()) <= 0:
                    raise ValueError
            except ValueError:
                r = r.somar(_reprovar(f"perfis.{codigo}.quantidade",
                                      "quantidade inválida", q,
                                      "inteiro > 0 (desconhecida = em branco)",
                                      origem))

    for secao in SECOES_LISTA:
        v = dados.get(secao)
        if v is not None and not isinstance(v, list):
            r = r.somar(_reprovar(secao, "seção tem de ser lista",
                                  type(v).__name__, "lista", origem))
    return r


def converter_ficha_em_caso_real(dados: dict,
                                 origem: str = "ficha") -> CasoRealFabricacao:
    """Converte SEM completar. O que estiver em branco continua `None`."""
    estrutura = validar_estrutura_ficha(dados, origem)
    if not estrutura.ok:
        raise ReceitaErro("ficha estruturalmente inválida:\n"
                          + estrutura.descrever())
    caso = dados.get("caso_real") or {}
    ident = (caso.get("identificador") or "").strip() or IDENTIFICADORES_DE_CASO[0]
    largura, _ = _decimal_positivo(caso.get("largura_total_mm"), "l", origem)
    altura, _ = _decimal_positivo(caso.get("altura_total_mm"), "a", origem)

    fontes = []
    for f in (dados.get("fontes") or []):
        if isinstance(f, dict) and f.get("tipo") and f.get("referencia"):
            fontes.append(FonteEvidencia(
                tipo=f["tipo"], referencia=f["referencia"],
                descricao=f.get("descricao") or "",
                estado=EstadoConhecimento(
                    f.get("estado") or EstadoConhecimento.PENDENTE.value),
                responsavel=f.get("responsavel"), data=f.get("data")))

    tem_conteudo = any(dados.get(s) for s in ("cortes", "vidros", "acessorios")) \
        or largura is not None or altura is not None
    return CasoRealFabricacao(
        identificador=ident,
        largura_total_mm=largura,
        altura_total_mm=altura,
        cortes=tuple(dados.get("cortes") or ()),
        vidros=tuple(dados.get("vidros") or ()),
        acessorios=tuple(dados.get("acessorios") or ()),
        croquis=tuple(dados.get("croquis") or ()),
        fontes=tuple(fontes),
        estado_validacao=(ESTADO_CASO_RECEBIDO if tem_conteudo
                          else ESTADO_CASO_AGUARDANDO),
    )


def _preenchido(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, dict)):
        return bool(v)
    return True


def extrair_decisoes_confirmadas(dados: dict) -> tuple[dict, ...]:
    """O que a ficha efetivamente respondeu — nada é deduzido do silêncio."""
    decisoes = []
    vista = dados.get("vista") or {}
    for campo, valor in vista.items():
        if _preenchido(valor):
            decisoes.append({"escopo": "vista", "campo": campo,
                             "valor": valor})
    for codigo, bloco in (dados.get("perfis") or {}).items():
        if not isinstance(bloco, dict):
            continue
        for campo in ("funcao", "quantidade", "orientacao"):
            if _preenchido(bloco.get(campo)):
                decisoes.append({"escopo": f"perfis.{codigo}", "campo": campo,
                                 "valor": bloco[campo],
                                 "fonte": bloco.get("fonte")})
    for secao in ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                  "sobreposicoes"):
        for i, item in enumerate(dados.get(secao) or []):
            decisoes.append({"escopo": secao, "campo": f"[{i}]",
                             "valor": item})
    return tuple(decisoes)


def extrair_pendencias(dados: dict) -> tuple[dict, ...]:
    """O que continua sem resposta. Silêncio é pendência, nunca default."""
    pendencias = []
    caso = dados.get("caso_real") or {}
    for campo in ("identificador", "largura_total_mm", "altura_total_mm"):
        if not _preenchido(caso.get(campo)):
            pendencias.append({"escopo": "caso_real", "campo": campo})
    vista = dados.get("vista") or {}
    for campo in ("lado_de_referencia", "folha_trilho_interno",
                  "folha_trilho_externo", "sentidos_de_movimento",
                  "posicao_do_fecho"):
        if not _preenchido(vista.get(campo)):
            pendencias.append({"escopo": "vista", "campo": campo})
    perfis = dados.get("perfis") or {}
    for codigo in PERFIS_SUPREMA_E4C:
        bloco = perfis.get(codigo) or {}
        if not isinstance(bloco, dict):
            bloco = {}
        for campo in ("funcao", "quantidade", "orientacao", "fonte"):
            if not _preenchido(bloco.get(campo)):
                pendencias.append({"escopo": f"perfis.{codigo}",
                                   "campo": campo})
    for secao in ("cortes", "vidros", "baguetes", "acessorios", "folgas",
                  "sobreposicoes"):
        if not _preenchido(dados.get(secao)):
            pendencias.append({"escopo": secao, "campo": "(seção vazia)"})
    for i, duvida in enumerate(dados.get("duvidas") or []):
        pendencias.append({"escopo": "duvidas", "campo": f"[{i}]",
                           "detalhe": duvida})
    return tuple(pendencias)
