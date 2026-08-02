"""Construção dos registros oficiais e detecção de conflitos.

O contorno aprovado é copiado ponto a ponto. Nenhuma simplificação, suavização,
reorientação ou arredondamento acontece aqui."""
from __future__ import annotations

from .carregar import calcular_hash_canonico, gerar_id_geometria, perfil_id_oficial
from .modelos import (AssociacaoPerfilGeometriaProposta, CandidatoPromocao,
                      ConflitoPromocao, GeometriaOficialProposta, PlanoPromocao,
                      ResultadoValidacao)

DATA_CURADORIA = "2026-08-01"      # data da curadoria, não da execução
RESPONSAVEL = "Bruno"

DESCRICOES = {
    "SU-001": "Marco / quadro da janela de correr — família Suprema",
    "SU-002": "Marco / quadro da janela de correr — família Suprema",
    "SU-003": "Marco / quadro da janela de correr — família Suprema",
    "SU-039": "Perfil da folha de correr — família Suprema",
    "SU-040": "Perfil da folha de correr — família Suprema",
    "SU-041": "Perfil da folha de correr — família Suprema",
    "SU-053": "Perfil da folha de correr — família Suprema",
    "SU-102": "Baguete (perímetro do vidro) — família Suprema",
}


# ---------------------------------------------------------------------------
# Normalização SÓ para comparação — nunca aplicada à forma promovida
# ---------------------------------------------------------------------------

def normalizar_numero_sem_alterar_geometria(valor: float) -> float:
    """Colapsa -0.0 em 0.0 e força float. Não arredonda."""
    v = float(valor)
    return 0.0 if v == 0.0 else v


def normalizar_ponto(ponto) -> tuple:
    return tuple(normalizar_numero_sem_alterar_geometria(v) for v in ponto)


def normalizar_contorno_para_comparacao(contorno) -> tuple:
    """Abre o anel (remove repetição de fechamento) e normaliza -0.0.

    Não remove nenhum outro ponto, não reordena e não reorienta."""
    pts = [normalizar_ponto(p) for p in contorno]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return tuple(pts)


def comparar_contornos_exatamente(candidato, promovido) -> ResultadoValidacao:
    a = normalizar_contorno_para_comparacao(candidato)
    b = normalizar_contorno_para_comparacao(promovido)
    if len(a) != len(b):
        return ResultadoValidacao.reprovado(
            "-", "contagem de pontos divergente", len(b), len(a), "dados/geometrias.json")
    for i, (pa, pb) in enumerate(zip(a, b)):
        if pa != pb:
            return ResultadoValidacao.reprovado(
                "-", f"ponto {i} divergente", pb, pa, "dados/geometrias.json")
    return ResultadoValidacao.aprovado()


# ---------------------------------------------------------------------------
# Construção
# ---------------------------------------------------------------------------

def construir_geometria_oficial(c: CandidatoPromocao) -> GeometriaOficialProposta:
    origem = c.procedencia.get("fonte_reproducao") or {}
    nota = (
        f"Promovido do microlote E.4B (sprint E.4C) a partir de "
        f"{c.arquivo_origem}. Curadoria fechada em {DATA_CURADORIA}. "
        f"Nível 2: renderizável comercial — não é CAD, não autoriza fabricação. "
        f"Fonte do desenho: {origem.get('fonte_pdf','?')} p.{origem.get('pagina_pdf','?')}."
    )
    if c.codigo_perfil == "SU-102":
        nota += (
            " Cota não publicada por catálogo nenhum: veio de medição física "
            "repetida (16,9 × 15,0 mm), nominalizada para 17,0 × 15,0 mm por "
            "arbitragem de domínio. SU-102 e TMS-102 são o mesmo perfil físico; "
            "o TMS-102 NÃO foi medido separadamente."
        )
    registro = {
        "id": c.id_geometria,
        "descricao": DESCRICOES[c.codigo_perfil],
        "status": "homologada",
        "versao": "1.0",
        "familia_mercado": "SUPREMA",
        "curado_por": RESPONSAVEL,
        "data_curadoria": DATA_CURADORIA,
        "_nota": nota,
        "contorno_externo": [list(p) for p in c.contorno_externo],
        "vazios_internos": [[list(p) for p in v] for v in c.vazios_internos],
        "nivel_contorno": c.nivel_contorno,
        "status_contorno": "validado_por_pipeline_raster",
        "metodo_contorno": "contorno_externo_vazios_internos",
        "evidencia_contorno": c.arquivo_origem,
    }
    return GeometriaOficialProposta(id=c.id_geometria, registro=registro,
                                    codigo_perfil=c.codigo_perfil)


def construir_associacao_perfil_geometria(c: CandidatoPromocao) -> AssociacaoPerfilGeometriaProposta:
    obs = (f"Promoção oficial do microlote E.4B (sprint E.4C). Contorno "
           f"reproduzível; artefatos em curadoria/contornos/{c.codigo_perfil}/.")
    if c.codigo_perfil == "SU-102":
        obs += (" Dimensão nominal 17,0 × 15,0 mm por arbitragem de domínio "
                "sobre medição física de 16,9 × 15,0 mm.")
    registro = {
        "perfil_id": perfil_id_oficial(c.codigo_perfil),
        "geometria_padrao_id": c.id_geometria,
        "responsavel_homologacao": RESPONSAVEL,
        "metodo_validacao": "pipeline de aquisição raster + gates de curadoria E.4B",
        "data": DATA_CURADORIA,
        "nivel_de_confianca": "alto",
        "observacoes": obs,
    }
    return AssociacaoPerfilGeometriaProposta(
        perfil_id=registro["perfil_id"], geometria_padrao_id=c.id_geometria,
        registro=registro, codigo_perfil=c.codigo_perfil)


