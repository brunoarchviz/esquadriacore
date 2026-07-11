"""
Homologação em lote — Família GOLD (bitola 32mm)
=================================================
Estrutura na biblioteca todas as GeometriasPadrao da família Gold e suas
associações por fabricante, a partir das decisões de curadoria do Bruno.

Rodar no Claude Code, na raiz do repositório:
    source .venv/bin/activate && python3 homologar_gold.py

Decisões de curadoria (Bruno, 2026-07-10):
- Todos os perfis LG são a mesma geometria entre gerações e fabricantes,
  com variações apenas de peso e pequenas diferenças de medida (1-3mm) que
  NÃO alteram usabilidade → MESMA_GEOMETRIA em todos os casos.
- LG-020: MESMA_GEOMETRIA confirmada (apesar dos 9% de peso G3xG4).
- Nova Gold (linhagem GN): DESCARTADA por ora — perfis muito diferentes.
- Códigos SI- (catálogo base Alcoa) e códigos legados entre parênteses:
  registrados como aliases de rastreabilidade, não descartados.
"""

import json

# ---------------------------------------------------------------------------
# 1. Definição das geometrias GOLD com função (curadoria do Bruno)
#    e aliases conhecidos (SI- do catálogo base + código ASA MG32 + legado)
# ---------------------------------------------------------------------------

# codigo_LG: (funcao, alias_SI, codigo_ASA_MG32, obs_medida)
GOLD = {
    "LG-002": ("Marco Lateral Vertical", None, "MG32-016", None),
    "LG-003": ("Marco Bandeira / Peitoril", None, "MG32-017", None),
    "LG-004": ("Travessa Intermediária - Bandeira", None, "MG32-018", None),
    "LG-006": ("Folha Inferior e Superior Horizontal", None, "MG32-020", None),
    "LG-007": ("Folha Inferior Horizontal", None, "MG32-032", None),
    "LG-008": ("Trilho superior", None, None, "presente só nos catálogos Alcoa/Hydro"),
    "LG-009": ("Marco", None, None, "presente só nos catálogos Alcoa/Hydro"),
    "LG-010": ("Marco", None, None, "presente só nos catálogos Alcoa/Hydro"),
    "LG-011": ("Trilho superior 3 planos", None, None, "presente só nos catálogos Alcoa/Hydro"),
    "LG-014": ("Marco", None, None, "presente só nos catálogos Alcoa/Hydro"),
    "LG-015": ("Baguete", None, "MG32-115", None),
    "LG-016": ("Arremate Porta de Giro", None, "MG32-029", None),
    "LG-017": ("Folha Lateral Vertical com Reforço", None, None, None),
    "LG-018": ("Mão de amigo", None, "MG32-055", None),
    "LG-019": ("Mão de amigo", None, None, None),
    "LG-020": ("Folha", None, None, "peso G3 1.016 x G4 1.116 (9%), mas Bruno confirmou MESMA geometria"),
    "LG-021": ("Mão de amigo", None, None, None),
    "LG-022": ("Travessa", None, None, None),
    "LG-023": ("Mão de amigo", None, None, None),
    "LG-025": ("Trilho 2 planos", None, None, None),
    "LG-026": ("Baguete Vertical", None, "MG32-057", "MG32 3mm de diferença — não altera usabilidade"),
    "LG-027": ("Baguete Veneziana", None, "MG32-114", None),
    "LG-028": ("Complemento - Marco Lateral", None, "MG32-024", None),
    "LG-042": ("Folha", None, None, "sem equivalente em alguns catálogos; existe em Gold3 e Gold4 Alcoa"),
    "LG-043": ("Folha Perimetral Porta de Giro", None, "MG32-011", None),
    "LG-044": ("Marco Superior Horizontal", "SI-301", "MG32-001", None),
    "LG-048": ("Folha Mão de Amigo - Interno", "SI-309", "MG32-005", None),
    "LG-049": ("Folha Mão de Amigo - Externo", "SI-310", "MG32-006", None),
    "LG-050": ("Folha Lateral / Central Vertical", "SI-311", None, None),
    "LG-051": ("Folha Central Vertical", "SI-312", None, None),
    "LG-052": ("Mão de amigo", None, "MG32-054", None),
    "LG-053": ("Folha", "SI-314", "MG32-053", "1mm de diferença na medida — não altera usabilidade"),
    "LG-054": ("Folha", "SI-315", "MG32-056", "1mm de diferença na medida — não altera usabilidade"),
    "LG-055": ("Travessa Horizontal", "SI-317", "MG32-009", None),
    "LG-056": ("Marco Porta de Giro", "SI-319", "MG32-010", None),
    "LG-058": ("Folha", "SI-324", "MG32-026", None),
    "LG-059": ("Baguete Horizontal", "SI-328", "MG32-012", "MG32 2mm de diferença — não altera usabilidade"),
    "LG-062": ("Marco Superior Horizontal", "SI-343", None, None),
}

