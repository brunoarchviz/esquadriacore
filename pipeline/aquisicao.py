"""
EsquadriaCore — pipeline
========================
Orquestração da aquisição de dados (Volume 6).

O Pipeline recebe um Provider (qualquer implementação do contrato — ADR-003) e
produz Perfis normalizados. Não conhece o formato de origem; não decide
classificação final (isso é Curadoria humana — Volume 2, limites entre módulos).

Zero funcionalidade nova em relação aos protótipos das Fases 1-4.
"""

from domain.entidades import Perfil
from providers.base import Provider


def executar_aquisicao(provider: Provider) -> list[Perfil]:
    """Etapas 1-2 do Pipeline (Volume 6): descoberta + extração.
    Etapas seguintes (validação de qualidade, curadoria) acontecem sobre a
    lista retornada — a curadoria é humana por definição (ADR-005)."""
    perfis = provider.extrair_perfis()
    for p in perfis:
        p.estado_ciclo_vida = "normalizado"
    return perfis


def resumo_extracao(perfis: list[Perfil]) -> dict:
    """Resumo simples para conferência pós-extração (usado nos relatórios das
    Fases 1-4 e agora formalizado)."""
    return {
        "total": len(perfis),
        "com_peso": sum(1 for p in perfis if not p.peso_suspeito),
        "peso_suspeito": [p.codigo_fabricante for p in perfis if p.peso_suspeito],
        "indice_medio_qualidade": (
            round(sum(p.qualidade.indice for p in perfis) / len(perfis), 2)
            if perfis else 0
        ),
    }
