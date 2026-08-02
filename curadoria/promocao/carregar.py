"""Carregamento e hashing canônico. Nada aqui altera o conteúdo lido."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .modelos import (LOTES, PERFIS_E4B, ESTADOS_PROMOVIVEIS, NIVEL_PROMOCAO,
                      CandidatoPromocao)

RAIZ = Path(__file__).resolve().parents[2]

CAMINHO_CONFIG = RAIZ / "curadoria/aquisicao/configs/e4b_suprema.json"
CAMINHO_GEOMETRIAS = RAIZ / "dados/geometrias.json"
CAMINHO_ASSOCIACOES = RAIZ / "dados/perfil_geometria.json"
RAIZ_CONTORNOS = RAIZ / "curadoria/contornos"

# Dois layouts convivem em curadoria/contornos/ e ambos são legítimos:
#
#   ATUAL  (SU-001/002/003/039/053/102) — arquivos separados, gerados pelo
#           pipeline E.4B corrente.
#   LEGADO (SU-040/041) — prefixos numéricos, do lote 1; a assinatura e as
#           operações viajam DENTRO do próprio contorno comercial.
#
# O carregador reconhece os dois. Nenhum artefato aprovado é reescrito para
# encaixar num formato único: reprocessar geometria já homologada seria
# refazer curadoria.
LAYOUT_ATUAL = {
    "contorno": "contorno_comercial.json",
    "metricas": "metricas.json",
}
LAYOUT_LEGADO = {
    "contorno": "30_contorno_comercial.json",
    "metricas": "45_metricas_comercial.json",
}

# Fabricante cujo código nomeia o perfil. SU-xxx é o namespace Alcoa — as
# associações existentes provam a convenção (ALCOA-SU-005, CENTENARIO-TMS-005).
# Que o DESENHO tenha vindo do card Centenário não muda o namespace do código:
# são coisas distintas, e a procedência guarda a fonte real.
PREFIXO_FABRICANTE = "ALCOA"


class PromocaoErro(RuntimeError):
    """Falha de carregamento/validação. Sempre nomeia o arquivo."""


# ---------------------------------------------------------------------------
# JSON canônico e hash determinístico
# ---------------------------------------------------------------------------

def serializar_json_canonico(valor: object) -> bytes:
    """Serialização estável: chaves ordenadas, sem espaços supérfluos, UTF-8.

    É a base do hash. Não altera valores — só a representação."""
    return json.dumps(valor, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def calcular_hash_canonico(valor: object) -> str:
    return hashlib.sha256(serializar_json_canonico(valor)).hexdigest()


def hash_arquivo(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------

def _ler_json(caminho: Path) -> dict:
    p = Path(caminho)
    if not p.exists():
        raise PromocaoErro(f"arquivo ausente: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PromocaoErro(f"JSON inválido em {p}: {e}") from e


def carregar_config_e4b(caminho: Path = CAMINHO_CONFIG) -> dict:
    cfg = _ler_json(caminho)
    if "perfis" not in cfg:
        raise PromocaoErro(f"config sem chave 'perfis': {caminho}")
    return cfg


def carregar_geometrias_oficiais(caminho: Path = CAMINHO_GEOMETRIAS) -> dict:
    doc = _ler_json(caminho)
    if "geometrias" not in doc:
        raise PromocaoErro(f"biblioteca sem chave 'geometrias': {caminho}")
    return doc


def carregar_associacoes_oficiais(caminho: Path = CAMINHO_ASSOCIACOES) -> dict:
    doc = _ler_json(caminho)
    if "associacoes" not in doc:
        raise PromocaoErro(f"associações sem chave 'associacoes': {caminho}")
    return doc


def localizar_artefatos_candidato(codigo_perfil: str,
                                  raiz: Path = RAIZ_CONTORNOS) -> dict:
    """Devolve {'contorno','metricas','layout'} — reconhece os dois layouts."""
    base = Path(raiz) / codigo_perfil
    if not base.is_dir():
        raise PromocaoErro(f"{codigo_perfil}: diretório de curadoria ausente: {base}")
    for nome, layout in (("atual", LAYOUT_ATUAL), ("legado", LAYOUT_LEGADO)):
        if (base / layout["contorno"]).exists():
            faltando = [v for v in layout.values() if not (base / v).exists()]
            if faltando:
                raise PromocaoErro(
                    f"{codigo_perfil}: layout {nome} incompleto em {base} — "
                    f"ausentes: {faltando}")
            return {"contorno": base / layout["contorno"],
                    "metricas": base / layout["metricas"],
                    "layout": nome}
    raise PromocaoErro(
        f"{codigo_perfil}: nenhum contorno comercial encontrado em {base} "
        f"(procurados: {LAYOUT_ATUAL['contorno']}, {LAYOUT_LEGADO['contorno']})")


def carregar_contorno_aprovado(codigo_perfil: str, raiz: Path = RAIZ_CONTORNOS) -> dict:
    return _ler_json(localizar_artefatos_candidato(codigo_perfil, raiz)["contorno"])


def carregar_metricas_aprovadas(codigo_perfil: str, raiz: Path = RAIZ_CONTORNOS) -> dict:
    return _ler_json(localizar_artefatos_candidato(codigo_perfil, raiz)["metricas"])


def carregar_assinatura_aprovada(codigo_perfil: str, raiz: Path = RAIZ_CONTORNOS) -> dict:
    """No layout atual é arquivo próprio; no legado vem dentro do contorno."""
    arte = localizar_artefatos_candidato(codigo_perfil, raiz)
    if arte["layout"] == "atual":
        return _ler_json(arte["contorno"].parent / "assinatura_topologica.json")
    return _ler_json(arte["contorno"]).get("assinatura_topologica") or {}


def carregar_operacoes_curadoria(codigo_perfil: str, raiz: Path = RAIZ_CONTORNOS) -> dict:
    arte = localizar_artefatos_candidato(codigo_perfil, raiz)
    if arte["layout"] == "atual":
        return _ler_json(arte["contorno"].parent / "operacoes_limpeza.json")
    return {"operacoes": _ler_json(arte["contorno"]).get("operacoes") or []}


def listar_candidatos_promoviveis(config: dict, lote: str = "E4B") -> tuple[str, ...]:
    if lote not in LOTES:
        raise PromocaoErro(f"lote desconhecido: {lote!r} (conhecidos: {sorted(LOTES)})")
    return LOTES[lote]


def gerar_id_geometria(codigo_perfil: str) -> str:
    return f"GEO-{codigo_perfil}"


def perfil_id_oficial(codigo_perfil: str) -> str:
    return f"{PREFIXO_FABRICANTE}-{codigo_perfil}"


# ---------------------------------------------------------------------------
# Montagem do candidato
# ---------------------------------------------------------------------------

def _tupla_anel(anel) -> tuple:
    return tuple((float(x), float(y)) for x, y in anel)


def montar_candidato(codigo_perfil: str, config: dict,
                     raiz: Path = RAIZ_CONTORNOS) -> CandidatoPromocao:
    """Monta o candidato ou levanta — nunca devolve parcialmente."""
    p = config["perfis"].get(codigo_perfil)
    if p is None:
        raise PromocaoErro(f"{codigo_perfil}: ausente do config de curadoria")

    arte = localizar_artefatos_candidato(codigo_perfil, raiz)
    contorno = _ler_json(arte["contorno"])
    metricas = _ler_json(arte["metricas"])
    operacoes = carregar_operacoes_curadoria(codigo_perfil, raiz)

    externo = _tupla_anel(contorno["contorno_externo"])
    vazios = tuple(_tupla_anel(v) for v in (contorno.get("vazios_internos") or []))

    # A procedência vive em `metricas.procedencia` (layout atual, dict) ou em
    # `contorno.origem` (legado, string livre). No legado ela é reconstruída a
    # partir do config, que é a fonte de verdade da ROI e da página.
    proc = metricas.get("procedencia")
    if not isinstance(proc, dict):
        g = p.get("fonte_geometrica_primaria") or p
        proc = {
            "fonte_reproducao": {
                "fonte_pdf": g.get("fonte_pdf", p.get("fonte_pdf")),
                "pagina_pdf": g.get("pagina_pdf", p.get("pagina_pdf")),
                "roi_norm": g.get("roi_norm", p.get("roi_norm")),
            },
            "origem_legado": contorno.get("origem"),
        }
    proc = dict(proc)
    proc["codigo_perfil"] = codigo_perfil
    proc["layout_artefato"] = arte["layout"]
    proc["dimensoes_curadoria_mm"] = (metricas.get("dimensoes_mm")
                                      or metricas.get("dimensoes_obtidas_mm")
                                      or contorno.get("dimensoes_mm"))

    return CandidatoPromocao(
        codigo_perfil=codigo_perfil,
        id_geometria=gerar_id_geometria(codigo_perfil),
        dimensao_nominal_mm=(float(p["largura_mm"]), float(p["altura_mm"])),
        contorno_externo=externo,
        vazios_internos=vazios,
        quantidade_componentes=len(externo),
        quantidade_vazios=len(vazios),
        nivel_contorno=NIVEL_PROMOCAO,
        fabricante=PREFIXO_FABRICANTE,
        fonte=str(arte["contorno"].relative_to(RAIZ)),
        procedencia=proc,
        hash_contorno=calcular_hash_canonico(contorno),
        hash_metricas=calcular_hash_canonico(metricas),
        hash_operacoes=calcular_hash_canonico(operacoes),
        decisao_curadoria=(p.get("decisao_dimensional") or {}).get("tipo", "COTA_DE_CATALOGO"),
        estado_curadoria=p.get("estado_geometrico") or p.get("estado") or "",
        arquivo_origem=str(arte["contorno"].relative_to(RAIZ)),
    )


def montar_candidatos(config: dict, lote: str = "E4B",
                      raiz: Path = RAIZ_CONTORNOS) -> tuple[CandidatoPromocao, ...]:
    return tuple(montar_candidato(c, config, raiz)
                 for c in listar_candidatos_promoviveis(config, lote))
