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

def _matriz_rotacao(rx, ry, rz):
    """R = Rz·Ry·Rx sobre o frame local (+X extrusão, +Y contorno[1],
    +Z contorno[0]). Ordem fixada aqui e repetida em qualquer consumidor: uma
    ordem diferente do outro lado giraria a peça para outro lugar."""
    (cx, sx), (cy, sy), (cz, sz) = ((np.cos(np.radians(g)), np.sin(np.radians(g)))
                                    for g in (rx, ry, rz))
    X = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Z @ Y @ X


def _pontos_no_mundo(contorno, avanco, rotacao_graus, posicao_mm,
                     rotacao_xyz=None, posicao_z_mm=0.0, eixo_a_max=None):
    """Seção 2D -> pontos no mundo, na altura `avanco` da extrusão.

    Dois caminhos, e o antigo continua bit a bit o que era:

    ```text
    rotacao_xyz ausente   0/90 = horizontal/vertical, 180/270 = idem
                          espelhados. Caminho histórico, intocado.
    rotacao_xyz presente  três ângulos livres no frame local. Prevalece.
    ```

    O espelho só existe no caminho histórico. Ele não foi levado para o
    caminho novo de propósito: refletir a seção descreveria uma barra que
    nenhuma matriz de extrusão produz (ver `InstanciaCena`)."""
    pts = np.asarray(contorno, dtype=float)
    n = len(pts)
    dx, dy = posicao_mm

    if rotacao_xyz is not None:
        R = _matriz_rotacao(*rotacao_xyz)
        local = np.stack([np.full(n, float(avanco)), pts[:, 1], pts[:, 0]], axis=1)
        return local @ R.T + np.array([dx, dy, float(posicao_z_mm)])

    vertical = abs((rotacao_graus % 180) - 90) < 1e-6
    espelhado = rotacao_graus >= 180 - 1e-6
    ref = pts[:, 0].max() if eixo_a_max is None else eixo_a_max
    a = (ref - pts[:, 0]) if espelhado else pts[:, 0]
    if vertical:
        return np.stack([a + dx, np.full(n, dy + avanco), pts[:, 1]], axis=1)
    return np.stack([np.full(n, dx + avanco), pts[:, 1] + dy, a], axis=1)


def extrudar_perfil(contorno_mm, comprimento_mm, rotacao_graus, posicao_mm,
                    rotacao_xyz=None, posicao_z_mm=0.0):
    """Extrusão de perfil MACIÇO. Ver `_pontos_no_mundo` para a convenção de
    eixos e para a diferença entre o caminho histórico e `rotacao_xyz`."""
    contorno = np.array(contorno_mm, dtype=float)
    n = len(contorno)
    v_inicio = _pontos_no_mundo(contorno, 0.0, rotacao_graus, posicao_mm,
                                rotacao_xyz, posicao_z_mm)
    v_fim = _pontos_no_mundo(contorno, comprimento_mm, rotacao_graus,
                             posicao_mm, rotacao_xyz, posicao_z_mm)

    faces = [v_inicio.tolist(), v_fim.tolist()]
    for i in range(n):
        j = (i + 1) % n
        faces.append(np.array([v_inicio[i], v_inicio[j], v_fim[j], v_fim[i]]).tolist())
    return faces


def extrudar_com_furos(contorno_externo, vazios_internos, comprimento_mm,
                       rotacao_graus, posicao_mm, passo_mm=1.5,
                       rotacao_xyz=None, posicao_z_mm=0.0):
    """Extrusão de perfil OCO (ADR-008, rascunho): paredes do contorno externo
    e de cada vazio interno + tampas em grade que respeitam os furos.

    Validado em protótipo externo (Sprint E.2); portado aqui para a MESMA
    convenção de eixos do extrudar_perfil (o protótipo usava frame próprio,
    que ignoraria rotacao/posicao e reintroduziria o bug de achatamento).

    O espelho do caminho histórico usa como referência o `secao_a.max()` do
    CONTORNO EXTERNO, nunca o de cada polígono isoladamente — os vazios
    internos (furos) têm de espelhar em torno do mesmo eixo do contorno que
    os contém, ou o furo se desloca em relação à parede."""
    eixo_a_max = float(np.asarray(contorno_externo, dtype=float)[:, 0].max())

    def _mapear(pontos_2d, avanco):
        return _pontos_no_mundo(pontos_2d, avanco, rotacao_graus, posicao_mm,
                                rotacao_xyz, posicao_z_mm, eixo_a_max)

    faces = []
    for poligono in [contorno_externo] + list(vazios_internos or []):
        ini = _mapear(poligono, 0.0)
        fim = _mapear(poligono, comprimento_mm)
        n = len(ini)
        for i in range(n):
            j = (i + 1) % n
            faces.append([ini[i].tolist(), ini[j].tolist(),
                          fim[j].tolist(), fim[i].tolist()])
    for avanco in (0.0, comprimento_mm):
        faces.extend(_tampa_com_furos(contorno_externo, vazios_internos or [],
                                      avanco, _mapear, passo_mm))
    return faces


def _tampa_com_furos(externo, vazios, avanco, mapear, passo):
    """Tampa da extrusão triangulada por grade: célula entra se o centro está
    dentro do contorno externo e fora de todos os vazios."""
    from matplotlib.path import Path
    ext = np.asarray(externo, dtype=float)
    xmin, ymin = ext.min(axis=0)
    xmax, ymax = ext.max(axis=0)
    caminho_ext = Path(externo)
    caminhos_vazios = [Path(v) for v in vazios]
    faces = []
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            cx, cy = x + passo / 2, y + passo / 2
            if caminho_ext.contains_point((cx, cy)) and not any(
                    p.contains_point((cx, cy)) for p in caminhos_vazios):
                celula = [(x, y), (x + passo, y),
                          (x + passo, y + passo), (x, y + passo)]
                faces.append(mapear(celula, avanco).tolist())
            y += passo
        x += passo
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

        extra = {"rotacao_xyz": getattr(inst, "rotacao_xyz", None),
                 "posicao_z_mm": getattr(inst, "posicao_z_mm", 0.0)}
        if geo.contorno_externo:
            faces = extrudar_com_furos(geo.contorno_externo, geo.vazios_internos,
                                       inst.comprimento_mm, inst.rotacao_graus,
                                       inst.posicao_mm, **extra)
        else:
            faces = extrudar_perfil(geo.contorno_mm, inst.comprimento_mm,
                                    inst.rotacao_graus, inst.posicao_mm, **extra)
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
