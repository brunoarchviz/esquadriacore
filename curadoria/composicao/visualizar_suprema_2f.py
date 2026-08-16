"""
EsquadriaCore — curadoria/composicao/visualizar_suprema_2f
============================================================
Primeira visualização real da Suprema de correr 2 folhas — exerce o gate de
visualização preliminar (ABERTO desde E.4D) pela primeira vez para esta
tipologia.

Fluxo: contrato.consumo (geometrias homologadas) + composicao.receita
(topologia confirmada, E.4E) + composicao.visualizacao (posições
ILUSTRATIVAS) -> core_engine.renderer (inalterado).

NÃO é cálculo de fabricação. As posições/comprimentos usados são
esquemáticos — ver `composicao/visualizacao.py`. Nenhuma regra dimensional
PENDENTE foi promovida; nenhum caso real ou fórmula candidata foi citado.

Uso:  python3 curadoria/composicao/visualizar_suprema_2f.py
Saída: curadoria/composicao/vista_suprema_correr_2f.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from contrato.consumo import carregar_biblioteca
from core_engine.renderer import renderizar
from domain.entidades import Perfil, Vista
from composicao.visualizacao import montar_cena_suprema_2f

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "vista_suprema_correr_2f.png")

CODIGOS = ("SU-001", "SU-002", "SU-003", "SU-039", "SU-040", "SU-041",
          "SU-053", "SU-102")


def gerar(saida: str = SAIDA) -> str:
    bib = carregar_biblioteca()
    cena = montar_cena_suprema_2f()

    perfis = {f"ALCOA-{c}": Perfil(id=f"ALCOA-{c}", fabricante="Alcoa",
                                   codigo_fabricante=c)
             for c in CODIGOS}
    associacoes = [a for a in bib.associacoes if a.perfil_id in perfis]
    geometrias = {a.geometria_padrao_id: bib.geometria(a.geometria_padrao_id)
                 for a in associacoes}

    # Ângulos explícitos, não o isométrico padrão. A composição usa Y como
    # altura da janela e Z como profundidade do quadro, enquanto o matplotlib
    # trata Z como vertical — com o padrão (35°, 45°) a janela aparece
    # DEITADA, o que atrapalha exatamente a leitura que o Bruno precisa fazer.
    # Só apresentação (ADR-002): não muda nada da cena.
    vista = Vista(id="V-SUPREMA-2F-ILUSTRATIVA", cena_id=cena.id,
                 tipo_projecao="isometrica", estilo="tecnico_ilustrativo",
                 angulo_elevacao_graus=60.0, angulo_azimute_graus=-75.0)

    return renderizar(vista, cena, perfis, associacoes, geometrias, saida)


if __name__ == "__main__":
    caminho = gerar()
    print(f"Vista gerada: {caminho}")
    print(f"{len(montar_cena_suprema_2f().instancias)} instâncias (esperado: 20)")
