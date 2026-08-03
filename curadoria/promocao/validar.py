"""Validações do candidato. Cada reprovação nomeia perfil, regra, encontrado,
esperado e arquivo de origem — nunca 'candidato inválido'."""
from __future__ import annotations

from .modelos import (ESTADOS_PROMOVIVEIS, NIVEL_PROMOCAO, PERFIS_E4B,
                      CandidatoPromocao, ResultadoValidacao)

TOL = 1e-6          # tolerância de REPRESENTAÇÃO numérica, não de decisão

SU102 = {
    "leitura_fisica_mm": [16.9, 15.0],
    "dimensao_nominal_mm": [17.0, 15.0],
    "gate_fisico": "REPROVADO",
    "gate_nominal": "APROVADO",
    "decisao": "APROVADO_POR_ARBITRAGEM_DE_DOMINIO_COM_NOMINALIZACAO",
    "fator_x": 1.005917,
    "fator_y": 1.0,
}


def _r(c, regra, enc, esp):
    return ResultadoValidacao.reprovado(c.codigo_perfil, regra, enc, esp,
                                        c.arquivo_origem)


def validar_candidato_fechado(c: CandidatoPromocao, config: dict) -> ResultadoValidacao:
    if c.codigo_perfil not in PERFIS_E4B:
        return _r(c, "perfil fora do microlote E.4B", c.codigo_perfil, list(PERFIS_E4B))
    if c.estado_curadoria not in ESTADOS_PROMOVIVEIS:
        return _r(c, "estado de curadoria não promovível",
                  c.estado_curadoria, sorted(ESTADOS_PROMOVIVEIS))
    ml = config.get("microlote_janela", {})
    if c.codigo_perfil not in (ml.get("perfis_fechados") or []):
        return _r(c, "perfil não consta em microlote_janela.perfis_fechados",
                  c.codigo_perfil, ml.get("perfis_fechados"))
    if ml.get("pendencia_restante"):
        return _r(c, "microlote com pendência restante aberta",
                  ml.get("pendencia_restante"), None)
    return ResultadoValidacao.aprovado()


def validar_id_geometria(c: CandidatoPromocao) -> ResultadoValidacao:
    esperado = f"GEO-{c.codigo_perfil}"
    if c.id_geometria != esperado:
        return _r(c, "id de geometria fora da convenção", c.id_geometria, esperado)
    return ResultadoValidacao.aprovado()


def validar_dimensoes_aprovadas(c: CandidatoPromocao, config: dict) -> ResultadoValidacao:
    p = config["perfis"][c.codigo_perfil]
    esperado = (float(p["largura_mm"]), float(p["altura_mm"]))
    if c.dimensao_nominal_mm != esperado:
        return _r(c, "dimensão divergente do config", c.dimensao_nominal_mm, esperado)
    if any(v <= 0 for v in c.dimensao_nominal_mm):
        return _r(c, "dimensão não positiva", c.dimensao_nominal_mm, "> 0")
    # o artefato de curadoria tem de concordar com a cota
    dc = c.procedencia.get("dimensoes_curadoria_mm") or {}
    medido = (dc.get("largura"), dc.get("altura"))
    if medido != (None, None) and (
            abs((medido[0] or 0) - esperado[0]) > TOL
            or abs((medido[1] or 0) - esperado[1]) > TOL):
        return _r(c, "artefato de curadoria diverge da cota", medido, esperado)
    return ResultadoValidacao.aprovado()


def validar_topologia_aprovada(c: CandidatoPromocao, config: dict) -> ResultadoValidacao:
    esperado = config["perfis"][c.codigo_perfil].get("vazios_esperados")
    if esperado is None:
        return _r(c, "vazios_esperados ausente no config", None, "inteiro >= 0")
    if c.quantidade_vazios != esperado:
        return _r(c, "quantidade de vazios divergente", c.quantidade_vazios, esperado)
    return ResultadoValidacao.aprovado()


def validar_contorno_externo(c: CandidatoPromocao) -> ResultadoValidacao:
    if len(c.contorno_externo) < 3:
        return _r(c, "contorno externo com menos de 3 pontos",
                  len(c.contorno_externo), ">= 3")
    for i, pt in enumerate(c.contorno_externo):
        if len(pt) != 2 or any(not isinstance(v, float) for v in pt):
            return _r(c, f"ponto inválido no índice {i}", pt, "(x: float, y: float)")
        if any(v != v or v in (float("inf"), float("-inf")) for v in pt):
            return _r(c, f"ponto não finito no índice {i}", pt, "valores finitos")
    return ResultadoValidacao.aprovado()


def validar_vazios_internos(c: CandidatoPromocao) -> ResultadoValidacao:
    for j, v in enumerate(c.vazios_internos):
        if len(v) < 3:
            return _r(c, f"vazio {j} com menos de 3 pontos", len(v), ">= 3")
        for i, pt in enumerate(v):
            if len(pt) != 2 or any(v_ != v_ for v_ in pt):
                return _r(c, f"ponto inválido no vazio {j}[{i}]", pt, "(x, y) finitos")
    return ResultadoValidacao.aprovado()


