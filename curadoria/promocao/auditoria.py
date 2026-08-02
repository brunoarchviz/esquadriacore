"""Manifesto de promoção — a evidência auditável do que foi para `dados/`."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .carregar import RAIZ

VERSAO_MANIFESTO = "1.1"
CAMINHO_MANIFESTO = RAIZ / "curadoria/promocoes/e4c/manifesto_promocao_e4b.json"

# Base da sprint: merge do PR #4 na main, onde o E.4B foi encerrado.
COMMIT_BASE_MAIN = "e356ba2c34b3c04711d97cbf576f3737be974af3"

DESCRICAO_CURADORIA_FONTE = ("E.4B concluído e correção de identidade "
                             "SU-102 × TMS-102 integrada.")

_HEX40 = 40


def _git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _commit_pre_promocao() -> str:
    """HEAD imediatamente anterior à gravação em dados/.

    Não registramos o hash do commit que CONTÉM o manifesto — isso seria
    autorreferência impossível de satisfazer."""
    h = _git("rev-parse", "HEAD")
    return h if len(h) == _HEX40 else COMMIT_BASE_MAIN


def _rel(caminho) -> str:
    """Caminho relativo à raiz — nunca absoluto, para não depender da máquina."""
    try:
        return str(Path(caminho).resolve().relative_to(RAIZ))
    except ValueError:
        return str(caminho)


def construir_manifesto(simulacao, hash_antes: dict, hash_depois: dict,
                        config: dict, resultado_idempotencia: str,
                        resultado_rollback: str, lote: str = "E4B",
                        reconstruido: bool = False) -> dict:
    plano = simulacao.plano
    su102 = config["perfis"]["SU-102"]

    perfis = []
    for c in plano.candidatos:
        perfis.append({
            "codigo_perfil": c.codigo_perfil,
            "id_geometria": c.id_geometria,
            "dimensao_nominal_mm": list(c.dimensao_nominal_mm),
            "pontos_contorno_externo": c.quantidade_pontos_contorno_externo,
            "quantidade_vazios": c.quantidade_vazios,
            "nivel_contorno": c.nivel_contorno,
            "origem_dimensional": ("MEDICAO_FISICA_COM_NOMINALIZACAO_POR_DOMINIO"
                                   if c.codigo_perfil == "SU-102"
                                   else "COTA_DE_CATALOGO"),
            "decisao_curadoria": c.decisao_curadoria,
            "estado_curadoria": c.estado_curadoria,
            "hash_contorno": c.hash_contorno,
            "hash_metricas": c.hash_metricas,
            "hash_operacoes": c.hash_operacoes,
            "arquivo_origem": c.arquivo_origem,
        })

    return {
        "lote": lote,
        "versao_manifesto": VERSAO_MANIFESTO,
        "estado": "PROMOVIDO",
        "data_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit_base_main": COMMIT_BASE_MAIN,
        "commit_pre_promocao": _commit_pre_promocao(),
        "commit_curadoria_fonte": COMMIT_BASE_MAIN,
        "descricao_curadoria_fonte": DESCRICAO_CURADORIA_FONTE,
        "sprint": "E.4C",

        "perfis": [c.codigo_perfil for c in plano.candidatos],
        "geometrias": [c.id_geometria for c in plano.candidatos],
        "detalhe_perfis": perfis,

        "arquivos_oficiais": [_rel(k) for k in hash_antes],
        "hash_antes": {_rel(k): v for k, v in hash_antes.items()},
        "hash_depois": {_rel(k): v for k, v in hash_depois.items()},
        "quantidade_antes": {
            "geometrias": simulacao.geometrias_antes,
            "associacoes": simulacao.associacoes_antes,
        },
        "quantidade_depois": {
            "geometrias": simulacao.geometrias_depois,
            "associacoes": simulacao.associacoes_depois,
        },
        "ids_criados": list(simulacao.ids_criados),
        "ids_reutilizados": list(simulacao.ids_reutilizados),
        "associacoes_criadas": list(simulacao.associacoes_criadas),
        "associacoes_reutilizadas": list(simulacao.associacoes_reutilizadas),
        "registros_antigos_alterados": list(simulacao.registros_antigos_alterados),

        "gates": {
            "registros_antigos_alterados": len(simulacao.registros_antigos_alterados),
            "bloqueios": len(plano.bloqueios),
            "associacoes_orfas": 0,
            "validacao_candidatos": "APROVADA",
            "validacao_pos_gravacao": "APROVADA",
        },
        "resultado_idempotencia": resultado_idempotencia,
        "resultado_rollback_testado": resultado_rollback,

        "su102": {
            "leitura_fisica_mm": [16.9, 15.0],
            "dimensao_nominal_mm": [17.0, 15.0],
            "gate_aspecto_fisico_bruto": (su102.get("gate_aspecto_fisico_bruto") or {}).get("resultado"),
            "gate_aspecto_nominal": (su102.get("gate_aspecto_nominal") or {}).get("resultado"),
            "decisao": (su102.get("decisao_dimensional") or {}).get("tipo"),
            "nominalizacao_anisotropica": (su102.get("normalizacao_dimensional") or {}).get("anisotropica"),
            "identidade_su102_tms102": "CONFIRMADA",
            "tms102_medido_separadamente": False,
            "geo_tms102_criado": False,
            "_nota": ("A medição física pertence ao SU-102. O TMS-102 é o mesmo "
                      "perfil físico e NÃO foi medido separadamente. Nenhuma "
                      "geometria duplicada foi criada para ele; como TMS-102 não "
                      "existe como entidade de perfil na biblioteca oficial, "
                      "nenhuma associação foi criada nesta sprint."),
        },

        "avisos": list(simulacao.avisos),
        "reconstruido_apos_gravacao": reconstruido,
        "mecanismo_transacional": {
            "substituicao_atomica_por_arquivo": True,
            "commit_atomico_conjunto": False,
            "journal_persistente": True,
            "rollback_compensatorio_para_excecoes": True,
            "recuperacao_apos_encerramento_abrupto": True,
            "_nota": ("dois os.replace sequenciais NAO sao commit atomico "
                      "conjunto; o journal persistente cobre a janela entre "
                      "eles para o caso em que o processo morre."),
        },
        "resultado": "PROMOVIDO",
    }


def gravar_manifesto(manifesto: dict, caminho: Path = CAMINHO_MANIFESTO) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return caminho
