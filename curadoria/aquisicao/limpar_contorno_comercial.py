"""
Limpeza comercial TRANSACIONAL do contorno bruto (diretriz 7.7).
Cada operação: copiar estado → aplicar UMA operação → validar → aceitar ou
rollback → registrar. Zonas protegidas (motivos de gabarito) têm os pontos
travados: a limpeza não os altera além do epsilon seguro.

Operações desta versão:
  snap_eixos       — trechos a ≤5° do eixo alinham à mediana (fora de zonas)
  simplificar      — Douglas-Peucker (shapely simplify) fora de zonas
  remover_carocos  — dentes sem função (fora de zonas); limite operacional
                     0.15 mm — 0.3 mm cortava cantos reais de degrau em
                     chanfro (desvio do canto ao vão ≈ 0.28 mm)
Sem buffer global; suavização de quina NÃO é padrão.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely.geometry import LineString, Point, Polygon

import sys
sys.path.insert(0, "/home/bruno/Documentos/esquadriacore")
from domain.entidades import GeometriaPadrao, validar_contornos, ContornoInvalido
from curadoria.aquisicao import assinatura_topologica
from curadoria.aquisicao.extrair_contorno_raster import (
    f1_tolerante_seguro, rasterizar_vetor)


@dataclass
class RegistroOperacao:
    operacao: str
    aceita: bool
    detalhe: str = ""


@dataclass
class EstadoLimpeza:
    ext: list
    vazios: list
    log: list = field(default_factory=list)


def _em_zona(p, zonas) -> bool:
    return any(z[0] <= p[0] <= z[2] and z[1] <= p[1] <= z[3] for z in zonas)


def _validar(ext, vazios, assinatura, largura_mm, altura_mm,
             mascara=None, f1_min=0.98, area_max=0.035,
             dim_tol_mm=0.10, tolerancia_mm=0.15) -> list[str]:
    try:
        validar_contornos(GeometriaPadrao(
            id="LIMPEZA", contorno_mm=[], status="em_revisao", versao="0",
            contorno_externo=[tuple(p) for p in ext],
            vazios_internos=[[tuple(p) for p in v] for v in vazios]))
    except ContornoInvalido as e:
        return [f"dominio: {e}"]
    poly = Polygon([tuple(p) for p in ext],
                   [[tuple(p) for p in v] for v in vazios])
    if not poly.is_valid or poly.geom_type != "Polygon":
        return ["shapely inválido"]
    violacoes = assinatura_topologica.verificar(
        ext, vazios, assinatura, largura_mm, altura_mm)
    if mascara is not None:
        # diretriz 7.7: dimensões, F1 e área validados POR OPERAÇÃO
        xs = [p[0] for p in ext]
        ys = [p[1] for p in ext]
        larg, alt = max(xs) - min(xs), max(ys) - min(ys)
        if abs(larg - largura_mm) > dim_tol_mm:
            violacoes.append(f"largura {larg:.3f} ≠ {largura_mm}±{dim_tol_mm}")
        if abs(alt - altura_mm) > dim_tol_mm:
            violacoes.append(f"altura {alt:.3f} ≠ {altura_mm}±{dim_tol_mm}")
        h, w = mascara.shape
        vetor = rasterizar_vetor(ext, vazios, largura_mm, altura_mm, w, h)
        px_mm = ((w - 1) / largura_mm + (h - 1) / altura_mm) / 2
        f1 = f1_tolerante_seguro(mascara, vetor, tolerancia_mm * px_mm)["f1"]
        if f1 < f1_min:
            violacoes.append(f"F1 {f1:.4f} < {f1_min}")
        area_ref = max(int(mascara.sum()), 1)
        area = abs(int(vetor.sum()) - int(mascara.sum())) / area_ref
        if area > area_max:
            violacoes.append(f"área {area:.3%} > {area_max:.1%}")
    return violacoes


def _transacao(estado: EstadoLimpeza, nome: str, funcao, assinatura,
               largura_mm, altura_mm, mascara=None, **gates):
    import copy
    ext_novo = copy.deepcopy(estado.ext)
    vazios_novos = copy.deepcopy(estado.vazios)
    ext_novo, vazios_novos, detalhe = funcao(ext_novo, vazios_novos)
    violacoes = _validar(ext_novo, vazios_novos, assinatura,
                         largura_mm, altura_mm, mascara=mascara, **gates)
    if violacoes:
        estado.log.append(RegistroOperacao(nome, False,
                                           "; ".join(violacoes[:3])))
        return estado                     # rollback: estado inalterado
    estado.ext, estado.vazios = ext_novo, vazios_novos
    estado.log.append(RegistroOperacao(nome, True, detalhe))
    return estado


# ---------------------------------------------------------------------------
# Operações
# ---------------------------------------------------------------------------

def _snap_anel(anel, zonas, tol_graus=5.0, comprimento_min=0.8):
    """Alinha ao eixo trechos quase horizontais/verticais (mediana)."""
    n = len(anel)
    ajustados = 0
    i = 0
    while i < n:
        j = i
        # agrupa segmentos consecutivos quase-horizontais
        while j < i + n:
            a, b = anel[j % n], anel[(j + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ang = abs(math.degrees(math.atan2(dy, dx))) % 180
            horizontal = ang <= tol_graus or ang >= 180 - tol_graus
            if not horizontal or ang == 0:
                break
            j += 1
        if j > i:
            pontos = [anel[k % n] for k in range(i, j + 1)]
            if (abs(pontos[-1][0] - pontos[0][0]) >= comprimento_min
                    and not any(_em_zona(p, zonas) for p in pontos)):
                ys = sorted(p[1] for p in pontos)
                mediana = ys[len(ys) // 2]
                for k in range(i, j + 1):
                    anel[k % n] = [anel[k % n][0], round(mediana, 4)]
                ajustados += 1
            i = j
        else:
            i += 1
    # verticais
    i = 0
    while i < n:
        j = i
        while j < i + n:
            a, b = anel[j % n], anel[(j + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ang = abs(math.degrees(math.atan2(dy, dx))) % 180
            vertical = abs(ang - 90) <= tol_graus
            if not vertical or ang == 90:
                break
            j += 1
        if j > i:
            pontos = [anel[k % n] for k in range(i, j + 1)]
            if (abs(pontos[-1][1] - pontos[0][1]) >= comprimento_min
                    and not any(_em_zona(p, zonas) for p in pontos)):
                xs = sorted(p[0] for p in pontos)
                mediana = xs[len(xs) // 2]
                for k in range(i, j + 1):
                    anel[k % n] = [round(mediana, 4), anel[k % n][1]]
                ajustados += 1
            i = j
        else:
            i += 1
    return anel, ajustados


def op_snap_eixos(zonas):
    def fn(ext, vazios):
        ext, a1 = _snap_anel(ext, zonas)
        total = a1
        for v in vazios:
            _, ak = _snap_anel(v, zonas)
            total += ak
        return ext, vazios, f"{total} trechos alinhados"
    return fn


def _simplificar_anel(anel, zonas, eps):
    """Simplifica só os trechos LIVRES (fora de zonas protegidas)."""
    livre = [not _em_zona(p, zonas) for p in anel]
    n = len(anel)
    resultado = []
    i = 0
    while i < n:
        if not livre[i]:
            resultado.append(anel[i]); i += 1
            continue
        j = i
        while j < n and livre[j]:
            j += 1
        trecho = anel[i:j]
        if len(trecho) >= 3:
            ls = LineString(trecho).simplify(eps, preserve_topology=True)
            resultado.extend([[round(x, 4), round(y, 4)]
                              for x, y in ls.coords])
        else:
            resultado.extend(trecho)
        i = j
    return resultado


def op_simplificar(zonas, eps=0.07):
    def fn(ext, vazios):
        antes = len(ext) + sum(len(v) for v in vazios)
        ext = _simplificar_anel(ext, zonas, eps)
        vazios = [_simplificar_anel(v, zonas, eps) for v in vazios]
        depois = len(ext) + sum(len(v) for v in vazios)
        return ext, vazios, f"{antes}→{depois} pontos (eps={eps})"
    return fn


def op_remover_carocos(zonas, tamanho_max=0.3):
    """Remove dentes/oscilações menores que `tamanho_max` mm (fora de zonas):
    ponto cujo desvio da reta vizinha é < tamanho_max e cujos vizinhos são
    quase colineares."""
    def fn(ext, vazios):
        def limpar(anel):
            n = len(anel)
            xs = [p[0] for p in anel]
            ys = [p[1] for p in anel]
            eps = 1e-6
            def extremo(p):
                # pontos que definem o bbox carregam as cotas autoritativas
                return (p[0] <= min(xs) + eps or p[0] >= max(xs) - eps
                        or p[1] <= min(ys) + eps or p[1] >= max(ys) - eps)
            manter = [anel[0]]
            removidos = 0
            for i in range(1, n):
                p = anel[i]
                if _em_zona(p, zonas) or extremo(p):
                    manter.append(p); continue
                a, b = manter[-1], anel[(i + 1) % n]
                ls = LineString([a, b])
                if (0 < ls.length < 2.5
                        and ls.distance(Point(p)) < tamanho_max):
                    removidos += 1
                    continue
                manter.append(p)
            return (manter, removidos) if len(manter) >= 4 else (anel, 0)
        ext2, r1 = limpar(ext)
        total = r1
        vaz2 = []
        for v in vazios:
            vv, rk = limpar(v)
            vaz2.append(vv); total += rk
        return ext2, vaz2, f"{total} caroços removidos"
    return fn


# ---------------------------------------------------------------------------
# Correção local de aba truncada (defeito de ROI, não de limpeza)
# ---------------------------------------------------------------------------

def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _run_circular(anel, y_corte):
    """Índices do ÚNICO run circular contíguo com y >= y_corte.
    Devolve None se não houver run ou se houver mais de um (nesse caso a
    correção não é local e não deve ser aplicada automaticamente)."""
    n = len(anel)
    acima = {i for i, p in enumerate(anel) if p[1] >= y_corte}
    if not acima or len(acima) == n:
        return None
    inicios = [i for i in sorted(acima) if (i - 1) % n not in acima]
    if len(inicios) != 1:
        return None
    run = [inicios[0]]
    while (run[-1] + 1) % n in acima and len(run) < n:
        run.append((run[-1] + 1) % n)
    return run


def op_estender_aba_truncada(ext_fonte, y_corte, tol_junta_mm=0.25):
    """Substitui APENAS o trecho truncado do contorno pelo trecho real medido
    na fonte (mesmo referencial mm: origem no canto inferior-esquerdo do
    componente e mesma escala). Nenhum outro ponto é tocado.

    Uso legítimo: a ROI de aquisição cortou uma aba e o resto do perfil está
    correto. As duas juntas do splice precisam coincidir dentro de
    `tol_junta_mm`, senão a operação se recusa a agir (e a transação registra
    o motivo) — isso impede "consertar" um perfil que na verdade divergiu."""
    def fn(ext, vazios):
        alvo = _run_circular(ext, y_corte)
        fonte = _run_circular(ext_fonte, y_corte)
        if alvo is None or fonte is None:
            return ext, vazios, "trecho truncado não identificado (nada feito)"
        n, nf = len(ext), len(ext_fonte)
        antes = ext[(alvo[0] - 1) % n]
        depois = ext[(alvo[-1] + 1) % n]
        trecho = [list(ext_fonte[i]) for i in fonte]
        junta_ini = _dist(antes, ext_fonte[(fonte[0] - 1) % nf])
        junta_fim = _dist(depois, ext_fonte[(fonte[-1] + 1) % nf])
        if max(junta_ini, junta_fim) > tol_junta_mm:      # tenta invertido
            trecho_inv = list(reversed(trecho))
            ji = _dist(antes, ext_fonte[(fonte[-1] + 1) % nf])
            jf = _dist(depois, ext_fonte[(fonte[0] - 1) % nf])
            if max(ji, jf) > tol_junta_mm:
                return ext, vazios, (
                    f"juntas não coincidem ({junta_ini:.2f}/{junta_fim:.2f} mm "
                    f"> {tol_junta_mm}) — recusado")
            trecho, junta_ini, junta_fim = trecho_inv, ji, jf
        resto = [list(ext[(alvo[-1] + 1 + k) % n]) for k in range(n - len(alvo))]
        novo = trecho + resto
        return novo, vazios, (
            f"aba estendida: {len(alvo)}→{len(trecho)} pontos acima de "
            f"y={y_corte}; juntas {junta_ini:.2f}/{junta_fim:.2f} mm; "
            f"{len(resto)} pontos preservados intactos")
    return fn


# ---------------------------------------------------------------------------
# Sequência padrão
# ---------------------------------------------------------------------------

def limpar(ext, vazios, assinatura: dict, largura_mm: float, altura_mm: float,
           zonas_protegidas=None, eps_simplificacao=0.07,
           mascara_origem=None, f1_min=0.98, area_max=0.035,
           dim_tol_mm=0.10, carocos_max_mm=0.15) -> EstadoLimpeza:
    """Aplica a sequência padrão de limpeza, transacional. `zonas_protegidas`
    = [[x0,y0,x1,y1] mm] derivadas dos motivos esperados (gabaritos).
    Com `mascara_origem`, cada operação também é validada contra F1/área/
    dimensões (diretriz 7.7) — operação que degrada além do gate é revertida."""
    zonas = zonas_protegidas or []
    estado = EstadoLimpeza(ext=[list(p) for p in ext],
                           vazios=[[list(p) for p in v] for v in vazios])
    for nome, fn in [
        ("snap_eixos", op_snap_eixos(zonas)),
        ("simplificar", op_simplificar(zonas, eps_simplificacao)),
        ("remover_carocos", op_remover_carocos(zonas, carocos_max_mm)),
        ("snap_eixos_2", op_snap_eixos(zonas)),
    ]:
        estado = _transacao(estado, nome, fn, assinatura,
                            largura_mm, altura_mm, mascara=mascara_origem,
                            f1_min=f1_min, area_max=area_max,
                            dim_tol_mm=dim_tol_mm)
    return estado