def construir_associacao_alias_identico(codigo_alias: str, id_geometria: str,
                                        identidade_confirmada: bool,
                                        prefixo: str = "CENTENARIO"):
    """Alias de outro fabricante para a MESMA extrusão.

    Só é permitido com identidade de produto confirmada — sem isso, associar
    dois códigos à mesma geometria seria afirmar intercambiabilidade não
    curada (ADR-004)."""
    if not identidade_confirmada:
        return None
    registro = {
        "perfil_id": f"{prefixo}-{codigo_alias}",
        "geometria_padrao_id": id_geometria,
        "responsavel_homologacao": RESPONSAVEL,
        "metodo_validacao": "identidade de produto confirmada pelo especialista de domínio",
        "data": DATA_CURADORIA,
        "nivel_de_confianca": "alto",
        "observacoes": (f"{codigo_alias} é o mesmo perfil físico; a dimensão vem "
                        f"da medição do outro código, não de medição própria."),
    }
    return AssociacaoPerfilGeometriaProposta(
        perfil_id=registro["perfil_id"], geometria_padrao_id=id_geometria,
        registro=registro, codigo_perfil=codigo_alias, motivo="alias_identidade")


# ---------------------------------------------------------------------------
# Conflitos
# ---------------------------------------------------------------------------

def detectar_colisao_id_geometria(proposta: GeometriaOficialProposta,
                                  oficiais: dict) -> ConflitoPromocao | None:
    existente = {g["id"]: g for g in oficiais["geometrias"]}.get(proposta.id)
    if existente is None:
        return None
    if calcular_hash_canonico(existente) == calcular_hash_canonico(proposta.registro):
        return ConflitoPromocao("id_ja_promovido_identico", proposta.codigo_perfil,
                                proposta.id, "registro idêntico — idempotência",
                                bloqueante=False)
    return ConflitoPromocao(
        "id_existente_divergente", proposta.codigo_perfil, proposta.id,
        "ID já existe na biblioteca com conteúdo DIFERENTE — promoção bloqueada "
        "para não sobrescrever registro oficial", bloqueante=True)


def detectar_associacao_existente(perfil_id: str, associacoes: dict):
    for a in associacoes["associacoes"]:
        if a["perfil_id"] == perfil_id:
            return a
    return None


def comparar_geometria_existente(proposta: GeometriaOficialProposta,
                                 existente: dict) -> ResultadoValidacao:
    return comparar_contornos_exatamente(
        [tuple(p) for p in proposta.registro["contorno_externo"]],
        [tuple(p) for p in (existente.get("contorno_externo") or [])])


def detectar_ids_duplicados(propostas) -> list[ConflitoPromocao]:
    vistos, dup = set(), []
    for p in propostas:
        if p.id in vistos:
            dup.append(ConflitoPromocao("id_duplicado_no_plano", p.codigo_perfil,
                                        p.id, "mesmo ID proposto duas vezes"))
        vistos.add(p.id)
    return dup


def detectar_perfis_duplicados(associacoes) -> list[ConflitoPromocao]:
    vistos, dup = set(), []
    for a in associacoes:
        if a.perfil_id in vistos:
            dup.append(ConflitoPromocao("perfil_duplicado_no_plano", a.codigo_perfil,
                                        a.perfil_id, "mesmo perfil_id proposto duas vezes"))
        vistos.add(a.perfil_id)
    return dup


def detectar_reutilizacao_incompativel(assoc_propostas, associacoes_oficiais):
    """Perfil já associado a OUTRA geometria: bloqueia."""
    conflitos = []
    for a in assoc_propostas:
        existente = detectar_associacao_existente(a.perfil_id, associacoes_oficiais)
        if existente and existente["geometria_padrao_id"] != a.geometria_padrao_id:
            conflitos.append(ConflitoPromocao(
                "perfil_associado_a_outra_geometria", a.codigo_perfil, a.perfil_id,
                f"já aponta para {existente['geometria_padrao_id']}, "
                f"proposta aponta para {a.geometria_padrao_id}"))
    return conflitos


def construir_plano_promocao(candidatos, oficiais: dict,
                             associacoes: dict, lote: str = "E4B") -> PlanoPromocao:
    ids_oficiais = {g["id"] for g in oficiais["geometrias"]}
    novas, reutilizadas, conflitos = [], [], []

    for c in candidatos:
        prop = construir_geometria_oficial(c)
        colisao = detectar_colisao_id_geometria(prop, oficiais)
        if colisao is not None:
            conflitos.append(colisao)
            if not colisao.bloqueante:
                reutilizadas.append(prop.id)
                continue
            continue
        if prop.id not in ids_oficiais:
            novas.append(prop)

    assoc_novas, assoc_reut = [], []
    for c in candidatos:
        a = construir_associacao_perfil_geometria(c)
        existente = detectar_associacao_existente(a.perfil_id, associacoes)
        if existente is None:
            assoc_novas.append(a)
        elif existente["geometria_padrao_id"] == a.geometria_padrao_id:
            assoc_reut.append(a.perfil_id)

    conflitos += detectar_ids_duplicados(novas)
    conflitos += detectar_perfis_duplicados(assoc_novas)
    conflitos += detectar_reutilizacao_incompativel(assoc_novas, associacoes)

    return PlanoPromocao(
        lote=lote,
        geometrias_novas=tuple(novas),
        geometrias_reutilizadas=tuple(reutilizadas),
        associacoes_novas=tuple(assoc_novas),
        associacoes_reutilizadas=tuple(assoc_reut),
        conflitos=tuple(conflitos),
        candidatos=tuple(candidatos),
    )
