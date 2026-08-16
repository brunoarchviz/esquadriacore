"""
EsquadriaCore — curadoria/composicao/viewport_diagnostica
============================================================
Ferramenta DIAGNÓSTICA de curadoria: gera uma página local onde Bruno gira,
move e isola cada peça da composição Suprema correr 2F até a orientação ficar
visualmente certa, e depois copia o estado ajustado como texto.

NÃO é CAD, não é editor de fabricação, não calcula nada. Existe para eliminar
um gargalo de COMUNICAÇÃO: descrever orientação espacial por texto custa
dezenas de rodadas; apontar na tela custa minutos.

O que entra aqui é o ESTADO ATUAL da composição. A orientação do SU-003 já
passou pela validação visual do Bruno; as demais continuam sendo proposta do
desenho, não afirmação de domínio. A ferramenta não afirma que o estado está
certo; ela existe justamente para Bruno dizer o que está.

```text
composicao/receita.py        topologia confirmada  — NÃO tocado
composicao/visualizacao.py   estado inicial da PR  — só LIDO aqui
este módulo                  ferramenta de curadoria, descartável
```

O que Bruno ajustar aqui NÃO vira regra nem volta sozinho para o código: ele
copia o texto exportado, e a tradução para `composicao/visualizacao.py` é uma
rodada posterior, revisada.

Uso:  python3 curadoria/composicao/viewport_diagnostica.py
Saída: curadoria/composicao/viewport_suprema_2f.html (abrir no navegador)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import numpy as np

from composicao.modelos import PapelComponente
from composicao.receita import construir_receita_preliminar
from composicao.visualizacao import montar_cena_suprema_2f
from contrato.consumo import carregar_biblioteca
from core_engine.renderer import extrudar_perfil, resolver_geometria
from domain.entidades import Perfil

AQUI = os.path.dirname(os.path.abspath(__file__))
MODELO = os.path.join(AQUI, "viewport_template.html")
SAIDA = os.path.join(AQUI, "viewport_suprema_2f.html")

# Qual grupo de validação cada papel pertence. A ordem dos grupos é a ordem de
# fechamento acordada: quadro primeiro, folhas depois, baguetes por último.
GRUPO_DO_PAPEL = {
    PapelComponente.MARCO_SUPERIOR: "QUADRO",
    PapelComponente.MARCO_INFERIOR: "QUADRO",
    PapelComponente.MARCO_LATERAL: "QUADRO",
    PapelComponente.MONTANTE_LATERAL_FOLHA: "FOLHAS",
    PapelComponente.MONTANTE_CENTRAL_FOLHA: "FOLHAS",
    PapelComponente.TRAVESSA_SUPERIOR_FOLHA: "FOLHAS",
    PapelComponente.TRAVESSA_INFERIOR_FOLHA: "FOLHAS",
    PapelComponente.BAGUETE: "BAGUETES",
}


# ---------------------------------------------------------------------------
# Modelo de transformação exposto a Bruno
#
# A peça vive num FRAME LOCAL fixo:
#     +X local = direção de extrusão (o comprimento da barra)
#     +Y local = segunda coordenada do contorno
#     +Z local = primeira coordenada do contorno
#
# Sobre ela: rotação em passos de 90° (rx, ry, rz), depois translação
# (tx, ty, tz). É o MESMO frame que `composicao.visualizacao` usa, então o que
# Bruno vê aqui e o que a imagem oficial desenha não podem divergir.
# ---------------------------------------------------------------------------

def _rot(eixo: str, graus: float) -> np.ndarray:
    c, s = np.cos(np.radians(graus)), np.sin(np.radians(graus))
    if eixo == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if eixo == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def matriz(rx: float, ry: float, rz: float) -> np.ndarray:
    """R = Rz·Ry·Rx — mesma ordem que a página aplica no navegador."""
    return _rot("z", rz) @ _rot("y", ry) @ _rot("x", rx)


def _mundo_pelo_modelo(contorno, comprimento, transform):
    """Vértices que o MODELO LOCAL produz, nas duas tampas da extrusão."""
    pts = np.asarray(contorno, dtype=float)
    a, b = pts[:, 0], pts[:, 1]
    if transform["espelhado"]:
        a = a.max() - a
    R = matriz(transform["rx"], transform["ry"], transform["rz"])
    saida = []
    for t in (0.0, comprimento):
        local = np.stack([np.full(len(pts), t), b, a], axis=1)
        mundo = local @ R.T + np.array([transform["tx"], transform["ty"],
                                        transform["tz"]])
        saida.append(mundo)
    return np.concatenate(saida)


def _mundo_pelo_renderer(contorno, comprimento, instancia):
    """Vértices que o renderer produz hoje. Referência de verdade: se o modelo
    local não bater com isto, a ferramenta estaria mostrando uma composição
    diferente da que a imagem oficial mostra."""
    faces = extrudar_perfil(contorno, comprimento, instancia.rotacao_graus,
                            instancia.posicao_mm,
                            rotacao_xyz=instancia.rotacao_xyz,
                            posicao_z_mm=instancia.posicao_z_mm)
    return np.concatenate([np.asarray(faces[0]), np.asarray(faces[1])])


def deduzir_transform(contorno, comprimento, instancia):
    """Transformação local da instância, CONFERIDA contra o renderer.

    Desde que a cena passou a carregar `rotacao_xyz`/`posicao_z_mm`, não há
    mais nada a deduzir: a composição já fala o mesmo idioma da viewport. O
    que continua havendo é a conferência — os vértices que este modelo produz
    têm de bater com os que o renderer desenha, dentro de 1e-6 mm, ou a
    viewport estaria mostrando uma composição diferente da imagem oficial e
    Bruno validaria a coisa errada.

    `espelhado` permanece no formato exportado por compatibilidade com o que
    Bruno já usou, mas a composição não gera mais espelho: um perfil extrudado
    não pode ser espelhado no mundo físico (ver `InstanciaCena`)."""
    rx, ry, rz = instancia.rotacao_xyz or (0.0, 0.0, 0.0)
    dx, dy = instancia.posicao_mm
    cand = {"tx": float(dx), "ty": float(dy), "tz": float(instancia.posicao_z_mm),
            "rx": rx, "ry": ry, "rz": rz, "espelhado": False}

    alvo = _mundo_pelo_renderer(contorno, comprimento, instancia)
    obtido = _mundo_pelo_modelo(contorno, comprimento, cand)
    if not np.allclose(obtido, alvo, atol=1e-6):
        raise RuntimeError(
            f"{instancia.instancia_id}: o modelo da viewport não reproduz o "
            f"que o renderer desenha (erro máx "
            f"{np.abs(obtido - alvo).max():.6f} mm)")
    return cand


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------

def coletar() -> dict:
    receita = construir_receita_preliminar()
    cena = montar_cena_suprema_2f(receita)
    bib = carregar_biblioteca()

    grupo_por_id = {c.identificador: GRUPO_DO_PAPEL[c.papel]
                    for c in receita.componentes}
    plano_por_id = {c.identificador: (c.folha or "") for c in receita.componentes}

    geometrias, instancias = {}, []
    for inst in cena.instancias:
        codigo = inst.perfil_id.removeprefix("ALCOA-")
        if codigo not in geometrias:
            perfil = Perfil(id=inst.perfil_id, fabricante="Alcoa",
                            codigo_fabricante=codigo)
            assoc = [a for a in bib.associacoes if a.perfil_id == inst.perfil_id]
            geos = {a.geometria_padrao_id: bib.geometria(a.geometria_padrao_id)
                    for a in assoc}
            geo = resolver_geometria(perfil, assoc, geos)
            geometrias[codigo] = {
                "externo": [[float(x), float(y)] for x, y in geo.contorno_externo],
                "vazios": [[[float(x), float(y)] for x, y in v]
                           for v in geo.vazios_internos],
            }

        transform = deduzir_transform(geometrias[codigo]["externo"],
                                      inst.comprimento_mm, inst)
        instancias.append({
            "id": inst.instancia_id,
            "rotulo": inst.instancia_id.split(":", 1)[-1],
            "codigo": codigo,
            "comprimento": float(inst.comprimento_mm),
            "grupo": grupo_por_id[inst.instancia_id],
            "plano": plano_por_id[inst.instancia_id],
            "inicial": transform,
        })
    return {"geometrias": geometrias, "instancias": instancias}


def gerar(saida: str = SAIDA) -> str:
    dados = coletar()
    with open(MODELO, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DADOS__*/null",
                        json.dumps(dados, ensure_ascii=False))
    with open(saida, "w", encoding="utf-8") as f:
        f.write(html)
    return saida


if __name__ == "__main__":
    caminho = gerar()
    print(f"Viewport gerada: {caminho}")
    print(f"Abra no navegador:  file://{caminho}")
