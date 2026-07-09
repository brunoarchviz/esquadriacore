"""
EsquadriaCore — core_engine
===========================
Renderer (implementação matplotlib) + resolução de geometria.

Migrado da Fase 0 e da prova de conceito GeometriaPadrao. Zero funcionalidade
nova — inclusive o bug de extrusão achatada corrigido na Fase 0 permanece
corrigido aqui (mapeamento correto dos eixos do contorno por direção de extrusão).

Regras respeitadas:
- Renderer só consome Vista (ADR-002) — as funções de renderização não recebem
  Perfil/fabricante, só geometria resolvida + parâmetros da Vista.
- Resolução via cadeia Perfil -> PerfilGeometria -> GeometriaPadrao (ADR-005).

Nota: implementação matplotlib por restrição de ambiente (Volume 7). O contrato
(Vista entra, imagem sai) é o que importa — trocar para Three.js não altera
nenhum outro módulo.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from domain.entidades import (
    Perfil, PerfilGeometria, GeometriaPadrao, CenaTecnica, Vista,
    GeometryNotFound, MissingComponent, RendererFailure,
)


# ---------------------------------------------------------------------------
# Resolução de geometria (ADR-005)
# ---------------------------------------------------------------------------

def resolver_geometria(perfil: Perfil,
                       associacoes: list[PerfilGeometria],
                       geometrias: dict[str, GeometriaPadrao]) -> GeometriaPadrao:
    """Perfil -> PerfilGeometria -> GeometriaPadrao. O Perfil nunca embute
    geometria; esta função é a única porta de acesso."""
    assoc = next((a for a in associacoes if a.perfil_id == perfil.id), None)
    if assoc is None:
        raise GeometryNotFound(
            f"Perfil {perfil.id} não possui associação PerfilGeometria")
    geo = geometrias.get(assoc.geometria_padrao_id)
    if geo is None:
        raise GeometryNotFound(
            f"GeometriaPadrao {assoc.geometria_padrao_id} não existe "
            f"(referenciada por {perfil.id})")
    return geo


# ---------------------------------------------------------------------------
# Extrusão (migrada da Fase 0, com o bug de achatamento já corrigido)
# ---------------------------------------------------------------------------

def extrudar_perfil(contorno_mm, comprimento_mm, rotacao_graus, posicao_mm):
    contorno = np.array(contorno_mm, dtype=float)
    n = len(contorno)
    dx, dy = posicao_mm
    secao_a = contorno[:, 0]
    secao_b = contorno[:, 1]

    if abs(rotacao_graus - 90) < 1e-6:
        v_inicio = np.stack([secao_a + dx, np.full(n, dy), secao_b], axis=1)
        v_fim = np.stack([secao_a + dx, np.full(n, dy + comprimento_mm), secao_b], axis=1)
    else:
        v_inicio = np.stack([np.full(n, dx), secao_b + dy, secao_a], axis=1)
        v_fim = np.stack([np.full(n, dx + comprimento_mm), secao_b + dy, secao_a], axis=1)

    faces = [v_inicio.tolist(), v_fim.tolist()]
    for i in range(n):
        j = (i + 1) % n
        faces.append(np.array([v_inicio[i], v_inicio[j], v_fim[j], v_fim[i]]).tolist())
    return faces


def sombrear_face(face, cor_base_rgb, direcao_luz=np.array([0.5, 0.4, 0.75])):
    face = np.array(face)
    if len(face) < 3:
        return cor_base_rgb
    v1, v2 = face[1] - face[0], face[2] - face[0]
    normal = np.cross(v1, v2)
    norma = np.linalg.norm(normal)
    if norma == 0:
        return cor_base_rgb
    normal = normal / norma
    luz = direcao_luz / np.linalg.norm(direcao_luz)
    intensidade = max(0.35, abs(np.dot(normal, luz)))
    return tuple(min(1.0, c * intensidade + 0.15 * (1 - intensidade))
                 for c in cor_base_rgb)


def hex_para_rgb(hex_cor):
    hex_cor = hex_cor.lstrip("#")
    return tuple(int(hex_cor[i:i + 2], 16) / 255 for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Renderer (só consome Vista — ADR-002)
# ---------------------------------------------------------------------------

def renderizar(vista: Vista,
               cena: CenaTecnica,
               perfis: dict[str, Perfil],
               associacoes: list[PerfilGeometria],
               geometrias: dict[str, GeometriaPadrao],
               caminho_saida_png: str) -> str:
    """Produz a imagem de uma Vista. Falha explícita (MissingComponent) se a
    Cena referenciar perfil inexistente — o teste que torna o ADR-001
    verificável em runtime (Volume 9)."""
    if vista.cena_id != cena.id:
        raise RendererFailure(
            f"Vista {vista.id} referencia cena {vista.cena_id}, "
            f"mas recebeu {cena.id}")

    fig = plt.figure(figsize=(10, 8), dpi=150)
    ax = fig.add_subplot(111, projection="3d")
    cor_aluminio = hex_para_rgb(vista.cor_aluminio)
    cor_vidro = hex_para_rgb(vista.cor_vidro)

    todos_pontos = []
    for inst in cena.instancias:
        perfil = perfis.get(inst.perfil_id)
        if perfil is None:
            raise MissingComponent(
                f"Cena {cena.id} referencia perfil inexistente: {inst.perfil_id}")
        geo = resolver_geometria(perfil, associacoes, geometrias)

        faces = extrudar_perfil(geo.contorno_mm, inst.comprimento_mm,
                                inst.rotacao_graus, inst.posicao_mm)
        e_vidro = (perfil.categoria == "vidro")
        cor_base = cor_vidro if e_vidro else cor_aluminio
        alpha = vista.opacidade_vidro if e_vidro else 1.0
        cores = [sombrear_face(f, cor_base) for f in faces]
        ax.add_collection3d(Poly3DCollection(
            faces, facecolor=cores, edgecolor="#3a3a3a",
            linewidths=0.3, alpha=alpha))
        todos_pontos.extend(p for f in faces for p in f)

    if not todos_pontos:
        raise RendererFailure(f"Cena {cena.id} não produziu nenhuma face")

    pontos = np.array(todos_pontos)
    margem = 50
    ax.set_xlim(pontos[:, 0].min() - margem, pontos[:, 0].max() + margem)
    ax.set_ylim(pontos[:, 1].min() - margem, pontos[:, 1].max() + margem)
    ax.set_zlim(pontos[:, 2].min() - 100, pontos[:, 2].max() + 100)
    largura = pontos[:, 0].max() - pontos[:, 0].min()
    altura = pontos[:, 1].max() - pontos[:, 1].min()
    profundidade = max(pontos[:, 2].max() - pontos[:, 2].min(), 40) * 3
    ax.set_box_aspect([largura, altura, profundidade])
    ax.view_init(elev=vista.angulo_elevacao_graus, azim=vista.angulo_azimute_graus)
    ax.set_axis_off()
    fig.patch.set_alpha(0)
    plt.tight_layout()
    plt.savefig(caminho_saida_png, transparent=True, bbox_inches="tight")
    plt.close(fig)
    return caminho_saida_png