def validar_hashes_curadoria(c: CandidatoPromocao) -> ResultadoValidacao:
    for nome, h in (("contorno", c.hash_contorno), ("metricas", c.hash_metricas),
                    ("operacoes", c.hash_operacoes)):
        if not (isinstance(h, str) and len(h) == 64):
            return _r(c, f"hash de {nome} malformado", h, "sha256 hex de 64 chars")
    return ResultadoValidacao.aprovado()


def validar_procedencia(c: CandidatoPromocao) -> ResultadoValidacao:
    fr = c.procedencia.get("fonte_reproducao") or {}
    for campo in ("fonte_pdf", "pagina_pdf", "roi_norm"):
        if campo not in fr:
            return _r(c, f"procedência sem {campo}", sorted(fr), campo)
    return ResultadoValidacao.aprovado()


def validar_nivel_contorno(c: CandidatoPromocao) -> ResultadoValidacao:
    if c.nivel_contorno != NIVEL_PROMOCAO:
        return _r(c, "nível de contorno incompatível", c.nivel_contorno, NIVEL_PROMOCAO)
    return ResultadoValidacao.aprovado()


def validar_fabricante_derivado(c: CandidatoPromocao) -> ResultadoValidacao:
    from contrato.consumo import _FABRICANTE_POR_PREFIXO
    if c.fabricante not in _FABRICANTE_POR_PREFIXO:
        return _r(c, "prefixo de fabricante desconhecido pelo contrato",
                  c.fabricante, sorted(_FABRICANTE_POR_PREFIXO))
    return ResultadoValidacao.aprovado()


def validar_su102_para_promocao(c: CandidatoPromocao, config: dict) -> ResultadoValidacao:
    """Trava dedicada: a cota do SU-102 não vem de catálogo, e a aprovação é
    arbitragem de domínio. Nada disso pode se perder na promoção."""
    if c.codigo_perfil != "SU-102":
        return ResultadoValidacao.aprovado()
    p = config["perfis"]["SU-102"]

    dec = p.get("decisao_dimensional") or {}
    if dec.get("tipo") != SU102["decisao"]:
        return _r(c, "decisão dimensional alterada", dec.get("tipo"), SU102["decisao"])
    if dec.get("leitura_fisica_mm") != SU102["leitura_fisica_mm"]:
        return _r(c, "leitura física alterada",
                  dec.get("leitura_fisica_mm"), SU102["leitura_fisica_mm"])
    if list(c.dimensao_nominal_mm) != SU102["dimensao_nominal_mm"]:
        return _r(c, "dimensão nominal do SU-102 alterada",
                  list(c.dimensao_nominal_mm), SU102["dimensao_nominal_mm"])

    if (p.get("gate_aspecto_fisico_bruto") or {}).get("resultado") != SU102["gate_fisico"]:
        return _r(c, "gate físico bruto alterado",
                  (p.get("gate_aspecto_fisico_bruto") or {}).get("resultado"),
                  SU102["gate_fisico"])
    if (p.get("gate_aspecto_nominal") or {}).get("resultado") != SU102["gate_nominal"]:
        return _r(c, "gate nominal alterado",
                  (p.get("gate_aspecto_nominal") or {}).get("resultado"),
                  SU102["gate_nominal"])

    n = p.get("normalizacao_dimensional") or {}
    if n.get("anisotropica") is not True:
        return _r(c, "nominalização deixou de ser declarada anisotrópica",
                  n.get("anisotropica"), True)
    if abs((n.get("fator_x") or 0) - SU102["fator_x"]) > TOL:
        return _r(c, "fator_x alterado", n.get("fator_x"), SU102["fator_x"])
    if abs((n.get("fator_y") or 0) - SU102["fator_y"]) > TOL:
        return _r(c, "fator_y alterado", n.get("fator_y"), SU102["fator_y"])

    ident = p.get("identidade_de_perfil") or {}
    if ident.get("confirmada") is not True:
        return _r(c, "identidade SU-102 × TMS-102 não confirmada",
                  ident.get("confirmada"), True)
    ap = (p.get("candidato_compartilhamento") or {}).get("aplicacao_dimensional") or {}
    if ap.get("tms102_medido_separadamente") is not False:
        return _r(c, "registro alega medição separada do TMS-102",
                  ap.get("tms102_medido_separadamente"), False)
    return ResultadoValidacao.aprovado()


def validar_candidato_completo(c: CandidatoPromocao, config: dict) -> ResultadoValidacao:
    r = ResultadoValidacao.aprovado()
    for f in (validar_candidato_fechado, validar_dimensoes_aprovadas,
              validar_topologia_aprovada, validar_su102_para_promocao):
        r = r.somar(f(c, config))
    for f in (validar_id_geometria, validar_contorno_externo,
              validar_vazios_internos, validar_hashes_curadoria,
              validar_procedencia, validar_nivel_contorno,
              validar_fabricante_derivado):
        r = r.somar(f(c))
    return r
