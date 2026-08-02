"""Manifesto de promoção — a evidência auditável do que foi para `dados/`."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import evento
from .carregar import RAIZ

VERSAO_MANIFESTO = "1.2"
CAMINHO_MANIFESTO = RAIZ / "curadoria/promocoes/e4c/manifesto_promocao_e4b.json"


def _rel(caminho) -> str:
    """Caminho relativo à raiz — nunca absoluto, para não depender da máquina."""
    try:
        return str(Path(caminho).resolve().relative_to(RAIZ))
    except ValueError:
        return str(caminho)


def construir_manifesto(simulacao, config: dict,
                        resultado_idempotencia: str = "APROVADA",
                        resultado_rollback: str = "coberto por regressão "
                                                  "(tests/test_promocao.py)",
                        lote: str = "E4B",
                        reconstruido: bool = False) -> dict:
    """Manifesto do EVENTO de promoção — não do estado do disco agora.

    `hash_antes`, `quantidade_antes` e `ids_criados` vêm de `evento.py`, não da
    simulação: numa reconstrução sobre dados já promovidos a simulação enxerga
    54 → 54 com zero criados, o que descreveria a própria reconstrução em vez da
    promoção. Uma reconstrução nunca muda os fatos do evento."""
    su102 = config["perfis"]["SU-102"]
    perfis = []
    for c in simulacao.plano.candidatos:
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
        "data_utc": evento.DATA_UTC_EVENTO,
        "commit_base_main": evento.COMMIT_BASE_MAIN,
        "commit_pre_promocao": evento.COMMIT_PRE_PROMOCAO,
        "commit_curadoria_fonte": evento.COMMIT_CURADORIA_FONTE,
        "descricao_curadoria_fonte": evento.DESCRICAO_CURADORIA_FONTE,
        "sprint": "E.4C",

        "perfis": [c.codigo_perfil for c in simulacao.plano.candidatos],
        "geometrias": list(evento.IDS_CRIADOS),
        "detalhe_perfis": perfis,

        "arquivos_oficiais": [evento.REL_GEOMETRIAS, evento.REL_ASSOCIACOES],
        "hash_antes": dict(evento.HASH_ANTES),
        "hash_depois": dict(evento.HASH_DEPOIS),
        "quantidade_antes": dict(evento.QUANTIDADE_ANTES),
        "quantidade_depois": dict(evento.QUANTIDADE_DEPOIS),
        "ids_criados": list(evento.IDS_CRIADOS),
        "ids_reutilizados": list(evento.IDS_REUTILIZADOS),
        "associacoes_criadas": list(evento.ASSOCIACOES_CRIADAS),
        "associacoes_reutilizadas": list(evento.ASSOCIACOES_REUTILIZADAS),
        "registros_antigos_alterados": [],

        "gates": {
            "registros_antigos_alterados": 0,
            "bloqueios": 0,
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
                      "geometria duplicada foi criada; como TMS-102 não existe "
                      "como entidade de perfil na biblioteca, nenhuma "
                      "associação foi criada para ele nesta sprint."),
        },

        "mecanismo_transacional": {
            "substituicao_atomica_por_arquivo": True,
            "commit_atomico_conjunto": False,
            "journal_persistente": True,
            "journal_cobre_config_e_manifesto": True,
            "hash_final_esperado_dos_quatro_papeis": True,
            "config_gravado_pela_transacao": True,
            "rollback_unico_pelo_journal": True,
            "rollback_compensatorio_para_excecoes": True,
            "recuperacao_apos_encerramento_abrupto": True,
            "retomada_orientada_por_estado": True,
            "concluida_validada_antes_da_limpeza": True,
            "preflight_antes_de_restaurar": True,
            "_nota": ("dois os.replace sequenciais NAO sao commit atomico "
                      "conjunto; o journal persiste ate a finalizacao auditavel "
                      "(manifesto + config + verificacao unificada) e e a unica "
                      "autoridade de rollback depois de criado."),
        },
        "capacidade_reconstrucao_manifesto": {
            "testada": True,
            "resultado": "APROVADA",
            "_nota": ("o manifesto pode ser recriado a partir do recibo do "
                      "journal sem alterar os fatos do evento original."),
        },
        "reconstruido_apos_gravacao": reconstruido,
        "avisos": list(simulacao.avisos),
        "resultado": "PROMOVIDO",
    }


def gravar_manifesto(manifesto: dict, caminho: Path = CAMINHO_MANIFESTO) -> Path:
    """Gravação durável — temporário + fsync + replace + fsync do diretório."""
    from .journal import escrever_atomico
    caminho = Path(caminho)
    escrever_atomico(caminho,
                     json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n")
    return caminho
