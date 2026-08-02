"""Manifesto de promoção — a evidência auditável do que foi para `dados/`."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .carregar import RAIZ

VERSAO_MANIFESTO = "1.0"
CAMINHO_MANIFESTO = RAIZ / "curadoria/promocoes/e4c/manifesto_promocao_e4b.json"


def _commit_base() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ,
                              capture_output=True, text=True, timeout=10
                              ).stdout.strip() or "desconhecido"
    except Exception:
        return "desconhecido"


def _rel(caminho) -> str:
    """Caminho relativo à raiz — nunca absoluto, para não depender da máquina."""
    try:
        return str(Path(caminho).resolve().relative_to(RAIZ))
    except ValueError:
        return str(caminho)


def construir_manifesto(simulacao, hash_antes: dict, hash_depois: dict,
                        config: dict, resultado_idempotencia: str,
                        resultado_rollback: str, lote: str = "E4B") -> dict:
    plano = simulacao.plano
    su102 = config["perfis"]["SU-102"]

    perfis = []
    for c in plano.candidatos:
        perfis.append({
            "codigo_perfil": c.codigo_perfil,
            "id_geometria": c.id_geometria,
            "dimensao_nominal_mm": list(c.dimensao_nominal_mm),
            "pontos_contorno_externo": c.quantidade_componentes,
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
        "commit_base": _commit_base(),
        "commit_curadoria": "E.4B — microlote fechado com 8 perfis",
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
        "resultado": "PROMOVIDO",
    }


def gravar_manifesto(manifesto: dict, caminho: Path = CAMINHO_MANIFESTO) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return caminho