# Fabricantes que usam a nomenclatura LG diretamente (mesmo código)
FABRICANTES_LG = ["Alcoa", "Hydro", "VitralSul"]
# Centenário e Tamboré usam TMG no lugar de LG
FABRICANTES_TMG = ["Centenario", "Tambore"]

DATA = "2026-07-10"
RESP = "Bruno"
METODO = "comparação visual no catálogo impresso — família Gold, múltiplos fabricantes e gerações"


def main():
    with open("dados/geometrias.json") as f:
        geos = json.load(f)
    with open("dados/perfil_geometria.json") as f:
        assocs = json.load(f)

    ids_existentes = {g["id"] for g in geos["geometrias"]}
    novas_geos = 0
    novas_assocs = 0

    for lg, (funcao, si, mg32, obs_medida) in GOLD.items():
        geo_id = f"GEO-{lg}"
        if geo_id in ids_existentes:
            continue

        # aliases de rastreabilidade
        aliases = []
        if si:
            aliases.append(f"Alcoa base: {si}")
        if mg32:
            aliases.append(f"ASA: {mg32}")

        nota = "Homologação em lote família Gold. Equivalência confirmada por curadoria visual do Bruno em todos os catálogos. Contorno preciso pendente."
        if obs_medida:
            nota += f" NOTA: {obs_medida}."
        if aliases:
            nota += f" Aliases: {'; '.join(aliases)}."

        geos["geometrias"].append({
            "id": geo_id,
            "descricao": f"{funcao} — família Gold",
            "status": "bruto_aproximado",
            "versao": "1.0",
            "familia_mercado": "GOLD",
            "curado_por": RESP,
            "data_curadoria": DATA,
            "_nota": nota,
        })
        novas_geos += 1

        # associações: Alcoa/Hydro/VitralSul via LG
        for fab in FABRICANTES_LG:
            assocs["associacoes"].append({
                "perfil_id": f"{fab.upper()}-{lg}",
                "geometria_padrao_id": geo_id,
                "responsavel_homologacao": RESP,
                "metodo_validacao": METODO,
                "data": DATA,
                "nivel_de_confianca": "alto",
                "observacoes": f"Família Gold. Nomenclatura {lg}." +
                    (f" Alias base Alcoa: {si}." if (si and fab == 'Alcoa') else "")
            })
            novas_assocs += 1

        # Centenário e Tamboré via TMG (mesmo número, prefixo diferente)
        tmg = lg.replace("LG-", "TMG-")
        for fab in FABRICANTES_TMG:
            assocs["associacoes"].append({
                "perfil_id": f"{fab.upper()}-{tmg}",
                "geometria_padrao_id": geo_id,
                "responsavel_homologacao": RESP,
                "metodo_validacao": METODO,
                "data": DATA,
                "nivel_de_confianca": "alto",
                "observacoes": f"Família Gold. Nomenclatura local {tmg} (equivale a {lg}). Pesos diferem do padrão Alcoa."
            })
            novas_assocs += 1

        # ASA via MG32 (só quando há equivalente mapeado)
        if mg32:
            obs_asa = f"Família Gold. Nomenclatura ASA {mg32} (equivale a {lg})."
            if obs_medida and "MG32" in obs_medida:
                obs_asa += f" {obs_medida}."
            assocs["associacoes"].append({
                "perfil_id": f"ASA-{mg32}",
                "geometria_padrao_id": geo_id,
                "responsavel_homologacao": RESP,
                "metodo_validacao": METODO,
                "data": DATA,
                "nivel_de_confianca": "alto",
                "observacoes": obs_asa
            })
            novas_assocs += 1

    with open("dados/geometrias.json", "w") as f:
        json.dump(geos, f, ensure_ascii=False, indent=2)
    with open("dados/perfil_geometria.json", "w") as f:
        json.dump(assocs, f, ensure_ascii=False, indent=2)

    # relatório
    print(f"Novas geometrias GOLD: {novas_geos}")
    print(f"Novas associações: {novas_assocs}")
    print(f"\nBIBLIOTECA TOTAL:")
    print(f"  Geometrias: {len(geos['geometrias'])}")
    print(f"  Associações: {len(assocs['associacoes'])}")

    # contagem por família
    from collections import Counter
    fam = Counter(g.get("familia_mercado", "?") for g in geos["geometrias"])
    print(f"\n  Por família: {dict(fam)}")

    # fabricantes distintos nas associações
    fabs = set(a["perfil_id"].split("-")[0] for a in assocs["associacoes"])
    print(f"  Fabricantes na biblioteca: {sorted(fabs)}")


if __name__ == "__main__":
    main()
